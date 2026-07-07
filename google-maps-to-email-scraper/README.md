# Google Maps to Email Scraper

## What it is

An n8n workflow that takes a list of search topics from a Google Sheet (for example "Calgary dentists"), scrapes Google Maps search results for the businesses that match, visits each business website it finds, pulls any email addresses out of the page HTML, and writes the results back to the same Google Sheet.

## Why it exists

The workflow reads topics from a sheet that also tracks a "Progress" column ("Incomplete" / "Completed"), which points to a plain use case: building a list of local business contacts for outreach, one search topic at a time, without paying for a dedicated Maps or email-finder API. Beyond that, the specific outreach campaign this was built for is not stated anywhere in the node graph, so I'm not going to guess at it.

## Features

- Reads pending search topics from a Google Sheet and marks each one processed once emails are found.
- Scrapes Google Maps search results directly over HTTP, with no Maps API key.
- Extracts business website URLs from the raw search results HTML and filters out Google's own domains.
- Deduplicates website URLs before visiting them.
- Visits each business website in small batches with a delay between requests, tolerating failed pages instead of stopping the run.
- Extracts email addresses from each site's HTML with a regex that excludes obvious image filenames.
- Deduplicates the extracted emails and writes them back as a single comma-separated string per topic.

## Architecture

Node types used (all `n8n-nodes-base`): `manualTrigger`, `googleSheets`, `filter`, `limit`, `code`, `set`, `httpRequest`, `splitInBatches`, `wait`, `splitOut`, `removeDuplicates`, `aggregate`.

Data flow, in order:

1. **When clicking 'Execute workflow'** (`manualTrigger`) starts the run manually; there is no schedule or webhook trigger in this workflow.
2. **Google Sheets** reads the "Search" sheet, which has `Topic` and `Progress` columns.
3. **Filter** keeps only rows where `Progress` equals `Incomplete`.
4. **Limit1** has no `maxItems` override, so it defaults to passing through a single item. In practice this means one run processes one topic row, not the whole backlog.
5. **Code** replaces spaces in the topic with `+` so it can go into a URL query string.
6. **Set Topic** stores the original topic text and the URL-encoded query on the item.
7. **Scrape Google Maps** (`httpRequest`) does a GET on `https://www.google.com/maps/search/<query>` with the full response body returned and certificate validation turned off.
8. **Extract URLs** (`code`) runs a regex over the raw response body to pull out every `http(s)://` URL it can find.
9. **Filter Google URLs** drops any URL containing `schema`, `google`, `gg`, or `gstatic`, which removes Google's own domains and structured-data noise, leaving (mostly) business websites.
10. **Remove Duplicates** dedupes that URL list for the current run.
11. **Loop Over Items** (`splitInBatches`, batch size 5) processes the website list in batches of five, with one output for "still looping" and one for "batch finished."
12. On the looping branch: **Scrape Site** fetches each website (following redirects, continuing past errors, retrying on failure), then **Wait** pauses one second before **Extract Emails** runs a regex over the page HTML, excluding matches that end in common image extensions (jpg, png, gif, etc.) so it doesn't pick up filenames that look like addresses.
13. On the "batch finished" branch: **Wait1** pauses, then **Filter Out Empties** drops any site where no email was found, **Split Out** turns each site's email array into individual items, and **Remove Duplicates1** dedupes emails across all sites scraped this run.
14. **Aggregate** collects the deduped emails back into a single array, and **Code** (named `Code1`) joins that array into one comma-separated string.
15. **Store Emails in Sheets** writes back to the same spreadsheet row (matched on the `Topic` column) with `Progress` set to `Completed` and `Emails` set to the joined string.

## Setup

1. In n8n, go to **Workflows > Import from File** and select `workflow.json`.
2. Create and attach a **Google Sheets OAuth2** credential to the two Google Sheets nodes ("Google Sheets" and "Store Emails in Sheets"). See `CREDENTIALS.md` for the full list.
3. Point the `documentId` and `sheetName` fields at your own spreadsheet. It needs at minimum a `Topic` column and a `Progress` column (values `Incomplete` / `Completed`); the workflow will add an `Emails` column when it writes results.
4. No Google Maps API key or scraping service (Apify or similar) is used. The workflow scrapes `google.com/maps/search` and target business sites directly with n8n's HTTP Request node. Scraping Google Maps this way is not something Google's terms of service condone, and this was not verified for reliability at any real volume, only reviewed at the node-graph level.

