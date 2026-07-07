# Submagic Video Clip Generator

## What it is

An n8n workflow that watches a Google Sheet for new YouTube video URLs, sends each one
to a clip-generation API (endpoint shaped like Submagic's `magic-clips` API), polls
until the clips are ready, and writes the resulting short clips (with virality scores
and download links) back into a second sheet.

This is a demo/sales-pitch export, not a workflow that was ever run against real
production traffic. Its own sticky notes make that explicit: one is literally titled
"Demo Script" with talking points for presenting the workflow live, another is a
"Configuration Checklist" of things to set up "Before Demo," and the polling node's
note admits "No infinite loop protection in this demo version." I'm keeping that
framing honest rather than presenting it as a finished production system.

## Why it exists

Turning a long-form YouTube video into short, postable clips normally means manually
scrubbing through footage to find the best moments. This workflow automates the
handoff to a clip-generation API: drop a YouTube URL in a spreadsheet, and clips with
virality scores land in another sheet a few minutes later, no manual video editing
step in between.

## Features

- Google Sheets trigger polls a "Video Queue" sheet every 60 seconds for new rows.
- Validates each row before processing (status must be `pending`, YouTube URL must be
  non-empty).
- Sends the URL to a clip-generation API requesting 3 clips per video.
- Writes an intermediate "processing" status with the API's project ID back to the
  sheet immediately, so a human watching the sheet gets fast feedback.
- Polls the API every 30 seconds until the job reports `completed`.
- Extracts per-clip metadata (title, duration, virality score, download URL) with a
  Code node and appends each clip as its own row in a "Generated Clips" sheet.
- Marks the original video row `completed` once all clips are saved.

## Architecture

Node-by-node, in execution order:

1. **New Video Added** (`googleSheetsTrigger`, event `rowAdded`, polling every
   minute): fires when a new row appears in the Video Queue sheet.
2. **Check If Needs Processing** (`if`): passes the row through only if `status`
   equals `pending` and `youtube_url` is not empty.
3. **Generate Clips** (`httpRequest`, POST to `api.submagic.co/api/v1/magic-clips`,
   `httpHeaderAuth`): sends the YouTube URL and requests 3 clips.
4. **Update Status** (`googleSheets`, update): writes `status=processing`, the
   returned `project_id`, and a timestamp back to the row, matched by `row_number`.
5. **Wait for Processing** (`wait`, 30 seconds): pauses before the first status
   check.
6. **Check Clip Status** (`httpRequest`, GET
   `api.submagic.co/api/v1/projects/{project_id}`): polls the job.
7. **Is Completed?** (`if`, checks `status == completed`): true branch continues to
   extraction; false branch loops back to step 5, repeating the wait/check cycle.
8. **Extract Clips** (`code`): reads the `magicClips` array from the API response and
   turns it into one item per clip, pulling `id`, `title`, `duration`,
   `viralityScores.total`, `downloadUrl`, and the source YouTube id.
9. **Save Clips to Sheet** (`googleSheets`, append): writes each clip as a new row in
   the "Generated Clips" sheet.
10. **Mark Complete** (`googleSheets`, update, matched by `project_id`): sets the
    original video row to `status=completed` with a clip count and timestamp.

The retry loop (steps 5 to 7) has no counter or maximum attempt limit anywhere in the
graph. If the clip API never returns `completed`, this loop runs forever.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials needed after import (see `CREDENTIALS.md` for details):

- Google Sheets OAuth2, for the trigger and all three Google Sheets write nodes.
- An HTTP Header Auth credential for the clip-generation API, since the "Generate
  Clips" and "Check Clip Status" nodes both use `genericCredentialType` /
  `httpHeaderAuth` without a header configured in the export; you supply the actual
  key name and value for whichever provider you point this at.

You also need to create two sheets before the first run: a "Video Queue" sheet with a
`status`/`youtube_url`/`project_id` structure, and a "Generated Clips" sheet for the
output rows. Update the placeholder `YOUR_SPREADSHEET_ID` values (they appear on four
nodes) and the `gid=CLIPS_SHEET_ID` placeholder on "Save Clips to Sheet" with your
real sheet ids.

## Usage

Activate the workflow, then add a row to the Video Queue sheet with `status=pending`
and a `youtube_url`. Within 60 seconds the trigger fires, and within a few minutes
(depending on how long the clip API takes) three rows appear in the Generated Clips
sheet and the original row flips to `completed`.

## Challenges

- **No infinite loop protection.** The workflow's own sticky note says this outright.
  If the clip API's job never reaches `completed` (a stuck job, an API outage, a
  malformed response), the Wait/Check/Is Completed loop runs indefinitely with no
  retry counter, no timeout, and no alerting. A production version needs a maximum
  attempt count (the note itself suggests 20 tries at 30 seconds each, about 10
  minutes) that routes to a failure/notification path instead of looping forever.
- **The HTTP auth is unconfigured.** Both API-calling nodes use a generic header-auth
  credential type with no header name filled in in the export. Anyone importing this
  has to know, from the target API's own docs, exactly which header the clip service
  expects (`X-API-Key`, `Authorization: Bearer`, etc); the workflow gives no hint.
- **Four separate spreadsheet-id placeholders to keep in sync.** `YOUR_SPREADSHEET_ID`
  appears independently on the trigger and three Google Sheets nodes, plus a separate
  sheet-gid placeholder for the clips sheet. Nothing enforces that all of these
  actually point at the same file; a typo in one node silently breaks that one step.
- **No handling for a source video with zero valid clips.** If the API returns an
  empty `magicClips` array (a video too short to clip, for instance), "Extract Clips"
  produces zero items, so "Save Clips to Sheet" runs on nothing, and the flow still
  reaches "Mark Complete" and reports `clips_generated: 0` as if that were a normal
  successful outcome, not a case worth flagging.
- **This is explicitly a demo build, not a verified production run.** I did not run
  this against a live Submagic account or a real Google Sheet; there's no execution
  history to confirm the calls succeed as written, only that the graph and expressions
  are internally consistent.

## What I learned

Reading a workflow's sticky notes is not optional context, it can be the single most
reliable source of truth about what the author actually knew was missing. Here, the
"no infinite loop protection" admission and the "Demo Script"/"Configuration
Checklist" notes told me more about the real maturity of this workflow than the node
graph alone would have. It's also a clean example of the "poll with a Wait + IF loop"
pattern in n8n, useful to recognize since it recurs across several of these video
production workflows (the sibling `heygen-ai-video-production` folder uses the same
shape twice).

## What I'd do differently

I'd add a retry counter to the polling loop with a hard ceiling, replace the generic
`httpHeaderAuth` placeholders with named credentials scoped to the actual provider so
the setup requirement is explicit rather than implicit, and add a branch after
"Extract Clips" that flags (rather than silently completes) a video that produced
zero clips.
