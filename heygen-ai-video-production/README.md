# Heygen AI Video Production

## What it is

An n8n workflow that turns a script sitting in a Google Sheet into a captioned,
vertical AI-avatar video: it generates narration audio with ElevenLabs, feeds that
audio to HeyGen to produce an avatar video, crops the result from 16:9 to vertical
9:16 through an FFmpeg-as-a-service API, and sends the cropped video to Submagic to
add captions and B-roll. It chains five external APIs (Google Sheets, ElevenLabs,
HeyGen, an FFmpeg API, Submagic) into one pipeline.

Like its sibling `submagic-video-clip-generator`, this is a demo/sales-pitch export,
not confirmed production work. Its own sticky note ("Pipeline Info") is framed as a
feature list of "REAL API INTEGRATIONS" for presentation purposes, and lists a setup
checklist of API keys needed, which reads like pitch material rather than an
operator's runbook. I have not run this against live HeyGen, ElevenLabs, FFmpeg, or
Submagic accounts.

## Why it exists

Producing a short-form AI-avatar video normally means manually stitching together
several separate tools: a voice generator, an avatar video generator, a cropping
step for vertical platforms, and a captioning tool. This workflow chains all four
behind one Google Sheet, so adding a script to a row is meant to be the only manual
step.

## Features

- Reads all rows from a Google Sheet of video scripts and filters to only
  unprocessed ones.
- Generates narration audio from the script text using ElevenLabs.
- Uploads that audio to HeyGen and generates an avatar video from a fixed avatar id
  and the uploaded audio.
- Polls HeyGen every 10 seconds until the video is ready, then writes the raw HeyGen
  video URL back to the sheet.
- Downloads the finished video, uploads it to an FFmpeg API, and crops it from 16:9
  to a 607x1080 vertical frame.
- Sends the cropped video to Submagic to add auto-captions and B-roll, using a named
  caption template ("Hormozi 2").
- Polls Submagic every 10 seconds until captioning finishes.
- Has a branch ("Check If Video Exists") that skips voice/avatar generation entirely
  if a HeyGen video URL is already present on the row, going straight to the
  crop/caption steps instead. Useful for re-running just the formatting stage on a
  video that was already generated.

## Architecture

Node-by-node, in execution order:

1. **When clicking 'Test workflow'** (`manualTrigger`).
2. **1️⃣ Fetch All Scripts** (`googleSheets`): reads every row of the sheet.
3. **2️⃣ Filter Unprocessed** (`if`): keeps only rows where the `Final Video` column
   is empty.
4. **3️⃣ Loop Through Scripts** (`splitInBatches`): meant to process rows one at a
   time. See Challenges: nothing in this graph loops back into this node, so in
   practice it only ever processes a single batch.
5. **4️⃣ Prepare Avatar Data** (`set`): assigns a hardcoded `avatar_id`
   (`8361563f2c914ace8ed2d048cbde8a4e`, a specific HeyGen avatar) plus the script
   text, topic, and row number pulled from the sheet row.
6. **5️⃣ Check If Video Exists** (`if`): if the row's `Heygen Video` column is
   already filled in, skips straight to step 14 (FFmpeg prep); otherwise continues
   to voice generation.
7. **6️⃣ Generate AI Voice** (`@elevenlabs/n8n-nodes-elevenlabs.elevenLabs`, resource
   `speech`, model `eleven_flash_v2_5`): synthesizes narration audio from the script
   text.
8. **7️⃣ Upload Audio to HeyGen** (`httpRequest`, POST
   `upload.heygen.com/v1/asset`): uploads the generated audio.
9. **8️⃣ Create Avatar Video** (`httpRequest`, POST
   `api.heygen.com/v2/video/generate`): requests an avatar video using the fixed
   avatar id and the uploaded audio URL, 1920x1080, with captions enabled at the API
   level.
10. **9️⃣ Wait for Processing** (`wait`, 10 seconds).
11. **🔟 Check Video Status** (`httpRequest`, GET
    `api.heygen.com/v1/video_status.get`): polls HeyGen for the video id created in
    step 9.
12. **1️⃣1️⃣ Is Video Complete?** (`if`, checks `data.status == completed`): true
    branch continues to step 13; false branch loops back to step 10.
13. **1️⃣2️⃣ Save HeyGen URL** (`googleSheets`, update, matched by `row_number`):
    writes the finished HeyGen video URL into the `Heygen Video` column.
14. **1️⃣3️⃣ Prepare FFmpeg Upload** (`httpRequest`, POST
    `api.ffmpeg-api.com/file`): requests an upload URL from the FFmpeg API. Fed from
    both step 13 (normal path) and step 6's skip branch.
15. **1️⃣4️⃣ Download Video** (`httpRequest`, GET the `Heygen Video` URL, binary
    response): downloads the finished HeyGen video file.
16. **1️⃣5️⃣ Upload to FFmpeg** (`httpRequest`, PUT to the upload URL from step 14):
    uploads the video binary.
