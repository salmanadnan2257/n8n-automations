# Auto Video Generator

## What it is

An n8n workflow that picks a random row from a Google Sheet of source videos,
generates a short "POV" style caption for it with an LLM, renders that caption as
text overlays onto the video through Creatomate, waits for the render to finish,
then uploads the finished video to Blotato and posts it to Instagram.

## Why it exists

Turning a batch of raw video clips into captioned, ready-to-post content is a
repetitive manual job: pick a clip, write a caption, render an overlay, wait, then
upload it to each platform. This workflow automates that whole chain from a single
manual trigger, so one run produces one finished, captioned, posted video.

## Features

- Reads video source rows (with a `video_url` field) from a Google Sheet.
- Picks one row at random per run via a small Code node.
- Generates a short "POV:" style motivational caption using an AI Agent node backed
  by Google's Gemini model, following a fixed template and character-length rules
  in its system prompt.
- Splits the generated caption into two overlay-friendly lines.
- Renders the video with the two text lines overlaid, via a Creatomate template.
- Waits 30 seconds, then polls Creatomate once for the render's status and output
  URL.
- Uploads the rendered video to Blotato's media endpoint.
- Posts the uploaded video to Instagram through Blotato's posts endpoint.

## Architecture

Twelve functional nodes (plus three sticky notes used purely as section labels in
the n8n canvas: "Step 1", "Step 2", "Step 3"):

```
When clicking 'Test workflow' (Manual Trigger)
  -> video_data_from_sheets (Google Sheets)
  -> pick_random (Code)
  -> generate_overlay_text (LangChain Agent, using Google Gemini Chat Model)
  -> split_text_for_overlay (Code)
  -> render_creatomate (HTTP Request -> Creatomate /v1/renders)
  -> Wait (30s)
  -> get_render_status (HTTP Request -> Creatomate /v1/renders/{id})
  -> set_blotato_ids (Set)
  -> ready_video_blotato (HTTP Request -> Blotato /v2/media)
  -> Edit Fields (Set)
  -> social_app_posts (HTTP Request -> Blotato /v2/posts)
```

- **video_data_from_sheets**: `n8n-nodes-base.googleSheets` node reading a fixed
  spreadsheet and `Sheet1`.
- **pick_random**: `n8n-nodes-base.code` node that picks one random item out of all
  rows returned by the sheet read.
