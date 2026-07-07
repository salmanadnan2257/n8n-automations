# Instagram Reel Analyzer + Scripts Generator

## Note on scope

Two sibling variants of this workflow were also approved for this portfolio pass: "IG
Reel Analyzer - Demo" (id `6lnvLtpmZLby0aSv`) and "Main - Instagram Reels Analyzer" (id
`6O6pQENqapJ9tsxG`). Neither has accessible source anywhere checked: not in the n8n
backup export used to build this project, not on disk, and the MCP tool used to fetch
workflows directly from the live n8n instance is disabled for both of those ids. This
folder is built from the one workflow that was recoverable, "Instagram Reel Analyzer +
Scripts Generator" (id `sgMmmCzemVYfaE93`). What the two missing variants actually
contain, whether they differ in scraper, model, or output format, is not stated here
because it isn't known. Including them is possible once the owner has direct access to
the live n8n instance to export them.

## What it is

An n8n workflow that takes an Instagram username and a reel count from a form, scrapes
that account's reels through Apify, converts each reel's video to audio and transcribes
it with OpenAI, logs the reel's stats and transcript to a Google Sheet, then runs an LLM
agent over that data to write a performance breakdown and stores that breakdown in a
second sheet tab.

## Why it exists

The node graph is built around a single question: what made a specific reel perform the
way it did, and what should change next time. It scrapes real engagement numbers (views,
likes, comments) alongside the reel's actual spoken content (via transcription) and
caption, then hands all of that to an LLM prompted explicitly as "my content strategist"
to produce next-step recommendations. This points to a content-creator or social media
manager use case: reviewing recent reels account by account and getting written notes
on what to do differently, without manually watching each video and cross-referencing
its stats by hand.

## Features

- Takes an Instagram username and a reel count through an n8n form, so a run can be
  started without touching the workflow itself.
- Scrapes the account's reels through Apify's Instagram Reel Scraper actor in one
  synchronous HTTP call.
- Converts each scraped reel's video to an MP3 through CloudConvert, then transcribes it
  with OpenAI's audio transcription.
- Logs every reel's account, transcript, caption, views, likes, comments, and video URL
  to a Google Sheet as a running record.
- Runs an LLM agent (Google Gemini) over each reel's stats, transcript, and caption to
  generate a written performance analysis and improvement suggestions.
- Appends each generated analysis to a second sheet tab, keeping raw data and generated
  insights separate.

## Architecture

Node types used: `n8n-nodes-base.formTrigger`, `n8n-nodes-base.httpRequest` (x2),
`@n8n/n8n-nodes-langchain.openAi` (audio transcription), `n8n-nodes-base.googleSheets`
(x2), `@n8n/n8n-nodes-langchain.agent`, `@n8n/n8n-nodes-langchain.lmChatGoogleGemini`.

Data flow, in order:

1. **On form submission1** (`formTrigger`) collects two fields: "Instagram Usernames"
   (text, placeholder `@ahmedd`) and "How many reels would you like scraped" (number).
   There is no schedule or webhook trigger, only manual form submission.
2. **Extract Reels** (`httpRequest`) POSTs to Apify's
   `apify~instagram-reel-scraper` actor's `run-sync-get-dataset-items` endpoint, passing
   the requested `resultsLimit` and `username` from the form fields as a JSON body. The
   Apify API token is passed as a URL query parameter.
3. **Get Video** (`httpRequest`) POSTs a three-step job to CloudConvert
   (`sync.api.cloudconvert.com/v2/jobs`): import the reel's video from its URL, convert
   it from `mp4` to `mp3`, and export the result as a URL. Authenticated with a bearer
   token in the request header.
4. **Video -> Text** (`@n8n/n8n-nodes-langchain.openAi`, resource `audio`, operation
   `transcribe`) transcribes the converted MP3 with OpenAI.
5. **Store Video's Data** (`googleSheets`, operation `append`) writes one row per reel to
   the "Instagram Content Analyzer" spreadsheet's first sheet, pulling `Account` and
   `Instagram Usernames` from the original form submission, `Transcript` from the
   transcription output, and `Caption`, `Views` (`videoPlayCount`), `Likes`
   (`likesCount`), `Comments` (`commentsCount`), and `Video` (`url`) from the Apify scrape
   result.
