# Competitor Content Gap Analyzer

An n8n workflow that reads a list of competitor URLs from a Google Sheet, scrapes and
cleans each page's text, sends it to InfraNodus's GraphRAG API for topic and
content-gap analysis, writes the results back to the sheet, and then synthesizes a
final report of the overall content gaps into a Google Doc.

The internal workflow name is "Competitors Content Gaps copy," and the node graph and
sticky-note walkthrough match InfraNodus's own published "Content Gap Analysis with
GraphRAG" community template closely enough (same InfraNodus API endpoint and request
parameters, same stage numbering in the sticky notes, same overall Sheet-in,
Sheet-and-Doc-out structure) that this looks like an adapted copy of that public
template rather than an original design. I am documenting what the copy actually does,
not claiming to have designed the approach.

## Why it exists

Manually reading every competitor's site to figure out what topics they cover, and
what they are missing, does not scale past a handful of companies. This workflow turns
a spreadsheet of competitor URLs into a batch job: fetch each page, extract the topics
InfraNodus's graph analysis finds in it, and roll all of that up into one report of
where the shared content gaps are across the whole set.

## Features

- Reads company names and URLs from a Google Sheet and processes them in the batches
  driven by n8n's Split In Batches node, with a Wait step between batches to reduce the
  chance of hitting the InfraNodus rate limit.
- Fetches each competitor page over HTTP, strips it down to visible text with an HTML
  Extract node, and truncates it to 10,000 characters before sending it out for
  analysis.
- Calls the InfraNodus GraphRAG API three separate times for three different jobs: a
  per-page topical/graph summary during the scrape loop, then, after all pages are
  processed, a synthesized "AI advice" pass and a separate "gap question" pass over the
  combined summaries.
- Writes the per-page Topical Summary and Graph Summary back into the same Google
  Sheet row, matched by URL.
- Appends the final synthesized advice and top three gap-driven questions into a
  Google Doc as the deliverable report.
- Includes a second, separate sub-flow (disabled by default) that takes a market niche
  typed into an n8n form, asks Perplexity's API for a list of ~20 companies in that
  space, reformats the answer into strict JSON with an OpenAI call, and appends the
  resulting Name/URL/Category rows into the same Google Sheet, so the sheet can be
  seeded before the main analysis runs.

## Architecture

Two independent flows share one Google Sheet.

**Main flow** (manual trigger, "When clicking Execute Workflow"):

1. `Read a Google Sheets File` pulls all rows (company name + URL) from the sheet.
2. `Split In Batches` feeds rows into two parallel branches: one for the batch item
   itself, one for the HTTP fetch.
3. `HTTP Request` (`continueOnFail: true`, follows redirects) fetches each URL.
4. `HTML Extract` pulls the full `<html>` element's text out of the response.
5. `Clean Content` (Code node) strips newlines and collapses whitespace, then slices
   the result to 10,000 characters as `contentShort`.
6. `InfraNodus GraphRAG Content Enhancer` POSTs `contentShort` to
   `infranodus.com/api/v1/graphAndAdvice` with `requestMode=summary` and
   `aiTopics=true`, returning a topical summary and (when requested) a graph summary.
7. `Merge` (combine by position) rejoins the InfraNodus response with the original
   sheet row.
8. `Update Google Sheets with Content Insights` writes the Graph Summary and Topical
   Summary columns back, matched on the URL column.
9. `Wait to avoid API overload` pauses, then `If Node: did we process all the data?`
   checks the Split In Batches loop state and either loops back to step 2 or falls
   through to the second stage.
10. `Get the content from Google Sheets` re-reads the now-enriched sheet, and
    `Aggregate` collects every row's Topical Summary and Graph Summary into two arrays.
11. Those arrays feed two parallel InfraNodus calls: `InfraNodus AI Advice`
    (`optimize=develop`, `requestMode=response`) and `InfraNodus Question Generator`
    (`optimize=gap`, `requestMode=question`), both asking InfraNodus to identify the
    main topics and gaps across the combined text.
12. `Merge1` combines both responses, and `Google Docs` appends the AI advice text plus
    the top three generated questions into a specific Google Doc.

**Seed sub-flow** (disabled form trigger, "On form submission"): takes a niche and
optional instructions, asks Perplexity's `sonar-pro` model for a JSON list of roughly
20 companies in that niche, has an OpenAI `gpt-4o-mini` call reformat that into strict
JSON, splits the list into individual items with `Split Out`, and appends each one
(Name, URL, Category) to the same Google Sheet via a `Loop Over Items` / `Google
Sheets` append loop. This flow is disabled in the exported JSON; the sticky note says
to trigger it manually with n8n's "Test Workflow" button when you need to generate a
starting list of URLs.

## Setup

1. In n8n, go to Workflows, choose Import from File, and select `workflow.json` from
   this folder.
2. Create and attach the credentials listed in `CREDENTIALS.md`: Google Sheets OAuth2,
   Google Docs OAuth2, an InfraNodus API bearer token, a Perplexity API bearer token,
   and an OpenAI API key. None of these are present in the exported file.
3. Make your own copy of a Google Sheet with at minimum these columns: company name,
   URL, Topical Summary, Graph Summary (and, if you plan to use the seed sub-flow,
   Name/URL/Category as separate columns or a matching layout). Point every Google
   Sheets node at your copy (`documentId` and `sheetName`).
4. Point the `Google Docs` node at a Google Doc you own for the final report.
5. If you want to use the niche-to-company-list seed sub-flow, enable the "On form
   submission" trigger node (it ships disabled) and run it via n8n's Test Workflow
   button, filling in the Niche and Additional Search Instructions fields.