17. **1️⃣6️⃣ Crop to Vertical 9:16** (`httpRequest`, POST
    `api.ffmpeg-api.com/ffmpeg/process`, ffmpeg args `-vf crop=607:1080`): crops to
    vertical.
18. **1️⃣7️⃣ Add Captions & B-roll** (`httpRequest`, POST
    `api.submagic.co/v1/projects`): sends the cropped video's download URL to
    Submagic with `magicBrolls: true` and template `Hormozi 2`.
19. **1️⃣8️⃣ Wait for Submagic** (`wait`, 10 seconds).
20. **1️⃣9️⃣ Check Submagic Status** (`httpRequest`, GET
    `api.submagic.co/v1/projects/{id}`): polls Submagic.
21. **2️⃣0️⃣ Is Editing Complete?** (`if`, checks `status == completed`): false
    branch loops back to step 19. True branch connects to nothing.

### The pipeline does not write the final video back to the sheet

I traced the `connections` object specifically for this, since the workflow's own
sticky note claims the last step is "Update Tracking Sheet." The true branch of
"2️⃣0️⃣ Is Editing Complete?" is `[]`, an empty connection array. There is no node
downstream of it. No node anywhere in this graph writes to a `Final Video` column,
even though "2️⃣ Filter Unprocessed" reads exactly that column to decide which rows
still need processing. As exported, the pipeline generates and edits the video, then
dead-ends: once Submagic reports the video complete, nothing happens, and the sheet
is left with no record that the video is actually finished, no download link for it,
and no way for the filter step to ever mark that row done. This means re-running the
workflow would try to reprocess the same row indefinitely, since `Final Video` never
gets populated to satisfy the filter.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials needed after import (see `CREDENTIALS.md`): Google Sheets OAuth2,
ElevenLabs, and three separate HTTP Header Auth credentials for HeyGen, the FFmpeg
API, and Submagic. You also need to replace the `YOUR_SPREADSHEET_ID_HERE` and
`YOUR_VOICE_ID` placeholders, and either point "Prepare Avatar Data" at your own
HeyGen avatar id or keep the hardcoded one if it happens to be a valid avatar on
your account.

Your Google Sheet needs, at minimum, columns for Topics, Scripts, Heygen Video, and
Final Video.

## Usage

Add a row with a topic and script to the sheet, run the workflow manually. If it
worked as designed, narration, avatar video generation, cropping, and captioning
would run automatically. As exported, the last step (writing the finished video back
to the sheet) never happens, so you'd need to check the Submagic project directly
for the final download link, or add that write-back node yourself before relying on
this in practice.

## Challenges

- **The pipeline never writes the finished video back to the sheet.** Covered in
  detail above. This is the single biggest gap: the whole point of the "Final Video"
  column existing is defeated by no node ever setting it.
- **The batch loop is not actually wired to loop.** "3️⃣ Loop Through Scripts" is a
  `splitInBatches` node, which n8n normally uses by connecting a downstream node back
  into it so it advances to the next batch. Nothing in this graph's connections
  targets "3️⃣ Loop Through Scripts" as a destination. In practice this means only the
  first batch (by default, one row) from "Fetch All Scripts" is ever processed per
  run, regardless of how many unprocessed rows exist in the sheet.
- **Three different generic HTTP-auth credentials share the same auth type.** HeyGen,
  the FFmpeg API, and Submagic are all wired up as `genericCredentialType` /
  `httpHeaderAuth`, meaning n8n does not distinguish them by node type, only by
  whichever credential the person setting this up manually assigns to each node. It's
  easy to accidentally reuse or mismatch a credential across nodes that call
  different services.
- **No polling limit on either wait loop.** Both the HeyGen status loop (steps 10 to
  12) and the Submagic status loop (steps 19 to 21) can run forever if the respective
  API never reports `completed`. There's no maximum retry count or timeout on either.
- **The avatar id is hardcoded.** "4️⃣ Prepare Avatar Data" sets a fixed
  `avatar_id` value rather than reading it from the sheet or a parameter, so every
  video in a batch would use the same HeyGen avatar regardless of the script's
  topic, unless someone edits that node.
- **This is explicitly a demo/pitch export, not a verified run.** I did not execute
  this against any of the five live APIs it depends on; the analysis above is based
  entirely on reading the exported node graph and expressions.

## What I learned

Tracing a `connections` object node-by-node, rather than trusting a sticky note's
summary of "what the pipeline does," is the only reliable way to catch a workflow
that silently drops its own final step. The claimed feature list here ("Update
Tracking Sheet" as the last stage) simply isn't backed by any node in the actual
graph. It's also a good example of why `splitInBatches` needs an explicit loop-back
edge to function as a loop at all: without one, it just passes the first batch
through once, no matter what the node's name implies.

## What I'd do differently

I'd add the missing final Google Sheets update node so the `Final Video` column
actually gets written once Submagic reports completion, wire "3️⃣ Loop Through
Scripts" so it actually iterates over every unprocessed row instead of only the
first, and add retry ceilings to both polling loops. I'd also pull the avatar id
from the sheet row instead of hardcoding it, so different scripts could use
different avatars without editing the workflow.