6. **Generate Insights** (`@n8n/n8n-nodes-langchain.agent`) receives the just-written
   row's `Views`, `Likes`, `Comments`, `Transcript`, and `Caption` in a fixed prompt
   template ("You are my content strategist. take this data and tell me what we can do
   better for the video"), using **Google Gemini Chat Model**
   (`gemini-2.0-flash-lite-001`) as its language model.
7. **Store Insights** (`googleSheets`, operation `append`) writes the agent's `output`
   text to the `Breakdown` column of the same spreadsheet's "Insights" tab.

One thing not resolvable from the JSON alone: the "Generate Insights" node reads
`$json.Views`, `$json.Likes`, etc, which are the column names written by the immediately
preceding "Store Video's Data" node, not the httpRequest node's raw field names. This
only works because the Google Sheets append node's output item carries forward the
values it just wrote under those column headers; the workflow depends on that pass-
through behavior rather than referencing "Extract Reels" or "Video -> Text" directly at
this step.

## Setup

1. In n8n, go to **Workflows > Import from File** and select
   `instagram-reel-analyzer.json`.
2. Create and attach the following credentials (see `CREDENTIALS.md` for the full list):
   an Apify account and API token, a CloudConvert account and API token, an OpenAI API
   credential (for audio transcription), a Google Gemini (Google PaLM API) credential,
   and a Google Sheets OAuth2 credential attached to both Google Sheets nodes.
3. Replace `YOUR_APIFY_API_TOKEN_HERE` in the "Extract Reels" node's URL with a real
   Apify API token.
4. Replace `YOUR_CLOUDCONVERT_API_TOKEN_HERE` in the "Get Video" node's Authorization
   header with a real CloudConvert API token.
5. Point the `documentId` fields (currently `YOUR_SHEET_ID_HERE`) in "Store Video's
   Data" and "Store Insights" at your own spreadsheet. It needs a first sheet with
   `Account`, `Transcript`, `Caption`, `Views`, `Likes`, `Comments`, `Video` columns, and
   a second tab named "Insights" with a `Breakdown` column.

## Usage

Submit the form with an Instagram username and the number of reels to scrape. The
workflow scrapes that many of the account's recent reels in one Apify call, then
processes them through the video-to-transcript-to-insight chain. Nothing in the node
graph loops explicitly over multiple scraped reels; how Apify's dataset-items response
(likely an array of reels) flows one item at a time through the rest of the chain
depends on n8n's default per-item execution, which is standard behavior but was not
run and observed here to confirm each reel individually reaches "Get Video" through
"Store Insights".

## Challenges

- **Chaining three paid external services (Apify, CloudConvert, OpenAI) in sequence
  with no error handling between them.** Nothing in the node graph adds an `onError` or
  `retryOnFail` setting to "Extract Reels", "Get Video", or "Video -> Text". A single
  failure anywhere in that chain (a private account, a deleted reel, a CloudConvert
  quota limit) stops the run with no visible fallback or partial-progress path.
- **Video-to-audio conversion depends entirely on CloudConvert's job being synchronous
  and complete by the time the next node runs.** The `"redirect": true` flag on the
  CloudConvert job body suggests the intent is to follow the job through to a completed
  file URL in one request, but this only works if the conversion finishes within
  whatever timeout the `httpRequest` node allows; a slow conversion has no separate
  polling or wait step in this graph.
- **The reused hardcoded spreadsheet ID appears in two separate nodes.** "Store Video's
  Data" and "Store Insights" both hardcode the same document ID. Pointing this workflow
  at a different sheet means editing both nodes individually; nothing centralizes that
  value.
- **The Apify API token is passed as a URL query string parameter rather than a header.**
  This means the token appears in plaintext in n8n's execution logs and history for
  every run, wherever request URLs get logged, not just where credentials are stored.
- **The "Generate Insights" prompt is a single fixed instruction with no structured
  output format.** The agent is told to "tell me what we can do better for the video" in
  free text; there's no schema, scoring rubric, or field breakdown enforced, so the
  "Breakdown" column in the Insights sheet holds whatever prose shape the model chose to
  return that run, which will vary run to run.
- **The workflow reads `Views`, `Likes`, `Comments` from the just-appended sheet row
  instead of directly from the Apify response.** This makes "Generate Insights" and
  "Store Insights" implicitly dependent on the Google Sheets append node returning the
  written values in its output item; if that node's behavior changed (or the append
  failed silently), the insight generation step would break without an obvious cause
  upstream.

## What I learned

- How n8n chains a scrape (Apify) through a media conversion service (CloudConvert) into
  a transcription step (OpenAI's audio resource) as three separate HTTP-shaped nodes
  rather than one combined operation, and how each node's output field names become the
  input references for the next.
- Google Sheets append nodes in n8n pass their own written values forward in the output
  item, which lets a later node reference the sheet's column names (`$json.Views`)
  instead of the original API's field names (`videoPlayCount`), even without an explicit
  read-back from the sheet.
- Separating raw data storage (one sheet tab) from generated analysis (a second tab) is
  a workable way to make one Google Sheet function as both a data table and an ongoing
  content-strategy log.

## What I'd do differently

- Add `retryOnFail` and explicit `onError` handling to "Extract Reels", "Get Video", and
  "Video -> Text", since a chain of three paid external API calls with no error handling
  means one failed call (a private profile, a rate limit, a conversion timeout) silently
  kills the whole run.
- Move the Apify token out of the URL query string and into a header, or better, into an
  n8n credential type, so it stops showing up in plaintext anywhere n8n logs request
  URLs.
- Centralize the spreadsheet ID in one place (a Set node or workflow variable at the top
  of the graph) instead of duplicating it across "Store Video's Data" and "Store
  Insights".
- Give the "Generate Insights" prompt an explicit output structure (a short rubric: hook,
  pacing, caption fit, call to action) instead of one open-ended instruction, so the
  "Breakdown" column holds comparable output across runs instead of free-form prose that
  varies in shape and length every time.
- Add a wait or polling step around the CloudConvert job instead of assuming the
  synchronous request always returns a finished file URL before the next node runs.
