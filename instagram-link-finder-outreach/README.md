# Instagram Link Finder Automation

## What it is

An n8n workflow that reads a lead list from Google Sheets (business name, address,
website) and, for each unprocessed row, asks a Perplexity model to research the
business's official Instagram account and assess their website's quality, then
writes the results back into the same sheet.

The original export had a real, live Google Sheet reference: a spreadsheet id and
full edit URL for a sheet named "Lead List." I've replaced both the id and the URL
with `YOUR_SPREADSHEET_ID` placeholders in `workflow.json`; that sheet id is not
included anywhere in this repo.

## Why it exists

Manually searching for a business's Instagram account and judging their website
quality, one row at a time across a lead list, is repetitive research work that an
LLM with search access can do reasonably well unattended. This automates that first
pass so a human reviewing the lead list starts with an Instagram guess, a confidence
level, and a website quality note already filled in.

## Features

- Reads all rows from a "Lead List" Google Sheet.
- Filters to rows where the `Confidence` column is still empty (not yet processed).
- Loops over each unprocessed row one at a time.
- Sends a structured research prompt to Perplexity per row, asking it to: find the
  business's official Instagram account (with a confidence level: high/medium/
  low/none) and evaluate their website (professional look, visible contact info,
  presence of About/Services/Contact sections, or `no_website` if none is listed).
- Parses the model's JSON response in a Code node, tolerating malformed output by
  falling back to a "Failed to parse response" placeholder result instead of
  crashing.
- Writes the Instagram URL, confidence, reasoning, website quality, and website
  reasoning back to the matching row.

## Architecture

Node-by-node, in execution order:

1. **When clicking 'Execute workflow'** (`manualTrigger`).
2. **Get row(s) in sheet** (`googleSheets`, no filters set): reads every row from
   the Lead List sheet.
3. **If** (`if`): keeps only rows where `Confidence` is empty, i.e. not yet
   processed.
4. **Loop Over Items** (`splitInBatches`): iterates rows one at a time; its "loop"
   output feeds "Message a model," and "Update row in sheet" connects back into this
   node to advance to the next row.
5. **Message a model** (`n8n-nodes-base.perplexity`): sends the business's name,
   address, and website in a prompt instructing the model to return only a JSON
   object with `instagram_url`, `instagram_confidence`, `instagram_reason`,
   `website_quality`, and `website_reason`.
6. **Code in JavaScript** (`code`): parses `choices[0].message.content` as JSON,
   with a try/catch fallback to a "none"/"unknown" result set if parsing fails, and
   also pulls a `cost_usd` field from the response's usage data if present.
7. **Update row in sheet** (`googleSheets`, update, matched by `row_number`): writes
   the parsed fields back to the row, then loops back to step 4 for the next row.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials needed after import (see `CREDENTIALS.md`): Google Sheets OAuth2 and a
Perplexity API credential. Your sheet needs columns for Name, Address, Website,
Instagram, Confidence, Reason, Website Quality, and Website Reason at minimum; the
schema in the "Update row in sheet" node also references Rating, Reviews, and Phone
columns that this workflow doesn't itself populate, so they're likely used
elsewhere in the source spreadsheet (lead enrichment from another tool, most likely).

## Usage

Run the workflow manually. It processes every row currently marked unprocessed
(empty `Confidence`) in one pass, one row at a time, writing results back as it
goes. Re-running it skips rows already filled in.

## Challenges

- **No rate limiting or delay between Perplexity calls.** The loop fires one
  request per row with nothing throttling the pace: no Wait node, no batching by
  time, nothing. On a lead list of any real size, this risks hitting Perplexity's
  rate limits mid-run, and a rate-limited row would presumably fail the JSON parse
  and get written with the fallback "Failed to parse response" values rather than
  being retried.
- **The Code node's fallback silently masks real failures.** If Perplexity returns
  something that isn't valid JSON (a partial response, an error message, a rate
  limit notice), the workflow writes "Failed to parse response" into the sheet and
  moves on. That's better than crashing the whole run, but it means a batch of API
  failures looks identical, in the sheet, to a batch of "the model genuinely
  couldn't identify this business," with no way to tell which happened from the
  output alone.
- **No validation on the model's Instagram guess.** The prompt is careful to say
  "only return an account you are reasonably confident belongs to THIS exact
  business," but nothing in the workflow verifies that. A `high` confidence result
  is exactly as unverified as `low`, it's whatever the model self-reports, not
  something checked against Instagram's API.
- **A real production spreadsheet id was hardcoded in the export.** The version
  fetched from the live n8n instance embedded an actual Google Sheets id and full
  edit URL twice, once on the read node and once on the write node. Both are
  replaced with placeholders in this copy.
- **The sheet schema has columns this workflow never writes.** "Update row in
  sheet"'s column schema lists Rating, Reviews, and Phone as available fields, but
  no node in this graph ever sets them, suggesting this workflow is one piece of a
  larger lead-generation pipeline (probably a separate scraping step upstream) that
  wasn't part of what got exported here.

## What I learned

Wrapping an LLM's JSON output in a try/catch with an explicit fallback object,
rather than letting a malformed response throw and kill the whole batch, is a
small pattern that matters a lot at scale: one bad response out of a hundred
shouldn't stop the other ninety-nine rows from being processed. It's a pattern
worth reusing anywhere an LLM's output feeds directly into a downstream write step.

## What I'd do differently

I'd add a Wait node inside the loop to throttle the Perplexity calls, and split the
"failed to parse" case from the "model returned none" case with distinct marker
values, so a human scanning the sheet afterward can tell API failures apart from
genuine no-Instagram-found results. I'd also add a lightweight verification step
(even just an HTTP HEAD request to the returned Instagram URL) before writing a
`high` confidence result, instead of trusting the model's self-reported confidence
outright.
