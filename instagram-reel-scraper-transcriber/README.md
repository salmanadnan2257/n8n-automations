# Instagram Reel Scraper and Transcriber

## What it is

A scheduled n8n workflow that scrapes new Instagram Reels from a fixed list of
accounts through Apify, filters out reels already logged, transcribes the new ones
with Whisper, has GPT-4o decide whether the content is about a tool or technology
worth covering, pulls supporting facts on that tool from Perplexity, and writes a new
short-form video script from all of it. Everything gets logged to a Google Sheet.

## Why it exists

Inferred from the node graph: a content-research pipeline for an AI/automation
Instagram account. Rather than manually scrolling competitor and creator accounts
looking for tool mentions worth turning into a video, this pulls their new Reels on a
schedule, transcribes them, and has an LLM flag anything tool-related and draft a
fresh script based on it. The workflow's own metadata does not state this goal
directly; this is the plausible read from what the twelve nodes actually do together.

## Features

- Runs on a daily schedule against a fixed list of 14 Instagram accounts.
- Scrapes each account's recent Reels via an Apify actor in one synchronous HTTP call.
- Checks a Google Sheet for reels already logged and drops anything already seen
  before continuing.
- Downloads and transcribes new reels' audio with Whisper.
- Uses GPT-4o to decide if a transcript is about a tool or technology worth covering,
  and if so, extracts the tool names, a step-by-step usage guide, and a suggestion for
  making it into better content.
- Looks up extra facts about the identified tool via the Perplexity API.
- Writes a new ~100-word video script combining the transcript, the extracted
  step-by-step guide, the Perplexity facts, and the improvement suggestion.
- Logs every new reel and its scraped/generated transcripts back to the sheet.

## Architecture

Twelve nodes, run in one continuous chain from a schedule trigger:

1. **Schedule Trigger** (`n8n-nodes-base.scheduleTrigger`): fires once daily at 6 AM.
2. **Run Actor Synchronously** (`n8n-nodes-base.httpRequest`): POSTs to an Apify actor
   endpoint (`run-sync-get-dataset-items`) with a hardcoded JSON body listing 14
   Instagram usernames to scrape and a `resultsLimit` of 5 results per run, using a
   Bearer token in the Authorization header.
3. **Limit** (`n8n-nodes-base.limit`): keeps only the last 2 items from whatever the
   actor call returned, across the whole batch, not per account.
4. **Search for Entries** (`n8n-nodes-base.googleSheets`, lookup by `id`): checks the
   "Instagram Reel Database" sheet for rows whose `id` matches the incoming reels.
5. **Drop Duplicates** (`n8n-nodes-base.merge`, mode `combine`, `joinMode:
   keepNonMatches`, matched on `id`): combines the lookup results with the raw scraped
   items and keeps only the reels that were not already found in the sheet, dropping
   ones already logged.
6. **Add Entries** (`n8n-nodes-base.googleSheets`, `append`): writes each new reel's
   id, timestamp, shortCode, caption, hashtags, url, comment/like/view/play counts,
   owner username, and video duration into the sheet as a new row.
7. **Download Video** (`n8n-nodes-base.httpRequest`): fetches the reel's raw video file
   from its scraped `videoUrl`.
8. **Transcribe Video** (`@n8n/n8n-nodes-langchain.openAi`, resource `audio`,
   operation `transcribe`): runs the downloaded video's audio through Whisper to get a
   text transcript.
9. **Filter & Generate Suggestions** (`@n8n/n8n-nodes-langchain.openAi`, GPT-4o, JSON
   output mode): reads the transcript and decides (`verdict: true/false`) whether it
   covers a tool, technology, or AI topic; if true, it also returns the tool names, a
   step-by-step usage guide, a content-improvement suggestion, and a short
   `searchPrompt` string for the next step.
10. **Search Perplexity** (`n8n-nodes-base.httpRequest`, POST to
    `api.perplexity.ai/chat/completions`, model `sonar-pro`): asks for three
    interesting facts about whatever `searchPrompt` came out of the previous step,
    authenticated with a Bearer token header. This node runs unconditionally; nothing
    checks the previous step's `verdict` field before calling it.
