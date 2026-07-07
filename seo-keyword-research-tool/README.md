# SEO Keyword Research Tool

## What it is

An n8n workflow that takes one seed keyword and pulls a full set of DataForSEO keyword
research data around it: related keywords, keyword suggestions, keyword ideas, Google
autocomplete suggestions, subtopics, top organic SERP results, and People Also Ask
questions. Everything is written into a fresh, per-run Google Sheet copied from a
template, plus a consolidated "Master All KW Variations" tab.

## Why it exists

Provenance first, honestly: the source filename was
`Basic_AI_SEO_KW_Research_n8n_DataForSEO_Gumroad_030125.json`, and the workflow's own
sticky notes credit an author ("Wayne Ergle") and a paid Gumroad product page. This is
a purchased template, not an original design, in the same sense that `cpp-ray-tracer`
in this Portfolio keeps its GPL scaffold's license because the class hierarchy
underneath it derives from someone else's code, not mine. Here the workflow itself
(node graph, prompts where used, sheet structure) is the purchased artifact; I did not
design the six-endpoint DataForSEO query pattern or the sheet schema. What I did was
read it closely enough to document exactly how it moves data through six parallel API
calls into six destination tabs, which is what the rest of this README covers.

## Features

- One manual trigger reads a "Main Keyword" row (keyword, location, language, result
  limit) from a template sheet, so the same sheet can be reused for many runs by
  changing one row.
- Creates a new Google Drive folder and a fresh copy of the results-sheet template per
  run, named after the keyword and date, so results from different keywords never mix
  in the same spreadsheet.
- Fires six parallel DataForSEO API calls off the same seed input:
  related keywords, keyword suggestions, keyword ideas, Google autocomplete, generated
  subtopics, and Google organic SERPs (which also carries People Also Ask data).
- Each result set is split out, field-mapped, and appended both to its own dedicated
  sheet tab and to a shared "Master All KW Variations" tab, so you can look at one
  data type or everything at once.

## Architecture

Trigger: `When clicking 'Test workflow'` (Manual Trigger; this is meant to be run on
demand per keyword, not on a schedule).

1. `Google Sheets KW Research Template` reads the single active row (Main Keyword,
   Location, Language, Limit) from a fixed "Main Keyword" sheet tab.
2. `Google Drive Create KW Folder` creates a new Drive folder named
   `<keyword> KW Research <date>`.
3. `Google Drive Copy KW Template` copies the master results-sheet template into that
   new folder, named `<keyword> Keyword Research <date>`.
4. `Set Main Fields` collects the keyword, location, language, limit, and the new
   sheet's file name/ID into one item, which every downstream branch references by
   node name (`$('Set Main Fields')`) rather than by chained output, since the six
   API branches all fan out from here in parallel.
5. Six parallel `HTTP Request` nodes call DataForSEO, all using HTTP header auth
   against the same credential:
   - `HTTP Related Keywords` -> `dataforseo_labs/google/related_keywords/live`
   - `HTTP Keyword Suggestions` -> `dataforseo_labs/google/keyword_suggestions/live`
   - `HTTP Keyword Ideas` -> `dataforseo_labs/google/keyword_suggestions/live` (same
     endpoint as suggestions, used a second time for a differently-processed result
     set; this is a property of the purchased template, not something added here)
   - `HTTP Autocomplete` -> `serp/google/autocomplete/live/advanced`
   - `HTTP Subtopics` -> `content_generation/generate_sub_topics/live`
   - `HTTP SERPs` -> `serp/google/organic/live/advanced` (also carries
     `people_also_ask` data at `depth: 20`)
6. Each HTTP response is split with a `Split Out` node on the relevant results array,
   field-mapped with a `Set` node (search volume, competition, keyword difficulty,
   CPC, search intent, etc. where the endpoint provides them), and appended with a
   `Google Sheets` node both to its dedicated tab and to the shared "Master All KW
   Variations" tab.
7. The SERP branch additionally splits into two filters: `Filter SERPs` (type =
   "organic") feeds the SERP results sheet; `Filter PAA` (type = "people_also_ask")
   feeds a separate People Also Ask sheet, both of which also append to the master
   tab.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- DataForSEO account and API credential (HTTP header auth), used by all six research
  HTTP Request nodes. The DataForSEO signup link referenced in this workflow's own
  setup notes carries the original author's affiliate tag; use your own DataForSEO
  account directly if you'd rather not use it.
- Google Sheets OAuth2 account, used to read the Main Keyword row and append results.
- Google Drive OAuth2 account, used to create the per-run folder and copy the sheet
  template.

Before running: create a Google Drive folder for this tool, copy the results-sheet
template referenced in the workflow's setup sticky note into it (removing "copy" from
the filename), and update the workflow's Google Sheets/Drive node references (folder
ID, template sheet ID) to point at your own copies. Only one keyword can be researched
per run; enter it in the Main Keyword sheet row before triggering.

## Usage

Set the Main Keyword sheet's single row to the keyword, location, language, and result
limit you want, then run the workflow manually. A new folder and results sheet appear
in Google Drive a few seconds to a couple of minutes later (DataForSEO's live
endpoints can be slow at high result limits), populated across seven tabs.

## Challenges

- **Six parallel unmonitored API calls, no retry logic.** If any of the six
  DataForSEO HTTP Request nodes times out or DataForSEO rate-limits the account, that
  branch simply fails; nothing in the workflow retries, backs off, or flags a partial
  result, so a partial research sheet can look complete when it isn't.
- **Duplicate endpoint used for two "different" result types.** `HTTP Keyword
  Suggestions` and `HTTP Keyword Ideas` call the exact same DataForSEO endpoint
  (`keyword_suggestions/live`) with identical parameters; the workflow just processes
  the same response twice into two different sheet tabs. This is a real limitation of
  the purchased template, not a deliberate design choice made here, and it means the
  "Keyword Ideas" sheet doesn't actually contain a distinct data set from "Keyword
  Suggestions."
- **Result limit affects API cost directly, with no cost guardrail.** The per-endpoint
  `limit` value is read straight from the sheet row with no upper bound check;
  DataForSEO bills per request/row, so an accidentally large limit runs up cost with
  no workflow-level warning.
- **Sheet IDs are hardcoded per node.** Every Google Sheets node references a specific
  spreadsheet ID for its target tab; changing which results sheet a run writes to
  means editing several nodes individually rather than one shared setting.
- **Single-keyword-per-run design doesn't batch.** Because the trigger reads one fixed
  row from the Main Keyword sheet, researching ten keywords means ten manual runs with
  a sheet edit between each; there's no loop-over-rows step to batch a keyword list.

## What I learned

Reading a purchased/templated workflow closely enough to document its real data flow
surfaced a structural flaw that wouldn't be obvious from just running it: the
"Keyword Ideas" branch calls the identical endpoint as "Keyword Suggestions," so two
of the seven output tabs are functionally duplicates dressed up as different data.
That's the kind of thing template marketplaces don't advertise and only shows up when
you trace each HTTP node's URL and body rather than trusting the node's display name.

## What I'd do differently

I'd replace the duplicated `Keyword Ideas` call with an endpoint that actually returns
a distinct data set (DataForSEO has several keyword-idea endpoints that aren't
`keyword_suggestions`), add basic retry/error handling around each of the six parallel
HTTP calls so a partial failure is visible rather than silent, and add a loop-over-
rows step so a list of seed keywords can run unattended instead of one manual trigger
per keyword.
