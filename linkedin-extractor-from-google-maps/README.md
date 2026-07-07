# Linkedin Extractor from Google Maps

## What it is

An n8n workflow, exported live from n8n instance workflow id `6DcdsZUcrFuiYpB8`, that is
actually two separate sub-workflows sharing one canvas:

1. A **lead extractor**: takes a business search (keyword, location, category) from a
   web form, runs Apify's Google Maps Scraper actor against it, pulls out the contact
   people that actor's Lead Enrichment add-on finds for each business (name, job title,
   email, seniority, and LinkedIn profile URL), and writes both the raw business
   listings and the flattened person-level leads into a Google Sheet.
2. A **lead qualifier**: reads leads back out of that same sheet, sends each one to
   Perplexity with a fixed prompt asking "is this company a potential buyer of baby and
   children's textile products", and writes `Qualified` or `Disqualified` back next to
   the lead.

The two flows are marked with sticky notes on the canvas ("Main Lead Extractor" and
"Lead Qualifier") and run independently: one triggers from a form submission, the other
runs manually.

**Naming note:** despite the workflow's name, nothing in this graph scrapes LinkedIn
directly. The LinkedIn profile URL is one of several fields ("linkedinProfile") that
Apify's Google Maps Scraper returns as part of its optional, paid Lead Enrichment
feature, alongside email, job title, and seniority. So this is a Google Maps business
scraper with person-level lead enrichment, of which a LinkedIn URL is one output field,
not a workflow that queries LinkedIn.

## Why it exists

This is built for a specific sales use case: finding businesses on Google Maps that
might buy baby and children's textile products (towels, blankets, swaddles, clothing),
then getting a named contact person at each business (with their LinkedIn profile,
email, and job title) instead of just a company phone number, and getting a fast
first-pass answer on whether that company is worth pursuing at all before a human
spends time on it.

## Features

- Web form intake for search parameters (keyword, location, max places, category
  filter), so a non-technical user can kick off a scrape without touching n8n.
- Runs Apify's Google Maps Scraper actor (`compass/crawler-google-places`) with its
  Lead Enrichment option turned on, capped at 2 enriched contacts per business, biased
  toward c-suite, operations, and marketing departments.
- Two-level deduplication: once against duplicate business names within a single Apify
  run, and again against every business already stored in the sheet (matched by Google
  Maps `placeId`), so re-running the same search doesn't create duplicate rows.
- Flattens each business's enriched contacts into individual lead rows (one row per
  person, not per business), then deduplicates people by LinkedIn URL and caps it at 2
  leads per company, preferring the more senior contact.
- A second, separately triggered flow reads back leads with no qualification `Status`
  yet, asks Perplexity to research the company and return `Qualified` or
  `Disqualified`, and writes that verdict back onto the same sheet row.

## Architecture

Node-by-node, in execution order. Node types are the exact n8n type strings from the
export.

**Lead extractor (form-triggered):**

1. **Google Maps Form1** (`formTrigger`): collects `Search Keyword` (required text),
   `Location` (dropdown of countries), `Max Places`, and `Category Filter` from a
   submitted form.
2. **Code in JavaScript5** (`code`): reads that form data and builds the JSON body
   Apify's Google Maps Scraper actor expects: `searchStringsArray`, `locationQuery`,
   `maxCrawledPlacesPerSearch`, plus fixed options that turn on Lead Enrichment
   (`maximumLeadsEnrichmentRecords: 2`, `leadsEnrichmentDepartments: ['c_suite',
   'operations', 'marketing']`) and turn off most other scraping options (reviews,
   images, social profiles, place detail pages) to keep the run focused and cheaper.
3. **Run an Actor and get dataset(Google Maps)** (`@apify/n8n-nodes-apify.apify`,
   operation "Run actor and get dataset"): runs Apify actor `nwua9Gu5YrADL7ZDj`
   ("Google Maps Scraper (compass/crawler-google-places)") with that body and returns
   its dataset, one item per business found.