11. **Write New Script** (`@n8n/n8n-nodes-langchain.openAi`, GPT-4o, JSON output mode,
    temperature 0.7): combines the tool names, the raw transcript, the Perplexity
    facts, the step-by-step guide, and the improvement suggestion into a new ~100-word
    script ending in a call to action ("comment [keyword] and I'll send it to your
    DMs").
12. **Update Entries** (`n8n-nodes-base.googleSheets`, `update`, matched on `id` from
    the earlier "Add Entries" item): writes the raw Whisper transcript and the new
    generated script back into the same row created in step 6.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create and attach credentials for:
   - **Google Sheets OAuth2**: used by Search for Entries, Add Entries, and Update
     Entries, all pointed at the same "Instagram Reel Database" spreadsheet ID in the
     export. Point these at your own sheet instead, with matching columns.
   - **OpenAI API**: used by Transcribe Video, Filter & Generate Suggestions, and
     Write New Script.
   - **Apify API token**: the Run Actor Synchronously node authenticates with a plain
     `Authorization: Bearer ...` header rather than an n8n credential, so the token
     has to be pasted into that header field directly.
   - **Perplexity API key**: same pattern, a manual Bearer header on the Search
     Perplexity node rather than an n8n credential.
3. Update the hardcoded list of 14 Instagram usernames in the Run Actor Synchronously
   node's JSON body to whichever accounts you actually want monitored.
4. Point the Google Sheets nodes at your own spreadsheet (create one with matching
   column headers first: id, timestamp, shortCode, caption, hashtags, url,
   commentsCount, firstComment, displayUrl, videoUrl, likesCount, videoViewCount,
   videoPlayCount, username, videoDuration, scrapedTranscript, newTranscript).
5. Activate the workflow. In the export, `active` is set to `true`, so it will start
   running on its 6 AM schedule as soon as credentials are attached.

A live Perplexity API key was found hardcoded in the Search Perplexity node in the
original export. It has been replaced with a placeholder in this copy; if that key is
still active anywhere, it should be rotated.

See `CREDENTIALS.md` for the full list of what each node needs.

## Usage

Once credentials and the account list are set, the workflow runs itself daily. New
reels from the configured accounts get scraped, deduplicated against the sheet,
transcribed, evaluated for tool-related content, researched further, and turned into a
draft script, all logged as new or updated rows in the connected sheet.

## Challenges

- **The Limit node caps the whole batch, not per account.** `maxItems: 2` keeps only
  the last 2 items from the entire Apify response, regardless of how many of the 14
  accounts posted something new that day. On a day where several accounts post, most
  of that day's new reels are dropped before they ever reach the duplicate check, with
  no queue or later pass to pick them up.
- **No branch on the filter's verdict.** Filter & Generate Suggestions produces a
  `verdict` field meant to gate whether a reel is worth covering, but there is no IF or
  Switch node reading it. Search Perplexity and Write New Script run on every reel
  regardless of verdict, so a reel judged irrelevant still produces a script, built
  from mostly empty fields.
- **No error handling around the scrape-to-transcript chain.** Apify's synchronous
  actor call, the video download, and the Whisper transcription are all unprotected: a
  slow or failing actor run, an expired or missing `videoUrl` (carousel posts and
  photo posts would not have one), or an oversized audio file would fail the run with
  no retry, fallback, or notification.
- **Duplicate detection is entirely dependent on Apify's own `id` field.** If the
  actor's output schema changes what it returns as `id` between versions, or a reel
  gets reprocessed under a different identifier, the dedup step (`Drop Duplicates`)
  would either silently reprocess an already-logged reel or, less likely, wrongly
  treat a genuinely new reel as a duplicate.
- **Transcription errors propagate uncorrected.** The final script is built from three
  chained LLM calls, each trusting the previous step's output completely. If Whisper
  mis-transcribes background music, multiple speakers, or heavy accents, that error
  flows into the tool-filter step and the final script with no human review
  checkpoint anywhere in the graph.
- **Manual header credentials instead of n8n's credential store.** Both the Apify
  token and the Perplexity key are pasted directly into HTTP Request header
  parameters rather than stored as reusable, revocable n8n credentials, which is also
  why a live key ended up committed to the original export in the first place.

## What I learned

- Apify's `run-sync-get-dataset-items` endpoint returns actor output directly to the
  calling HTTP node, which avoids a separate poll-for-completion step that async actor
  runs would need.
- A practical n8n dedup pattern: look up existing rows by a matching field (Search for
  Entries), then Merge in `combine` mode with `joinMode: keepNonMatches` against the
  raw incoming batch, which keeps only the items that were not already found, no
  external dedup service required.
- Chaining multiple JSON-mode LLM calls, each referencing an earlier node's output by
  name (`$('NodeName')`), is a workable way to build a multi-stage content pipeline
  entirely inside one workflow.
- A workflow can look complete on the canvas while a decision field one node produces
  (like `verdict`) is quietly never checked by anything downstream; that only shows up
  by tracing the actual connections, not by reading the prompt text.

## What I'd do differently

- Remove or rework the Limit node so it caps per-account results (or processes the
  full batch across more frequent runs) instead of dropping most of a busy day's new
  reels.
- Add an IF node right after Filter & Generate Suggestions to end the branch when
  `verdict` is false, instead of running Perplexity and script generation on
  irrelevant content.
- Wrap the Apify call, video download, and transcription in error handling, so a
  single bad reel does not silently produce a broken row (or, depending on n8n's
  failure settings, halt the whole run).
- Move the Apify token and Perplexity key into n8n's credential store (HTTP Header
  Auth credential type) instead of typing them into request headers directly, which
  would have prevented the live key exposure found in the original export.
- Add a lightweight review step, even a Slack or email notification with the draft
  script attached, before treating the generated script as finished content.
