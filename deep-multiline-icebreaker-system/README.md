# Deep Multiline Icebreaker System

## What it is

An n8n workflow that takes a list of lead search URLs from a Google Sheet, pulls
contact and company records for each via an Apify actor, scrapes each lead's company
website (home page plus a few internal subpages), summarizes each page with an LLM,
and combines those summaries into a personalized, multi-line cold-email opener. Each
result is appended as a row to a Google Sheet alongside the lead's contact details.

## Why it exists

Generic cold-email openers ("I love your website!") convert poorly. This workflow
exists to make an opener look deeply researched by actually reading multiple pages of
a prospect's site and folding specific, non-obvious details into the first two lines
of an email, at a cost of a few LLM calls per lead rather than a human spending
minutes per prospect.

## Features

- Bulk lead sourcing from an Apify actor call, filtered down to leads that have both
  a company website and an email address before any scraping happens.
- Per-lead loop that scrapes the homepage, extracts internal links, normalizes and
  deduplicates them, and caps subpage scraping to 3 pages per lead to control cost and
  runtime.
- Per-page LLM summarization, then an aggregation step that combines all of a lead's
  page summaries before the final icebreaker is written.
- A one-shot example baked into the icebreaker-writing prompt so the model has a
  concrete pattern to match (shortened company/location names, non-obvious details,
  a fixed sentence template) rather than free-form output.
- Results appended directly to a Google Sheet, one row per lead, so outreach tooling
  downstream can just read the sheet.

## Architecture

- **When clicking 'Test workflow'** (`n8n-nodes-base.manualTrigger`): the only entry
  point in this file. There is no schedule or webhook trigger wired in, so as shipped
  this only runs on manual execution in the n8n editor.
- **Get Search URL** (`n8n-nodes-base.googleSheets`, read): reads a row from a "Search
  URLs" sheet tab to get the next lead-search URL to run.
- **Call Apify Scraper** (`n8n-nodes-base.httpRequest`): a raw POST to
  `api.apify.com/v2/acts/<actor-id>/run-sync-get-dataset-items`, with the search URL
  as the body and `getPersonalEmails`/`getWorkEmails` flags set, requesting up to 500
  records. The Authorization header carries a bearer token hardcoded directly in the
  node (this has been replaced with a placeholder in this copy; see Security note
  below). The actor's own logic isn't visible from this workflow, only its inputs and
  outputs; the output shape (`first_name`, `last_name`, `email`, `organization`,
  `headline`, `city`, `country`) is consistent with a B2B contact/lead-search export,
  but which specific source service the search URL points at isn't determinable from
  the JSON alone.
- **Only Websites & Emails** (`n8n-nodes-base.filter`): drops any lead missing a
  company website URL or missing an email address before any scraping work happens.
- **Loop Over Items** (`n8n-nodes-base.splitInBatches`): iterates the filtered leads
  one at a time; everything from **Scrape Home** through **Add Row** runs per lead,
  then loops back for the next one.
- **Scrape Home** (`n8n-nodes-base.httpRequest`, `onError: continueErrorOutput`): GETs
  the lead's website homepage. Only the success output is wired downstream; the error
  output is left unconnected, so a lead whose homepage fails to load is silently
  dropped from that iteration rather than logged or retried.
- **HTML** (`n8n-nodes-base.html`, `extractHtmlContent`): pulls every `<a href>` on the
  homepage into a `links` array.
- **Edit Fields** (`n8n-nodes-base.set`): builds the lead's working record
  (`first_name`, `last_name`, `email`, `website_url`, `headline`, `location`, a blank
  `phone_number` placeholder, and the extracted `links`).
- **Split Out** (`n8n-nodes-base.splitOut`): turns the `links` array into one item per
  link so each can be filtered and normalized individually.
- **Filter**: keeps only links starting with `/`, i.e. relative internal paths,
  dropping external links, anchors, and mailto/tel links.
- **Code** (`n8n-nodes-base.code`): normalizes each link, if it's already a relative
  path it's kept as-is; if it's an absolute `http(s)` URL, the path is extracted and
  any trailing slash stripped.
- **Remove Duplicate URLs** (`n8n-nodes-base.removeDuplicates`): dedupes the
  normalized subpage paths for that lead.
- **Limit** (`n8n-nodes-base.limit`, `maxItems: 3`): caps subpage scraping to at most 3
  pages per lead.
- **Request web page for URL** (`n8n-nodes-base.httpRequest`,
  `onError: continueRegularOutput`): fetches each of the up-to-3 subpages. On error,
  the node continues with its regular (empty) output rather than stopping the run.
- **Markdown** (`n8n-nodes-base.markdown`): converts the fetched HTML to Markdown,
  substituting a literal `<div>empty</div>` when there's no page data (which is how
  the failed-fetch case from the previous node is actually handled downstream).
- **Summarize Website Page** (`@n8n/n8n-nodes-langchain.openAi`, `gpt-4.1`, JSON
  output): produces a two-paragraph abstract of each subpage, or "no content" if the
  page was empty.
- **Aggregate** (`n8n-nodes-base.aggregate`): collects all of a lead's per-page
  abstracts into a single array field for that lead.