4. **Remove Duplicates from Apify** (`code`): drops duplicate businesses within this
   run's results, keyed on lowercased `title`.
5. **Get row(s) in sheet1** (`googleSheets`): reads every existing row from the
   "Location" tab of the "Linkedin Leads - Google Maps" spreadsheet, to know what's
   already been stored.
6. **Remove Duplicates from Old Data and new data** (`code`): drops any business from
   this run whose Google Maps `placeId` already exists in the "Location" sheet.
7. **Append or update row in sheet** (`googleSheets`, operation `appendOrUpdate` on the
   "Location" tab): writes the surviving new businesses, auto-mapping every Apify field
   (title, address, phone, website, category, coordinates, `leadsEnrichment`, and
   dozens more) as its own column.
8. **Clean Lead Enrichment** (`code`): re-reads the deduplicated business list from
   step 6 and flattens each business's `leadsEnrichment` array (the enriched people
   Apify found) into one output row per person: Company, Website, Phone, First Name,
   Last Name, Job Title, Email, Email Status, Seniority, LinkedIn.
9. **Code in JavaScript** (`code`): deduplicates those person rows by LinkedIn URL,
   ranks them by seniority (c_suite first, then founder, senior, manager, entry), and
   keeps at most 2 people per company.
10. **Append or update row in sheet2** (`googleSheets`, operation `appendOrUpdate` on
    the "Leads" tab): writes the final lead rows.

**Lead qualifier (manually triggered, separate entry point):**

1. **When clicking 'Execute workflow'** (`manualTrigger`): starts this flow by hand.
2. **Get row(s) in sheet2** (`googleSheets`): reads every row currently in the "Leads"
   tab.
3. **If** (`if`): keeps only rows where the `Status` column is empty, i.e. not yet
   qualified.
4. **Limit** (`limit`): the node has no configured options, which means it uses n8n's
   default of keeping just the first item. In practice this flow qualifies one
   unqualified lead per manual execution, not a batch, unless someone opens the node
   and raises the limit.
5. **Loop Over Items** (`splitInBatches`): loops over whatever Limit passed through.
6. **Message a model** (`n8n-nodes-base.perplexity`): sends a fixed system prompt
   ("you only ever respond with one word: Qualified or Disqualified") plus a user
   prompt hardcoded to ask whether the company is a potential buyer of baby and
   children's textile products, referencing that lead's Company and Website fields.
7. **Update row in sheet** (`googleSheets`, operation `update`, matched on
   `row_number`): writes Perplexity's one-word answer into the `Status` column of that
   lead's row, then loops back into **Loop Over Items** for the next item (there is
   only one, given the Limit default).

The `Loop Over Items` node's "done" output (fired once the batch is empty) is not
wired to anything, so the qualifier flow just stops silently once it finishes; there is
no summary or notification step.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

The exported JSON does not include any credential references (n8n's API strips
credential bindings from workflow exports), so after import every credential-requiring
node needs its credential picked manually in the n8n editor. Accounts/credentials
needed:

- An **Apify** account and API credential, for the "Run an Actor and get
  dataset(Google Maps)" node. The Google Maps Scraper actor and its Lead Enrichment
  add-on are paid Apify usage, billed per run/result.
- A **Google Sheets** (OAuth2) credential with edit access to a spreadsheet that has a
  "Location" tab and a "Leads" tab (the "Leads" tab needs a `Status` column for the
  qualifier flow to write into), for all four Google Sheets nodes.
- A **Perplexity** API credential, for the "Message a model" node.

You also need to create the target spreadsheet yourself (or point the Google Sheets
nodes at your own copy) with columns matching what the code nodes emit: the "Location"
tab needs the wide set of Apify Google Maps fields (title, address, phone, website,
placeId, leadsEnrichment, and so on); the "Leads" tab needs Company, Website, Phone,
First Name, Last Name, Job Title, Email, Email Status, Seniority, LinkedIn, and Status.

## Usage