- **generate_overlay_text**: `@n8n/n8n-nodes-langchain.agent` node with a system
  prompt instructing it to write a "POV:" caption under 90 characters, split into
  lines under 45 characters, no emojis or hashtags, aimed at a real estate niche.
  It's wired to **Google Gemini Chat Model**
  (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`, model
  `models/gemini-1.5-flash-8b-latest`) as its language model input.
- **split_text_for_overlay**: `n8n-nodes-base.code` node meant to take the agent's
  generated text and split it into `line1` and `line2` for the video overlay.
- **render_creatomate**: `n8n-nodes-base.httpRequest` node, POSTs to Creatomate's
  render endpoint with a fixed `template_id` and modifications that swap in the
  source video and the two overlay lines.
- **Wait**: `n8n-nodes-base.wait`, a fixed 30 second pause before checking the
  render.
- **get_render_status**: `n8n-nodes-base.httpRequest` node, GETs the render by ID
  from Creatomate to retrieve its status and output URL.
- **set_blotato_ids**: `n8n-nodes-base.set` node (raw JSON mode) that hardcodes a
  block of per-platform account/media IDs (instagram, youtube, tiktok, facebook,
  threads, twitter, linkedin, pinterest, bluesky).
- **ready_video_blotato**: `n8n-nodes-base.httpRequest` node, POSTs the rendered
  video's URL to Blotato's media endpoint so Blotato can host/serve it.
- **Edit Fields**: `n8n-nodes-base.set` node that assembles the Instagram account
  ID, the uploaded media URL, and a `captions` value pulled from the original sheet
  row into one item.
- **social_app_posts**: `n8n-nodes-base.httpRequest` node, POSTs to Blotato's posts
  endpoint to publish the video to Instagram.

## Setup

1. An n8n instance with the LangChain community nodes available (this workflow uses
   `@n8n/n8n-nodes-langchain.agent` and `.lmChatGoogleGemini`).
2. A Google Sheets credential attached to the `video_data_from_sheets` node, with
   access to a spreadsheet containing at least a `video_url` column and a
   `captions` column. The copied `workflow.json` does not include a credential
   reference on this node (the export simply doesn't carry one), so it has to be
   attached manually after import.
3. A Google Gemini API credential attached to the `Google Gemini Chat Model` node.
   Same as above, no credential reference is present in the exported JSON.
4. A Creatomate account and API key, added as a generic HTTP Header Auth credential
   in n8n and attached to both `render_creatomate` and `get_render_status`. A
   Creatomate template with two text layers (`Text-1`, `Text-2`) and one video
   layer (`Video-1`) matching the hardcoded `template_id` in the workflow.
5. A Blotato API key, added as a header value on the `ready_video_blotato` and
   `social_app_posts` nodes (`blotato-api-key` header). The copy in this repo has
   this replaced with `YOUR_BLOTATO_API_KEY_HERE`.
6. Blotato account/media IDs for whichever platforms you actually intend to post
   to, entered into the `set_blotato_ids` node in place of the placeholder numbers
   shipped in the sheet.
7. No `.env` file or environment variables are used. All configuration lives in
   node parameters and n8n credentials.

## Usage

Run the workflow manually from the n8n canvas (its only trigger is a Manual
Trigger). Each run: reads the sheet, picks one row at random, generates a caption,
renders the video with Creatomate, waits, checks the render, uploads it to
Blotato, and posts it to Instagram. There's no schedule trigger in this graph, so
running it repeatedly for a batch of videos means clicking "Test workflow" once
per video, or replacing the Manual Trigger with a Schedule Trigger.

## Challenges

1. **Three node references in expressions don't match the actual node names in
   this file.** `split_text_for_overlay`'s code reads
   `$node["Generate Overlay Text"].json.choices`, but the node that actually
   generates the caption is named `generate_overlay_text`. `render_creatomate`'s
   body reads `{{ $('Pick Random Template').item.json.video_url }}`, but the node
   that picks the row is named `pick_random`. `ready_video_blotato`'s body reads
   `{{ $('Get Render Status').item.json.url }}`, but that node is named
   `get_render_status`. n8n node name lookups in expressions are exact matches, so
   as saved, these three references would fail to resolve at runtime. This reads
   like the nodes were renamed after the expressions referencing them were
   written, and the expressions were never updated.
2. **The caption-splitting code expects an OpenAI-style completion shape that this
   graph doesn't produce.** `split_text_for_overlay` reads
   `choices[0].message.content`, which is the shape of a raw OpenAI chat
   completions API response. The node actually feeding it is a LangChain Agent
   node (`generate_overlay_text`), whose output in n8n is a different shape
   (typically an `output` field), not a `choices` array. Even with the naming
   mismatch above fixed, this node would still be reading a field that doesn't
   exist on the agent's output.
3. **The generated caption is computed but never actually posted.** `Edit Fields`
   pulls a `captions` value from the original sheet row (not the LLM-generated
   text) into the item, but `social_app_posts`'s request body hardcodes
   `"text": "hello"` as the post caption instead of referencing `captions` or the
   overlay text. As saved, every post goes out with the literal word "hello" as
   its caption regardless of what the agent generated or what's in the sheet.
4. **Built for multi-platform, wired for one.** `set_blotato_ids` hardcodes account
   IDs for nine platforms (instagram, youtube, tiktok, facebook, threads, twitter,
   linkedin, pinterest, bluesky), but only `social_app_posts` exists downstream,
   and it's hardcoded to `targetType: instagram`. Eight of the nine prepared IDs
   are read into the workflow's data but never used by any node.
5. **A fixed 30 second wait stands in for actually polling the render.** Creatomate
   renders don't have a guaranteed completion time; a fixed `Wait` node assumes the
   render always finishes within 30 seconds, then reads whatever status Creatomate
   returns at that point, whether or not the render actually completed. There's no
   loop or retry checking the status again if it isn't done yet.
6. **No error handling or empty-data checks anywhere in the graph.** There's no IF
   node checking that the sheet actually returned rows before `pick_random` runs,
   no check that Creatomate's render succeeded before `get_render_status` reads its
   output URL, and no check that Blotato's upload succeeded before posting. A
   failure at any step just produces malformed output for the next node instead of
   stopping the run cleanly.

## What I learned

Working through this file made the LangChain Agent node's wiring in n8n concrete:
the language model isn't a parameter on the agent node itself, it's a separate node
(`Google Gemini Chat Model` here) connected through a distinct `ai_languageModel`
connection type, separate from the regular `main` data connections. It also made
clear that Creatomate's render API is asynchronous: you submit a render and get an
ID back immediately, then have to poll a separate status endpoint for the actual
output URL, which is why this graph has a submit node, a wait, and a separate
status-check node instead of one call.

## What I'd do differently

I'd fix the three node name mismatches first, since as saved the workflow can't
actually run past the point where `split_text_for_overlay` looks up a node that
doesn't exist under that name. I'd replace the fixed 30 second wait with a small
loop that polls Creatomate's status endpoint until the render reports done or
failed, since a flat wait either wastes time on fast renders or gives up too early
on slow ones. I'd wire the actual generated caption (or the sheet's `captions`
field, whichever is intended) into `social_app_posts`'s body instead of the literal
string "hello," and either wire up the other eight platforms `set_blotato_ids`
prepares IDs for, or remove the unused ones so the workflow's data doesn't imply
more coverage than it delivers.