- **Generate Multiline Icebreaker** (`@n8n/n8n-nodes-langchain.openAi`, `gpt-4.1`,
  JSON output): given the lead's name/headline and the combined page abstracts, plus
  one hardcoded few-shot example pair in the prompt (a real, publicly marketed
  business used purely to demonstrate the desired output format and tone), generates
  `{"icebreaker": "..."}`, a multi-line opener following a fixed template (shortened
  company/location names, specific non-obvious details, a closing pitch line).
- **Add Row** (`n8n-nodes-base.googleSheets`, append): writes the lead's contact
  fields plus the generated icebreaker to a "Leads" sheet tab, then loops back to
  **Loop Over Items** for the next lead.

## Setup

1. In n8n, go to **Workflows > Import from File** and import
   `deep-multiline-icebreaker-system.json`.
2. Create a Google Sheet with at least two tabs: one holding lead-search URLs (read by
   **Get Search URL**) and one to receive results (written by **Add Row**, expects
   columns `first_name`, `last_name`, `email`, `website_url`, `headline`, `location`,
   `phone_number`, `multiline_icebreaker`). Point both Google Sheets nodes at your own
   spreadsheet and tabs.
3. Set up an Apify actor that accepts a search URL and returns lead records shaped
   like `first_name`, `last_name`, `email`, `organization.website_url`, `headline`,
   `city`, `country`; update the actor ID in the **Call Apify Scraper** node's URL to
   match your own actor.
4. Replace the placeholder `YOUR_APIFY_API_TOKEN_HERE` in **Call Apify Scraper**'s
   Authorization header with a real Apify API token. This node uses a raw HTTP header
   rather than n8n's credential store, so the token has to be pasted directly into the
   node (or swapped for an n8n HTTP Header Auth credential, which is the safer option).
5. Attach credentials to the OpenAI and Google Sheets nodes.
6. Accounts/credentials needed: **OpenAI API**, **Google Sheets API**, **Apify API**.

## Usage

Populate the "Search URLs" sheet tab with lead-search URLs, then run the workflow
manually from the n8n editor (there's no schedule or webhook trigger wired in). Each
run pulls leads for the next search URL, works through them one at a time, and appends
a row per lead with its generated icebreaker to the results sheet.

## Challenges

- **Live Apify token hardcoded in the workflow JSON.** The original file had a real
  Apify bearer token typed directly into the HTTP Request node's header. It has been
  replaced with `YOUR_APIFY_API_TOKEN_HERE` in this copy; the original token should be
  rotated since it was stored in plaintext outside n8n's credential system.
- **Silent drop on homepage scrape failure.** `Scrape Home` sets
  `onError: continueErrorOutput`, but the error output isn't wired to anything. A lead
  whose homepage fails to load (timeout, blocked scraper, dead domain) just vanishes
  from that run with no log entry, rather than being recorded as a failed lead.
- **Subpage fetch failures degrade gracefully, but only by accident of a ternary.**
  `Request web page for URL` continues on error, and the downstream `Markdown` node
  happens to handle a missing `data` field with a fallback `<div>empty</div>`. This
  works, but it means a failed fetch and a genuinely empty page are indistinguishable
  by the time the summarizer sees them.
- **Chaining three sequential LLM calls per lead (summarize x up to 3, then one
  icebreaker call) with no retry logic.** None of the OpenAI nodes have retry or
  backoff configured. A rate limit or transient failure on any one call stops that
  lead's processing without an explicit fallback.
- **No trigger beyond manual execution.** As shipped, this only runs when someone
  clicks "Test workflow" in the n8n editor; there's no schedule trigger or webhook to
  make it run unattended.
- **Duplicated lookups of `Loop Over Items` and `Only Websites & Emails` state.**
  Downstream nodes repeatedly re-reference earlier nodes by name (for example,
  `$('Loop Over Items').item.json...`) rather than passing everything forward through
  the main data path; this works in n8n but makes the workflow harder to refactor
  without breaking a reference somewhere in the chain.

## What I learned

- n8n's `splitInBatches` (Loop Over Items) node has two outputs: one that fires once
  when the loop is done, and one that fires per batch/item while looping. Wiring the
  per-lead processing chain back into the loop node's input is what creates the
  "process one lead fully, then move to the next" behavior here.
- `onError: continueErrorOutput` vs `onError: continueRegularOutput` behave
  differently in a way that's easy to leave inconsistent: the former needs an explicit
  wire on the error output branch to do anything with the failure, the latter just
  keeps flowing with whatever (possibly empty) data comes back, silently.
- Baking a single strong few-shot example directly into a prompt (as done in
  **Generate Multiline Icebreaker**) is a simple, effective way to lock down output
  format and tone for a generative step, at the cost of the example being hardcoded
  and needing manual updates if the desired style changes.

## What I'd do differently

- Never hardcode an API token in a node parameter. Use n8n's HTTP Header Auth
  credential type for the Apify call instead, so the token lives in the credential
  store like every other integration in this workflow.
- Wire the error output of `Scrape Home` to a Sheets append (or a dedicated log)
  recording which leads failed to scrape and why, instead of letting them silently
  disappear.
- Add a schedule trigger (or a webhook) so the workflow can run unattended against a
  growing "Search URLs" queue, instead of relying on someone manually clicking "Test
  workflow."
- Add explicit retry/backoff on the OpenAI nodes given how many sequential LLM calls
  a single lead can trigger (up to 4: up to 3 page summaries plus 1 icebreaker call).