1. Submit the "Google Maps Scraper" form with a search keyword, a location, a max
   place count, and an optional category filter. This runs the extractor flow end to
   end and populates both sheet tabs.
2. Open the workflow in n8n and click "Execute workflow" to run the qualifier flow.
   Each click qualifies one unqualified lead (see the Limit node note above); run it
   repeatedly, or raise the Limit node's max items, to work through a backlog.

Before reusing this for anything other than baby/children's textile sales, rewrite the
user prompt inside the "Message a model" node. The workflow's own sticky note flags
this explicitly: "Need to update perplexity user prompt before using."

## Challenges

- **Two unrelated flows share one workflow file.** The extractor (form-triggered) and
  the qualifier (manual-triggered) have no node-level connection between them; they
  only share the Google Sheet as a common data store. Reading the JSON cold, without
  the sticky notes, it would be easy to mistake this for one linear pipeline that had
  a broken connection somewhere, when it's actually two separate entry points.
- **The qualifier's business logic is hardcoded to one product line.** The Perplexity
  prompt names specific products (baby hooded towels, swaddle sets, muslin wraps) and
  qualification rules for a textile business. There's no parameter, form field, or
  variable that swaps this out; reusing the workflow for a different product means
  editing the prompt text directly, which the workflow's own sticky note calls out as
  a required step before use.
- **Deduplication logic lives in code, not in the Sheets node config.** Both
  "appendOrUpdate" Google Sheets nodes have `matchingColumns` left empty, so the sheet
  operation itself isn't set up to recognize an existing row as a match; if it ran on
  its own without the upstream Code nodes, it would just append every row. The actual
  dedup work (by business title, then by `placeId`, then by LinkedIn URL) happens
  entirely in the three Code nodes before the data ever reaches the Sheets nodes. That
  works as built, but it means the Sheets nodes' own "or update" behavior is currently
  unused, not a backstop.
- **The qualifier processes one lead per run by default.** The Limit node has no
  configured value, which in n8n defaults to keeping the first item only. Nothing in
  the graph signals this; someone reading "Loop Over Items" would reasonably assume it
  loops over every unqualified lead, not just the one item Limit let through.
- **Contact enrichment quality depends entirely on Apify's third-party data.** Job
  title, seniority, and email verification all come from Apify's Lead Enrichment
  add-on with no independent check inside the workflow; a wrong seniority label
  upstream directly changes which contact survives the "keep 2 per company" cap.
- **No handling for a failed Apify run or a failed Perplexity call.** Neither the
  Apify node nor the Perplexity node has retry, continue-on-error, or a fallback
  branch configured. A rate limit or timeout on either service stops that execution
  with nothing written for that run.

## What I learned

Reading node graphs, not just their names, matters more than it seems: the workflow's
title promises a LinkedIn extractor, but the LinkedIn URL is a side effect of Apify's
Lead Enrichment feature on a Google Maps scrape, not a thing this workflow queries for
itself. Tracing the `Loop Over Items` connections also made it clear that a
`splitInBatches` node's "done" output being unwired isn't a bug exactly, it's just a
flow that has nowhere further to go, which is easy to miss unless you check both of
its outputs rather than assuming the obvious one. Same with the Limit node: an empty
parameters object isn't "no limit," it's n8n's default of 1, and that single fact
changes what "Execute workflow" actually does per click.

## What I'd do differently

I'd split this into two separate workflows instead of one file with two disconnected
flows sharing sticky-note labels; it would make the trigger boundaries obvious instead
of something you have to trace through connections to find. I'd move the qualifier's
product criteria out of the hardcoded prompt text and into form fields or a workflow
variable, since the workflow's own sticky note admits it needs editing before reuse. I'd
also set an explicit, documented value on the Limit node (or replace it with an
explicit batch size) so "Execute workflow" processes a predictable number of leads
instead of silently defaulting to one, and I'd wire the `Loop Over Items` "done" output
to at least a count or a completion log so a run doesn't just stop with no signal that
it finished.