6. Run the main flow from the manual trigger once the sheet is seeded with company
   names and URLs.

## Usage

Populate the Google Sheet with competitor names and URLs (either by hand, by running
the seed sub-flow, or by generating the list some other way), then execute the main
workflow. It fetches and analyzes each URL, writes per-page summaries back to the
sheet, and appends a combined content-gap report to the linked Google Doc once every
row has been processed.

## Challenges

- **Rate limiting against the InfraNodus API.** The workflow makes one InfraNodus call
  per competitor page, plus two more per full run for the synthesis step. The graph
  addresses this with `Split In Batches` plus a `Wait to avoid API overload` node
  between batches, per Sticky Note 6/7's own description of the problem. The batch
  size itself is left at whatever `Split In Batches`'s default is; the sticky note
  says "batches of 10" but the node's parameters in this export set no explicit
  `batchSize`, so the actual throttling behavior depends on n8n's default rather than
  anything visible in the node configuration.
- **Scraped pages are not guaranteed to return usable text.** `HTTP Request` and `HTML
  Extract` are both set to `continueOnFail: true`, and `Clean Content` guards with
  `if ($input.item.json.body)` before touching it. That means a dead link, a
  JavaScript-rendered page with no server-side HTML, or a non-200 response fails
  silently rather than crashing the run, but it also means a row can silently end up
  with no content and no summary, with nothing in the graph that flags which rows
  failed.
- **The content-cleaning code is broken.** The `Clean Content` node's stored source is
  `if ($input.item.json.body){nnnn$input.item.json.content = ...}`, meaning the
  newlines that should separate statements have been collapsed into literal letter "n"
  characters glued directly onto the next token. That turns `{` followed by
  `$input.item.json.content = ...` into a single expression `nnnn$input.item.json.content
  = ...`, which throws a `ReferenceError` (`nnnn$input` is not defined) the moment the
  `if` branch runs. The two regex arguments in that same line are also passed as
  quoted strings (`'/^s+|s+$/g'`, `'/(rn|n|r)/gm'`) rather than real `RegExp` literals,
  so even if the syntax were fixed they would not match whitespace or newlines as
  intended. Because the node has `continueOnFail: true` and `alwaysOutputData: true`,
  this failure is swallowed silently: the item passes through unmodified, `content` and
  `contentShort` are never actually set, and the InfraNodus call downstream receives
  whatever `contentShort` resolves to (effectively empty), not the cleaned, truncated
  page text the sticky note describes.
- **Matching enriched results back to the right row.** After the InfraNodus call
  returns, the workflow has to reattach that result to the correct company. It solves
  this two different ways in two places: `Merge` (combine by position) inside the
  per-batch loop, which is fragile if any item is dropped or reordered mid-batch, and
  `Update Google Sheets with Content Insights`, which more robustly matches by the URL
  column rather than position. The final aggregation stage relies on `Merge1`'s
  `fieldsToMatchString: "aiAdvice"` to line up the two parallel InfraNodus responses.
- **Two independent trigger points feeding one sheet.** The seed sub-flow (form
  trigger) and the main flow (manual trigger) both write to and read from the same
  Google Sheet, but nothing in the graph enforces running them in order or prevents
  the main flow from running against a stale or partially-seeded sheet. That
  sequencing has to be handled by whoever operates the workflow, not by the workflow
  itself.

## What I learned

- Reading an n8n export closely enough to describe it accurately means tracing the
  `connections` block by node name, not just the `nodes` array. Several nodes (like
  `Merge` and `Merge1`) only make sense once you see which named input is wired to
  which numbered `index` on the merge node.
- Sticky notes in an n8n export are documentation the original author left for
  themselves, and they are worth reading, but they describe intent, not necessarily
  what the code actually does. The gap between what Sticky Note 3 claims ("clean up
  the content to extract only text") and what the `Clean Content` node's stored source
  actually contains (newlines collapsed into literal "n" characters, breaking the
  script and throwing on every run) only shows up by reading the raw JavaScript string
  in the JSON, not by reading the node's description.
- `continueOnFail: true` combined with `alwaysOutputData: true` is a common pattern for
  keeping a batch job moving past bad individual items, but it also means failures are
  invisible unless something downstream explicitly checks for them, which this
  workflow does not.

## What I'd do differently

- Fix the `Clean Content` node outright: restore real line breaks between statements
  so it does not throw a `ReferenceError` on every item, and replace the quoted-string
  regex arguments with real `RegExp` literals (e.g. `/^\s+|\s+$/g` and `/\s+/g`) so the
  content actually sent to InfraNodus is the cleaned, truncated page text the workflow
  is supposed to produce, not an unset field.
- Add an explicit check after the HTTP fetch/extract step that flags or routes rows
  with empty content, rather than letting them silently continue with `""` or
  `undefined` all the way through the InfraNodus call.
- Set an explicit `batchSize` on `Split In Batches` instead of leaving it at whatever
  the node's default is, so the "batches of 10" the sticky note promises is actually
  what happens.
- Replace the position-based `Merge` node in the per-page loop with a match-by-URL
  merge, consistent with how `Update Google Sheets with Content Insights` already does
  it, so the pairing does not depend on item order surviving the HTTP fetch step.
- I did not run this workflow end to end. Doing so needs a live InfraNodus account and
  token, a Perplexity key, an OpenAI key, Google OAuth credentials, and a Google Sheet
  and Doc set up with the right columns, none of which I provisioned here. The
  behavior described above is based entirely on reading the node graph and code, not
  on an observed run.