## Usage

Add topic rows to the sheet with `Progress = Incomplete`, then trigger the workflow manually (there is no automatic schedule). Each run advances one topic row to `Completed` with its scraped emails, since the `Limit1` node caps processing to one item per run. To work through a backlog of topics, the workflow needs to be run once per topic, or `Limit1` needs a `maxItems` override added.

## Challenges

- **Google Maps has no stable, documented HTML structure to scrape.** The workflow relies on a plain regex over the raw search results page to find URLs, with no structured parsing. This is not addressed with any resilience layer (no fallback, no schema detection); a markup change on Google's side would silently reduce or break URL extraction.
- **Rate limiting and IP blocking when visiting many business sites.** This is addressed directly: `Loop Over Items` processes sites in batches of 5, `Wait` pauses one second between each site's scrape and its email extraction, and `Scrape Site` has `retryOnFail` and `onError: continueRegularOutput` so a single failed site does not stop the run.
- **Many businesses don't publish an email on their site.** `Filter Out Empties` explicitly drops any site where the email regex found nothing, so the sheet only ever records topics with at least one email found. There is no fallback such as checking a contact page or "about" page.
- **Deduplication is only within a single run.** `Remove Duplicates` dedupes the website list and `Remove Duplicates1` dedupes the extracted emails, but both only operate on the current run's data. Nothing in the graph checks the sheet's existing `Emails` column before writing, so re-running the same topic later (if its `Progress` were reset to `Incomplete`) would re-scrape the same sites from scratch.
- **The URL and email extraction rules are hand-rolled and approximate.** The Google-domain filter is a fixed list of four substrings (`schema`, `google`, `gg`, `gstatic`), which will let through other Google-owned or CDN domains not on that list. The email regex excludes common image extensions to avoid matching filenames, but does no further validation (no MX lookup, no format check beyond the regex itself).
- **Only one topic is processed per manual run.** The `Limit1` node has no `maxItems` set, which n8n defaults to 1. Whether this was a deliberate throttle (to avoid scraping too much in one run) or a leftover test setting is not clear from the node graph itself.

## What I learned

- How to structure a two-stage n8n scrape pipeline: a first HTTP fetch to build a list of targets, then a `splitInBatches` loop that fetches each target individually with a delay, using the loop node's two outputs (still-looping vs batch-finished) to sequence the per-item work against the after-loop aggregation.
- Using `removeDuplicates` at two different points in a pipeline (once on URLs, once on the final extracted values) instead of trying to dedupe everything in one place.
- Using a Google Sheets `appendOrUpdate` operation matched on a key column (`Topic`) to make writing results idempotent, so reruns update the same row instead of appending new ones.
- Regex-based scraping is workable for a narrow, known page shape (a Maps search results page, a small business's homepage) but has no resilience built in beyond basic string matching.

## What I'd do differently

- Move the spreadsheet ID out of every node's hardcoded parameters and into one place (an n8n variable or a Set node at the top of the workflow), so pointing the workflow at a different sheet doesn't mean editing three separate nodes.
- Add a real cross-run dedup check, comparing candidate emails against what is already in the sheet before writing, instead of only deduping within a single run.
- Replace the raw-HTML Google Maps scrape with a maintained scraping service or API once the added cost is worth it, since a Maps layout change breaks the current regex approach with no warning.
- Make the `Limit1` (one topic per run) and the duplicate copy's extra `Limit` (ten sites per run) explicit, named, and documented, instead of leaving them as bare default or magic-number nodes, so it's clear whether they're deliberate throttles or test leftovers.
- Add minimal email validation (format check beyond the regex, maybe a duplicate-domain check) before writing results, since the current filter only excludes image-file matches.

## Note on the duplicate workflow file

The source n8n backup contained two copies of this workflow. `workflow.json` is the primary copy (named "Google Maps to Email Scraper with Google Sheets Export", most recently updated). `workflow-duplicate.json` is a second copy from the same backup (named "...copy" in n8n) that is functionally almost identical but has two real differences worth keeping on record:

- It adds four sticky-note nodes that document each stage of the pipeline in plain language.
- It inserts an extra `Limit` node (`maxItems: 10`) between the URL dedup step and the per-site scraping loop, capping each run to at most 10 business sites instead of the unlimited list the primary copy would process.

Both copies have had their Google Sheet document ID and the personal email address embedded in the source file's project metadata replaced with placeholders.
