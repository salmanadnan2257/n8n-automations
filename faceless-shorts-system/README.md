# Faceless Shorts System

## What it is

An n8n workflow that pulls a short-video idea from a Google Sheet, generates AI images
of an animal in a chosen style, turns those images into short video clips, generates a
matching ambient sound track, renders everything into a finished vertical short with
Creatomate, uploads it to YouTube as unlisted, and emails a notification that the video
is ready for review.

## Why it exists

This workflow was pulled from a folder named "NATE HERK" inside the source repository,
which strongly suggests it originates from a public creator or course (Nate Herk runs
an AI automation channel/course) rather than being an original in-house design. The
workflow file itself carries a sticky note reading "Nate Herk | AI Automation", which
confirms the same thing directly from the source. I did not build the original
concept or node graph; what's documented here is a read-through of an existing
automation, exported, secret-scrubbed, and written up for the portfolio as an example
of a multi-stage, multi-API n8n pipeline. I have not run this workflow end to end
myself, so behavior described below is based on reading the node graph and its
parameters, not on an observed run.

## Features

- Pulls one video idea (four animal names plus a visual style) from a row in a Google
  Sheet.
- Uses GPT-4o (via an n8n langchain agent) to turn each animal and style into a
  detailed image-generation prompt.
- Generates four still images with a Flux model through PiAPI.
- Converts each still image into a short video clip via Runway's image-to-video API
  (a disabled alternate branch does the same with Kling through PiAPI instead).
- Uses Gemini 2.0 Flash (via a second langchain agent) to write a one-to-two sentence
  ambient sound prompt matching the chosen style.
- Generates an ambient audio track from that prompt with ElevenLabs' sound-generation
  endpoint, uploads it to Google Drive, and makes it link-shareable.
- Renders the four video clips, the audio track, and the four animal names into a
  single vertical short using a Creatomate template.
- Uploads the rendered short to YouTube as an unlisted video.
- Writes status back to the sheet (video created, then published, with the final
  link) and emails a notification when a new short is ready for approval.

## Architecture

Trigger: a `scheduleTrigger` node (interval-based) and a `manualTrigger` node
("When clicking 'Test workflow'") both feed the same path, so the workflow can run on
a schedule or be fired by hand.

Pipeline, in order:

1. **Grab Idea** (`googleSheets`, read) pulls one row from the ideas sheet.
2. **Set Animals** (`set`) packages the row's four animal columns into an array and
   carries the `style` field forward.
3. **Split Out** (`splitOut`) turns the four-animal array into four separate items so
   each animal gets its own image prompt.
4. **Image Prompt Agent** (`@n8n/n8n-nodes-langchain.agent`, backed by **GPT 4o**,
   `@n8n/n8n-nodes-langchain.lmChatOpenAi`) writes a detailed Flux-style image prompt
   per animal and style, with a system prompt that enforces family-friendly output and
   bans violent or weapon references.
5. **Remove \n** (`code`) strips stray newline characters from the agent's raw text
   output before it's used in an HTTP JSON body.
6. **Set Prompts** (`set`) stores the cleaned prompt string.
7. **Generate Image** (`httpRequest`, POST to `api.piapi.ai/api/v1/task`) submits a
   `Qubico/flux1-dev` text-to-image job.
8. **90 seconds** (`wait`) is a fixed pause to give the image job time to finish,
   followed by **Get Images** (`httpRequest`, GET) polling the task by ID once.
9. **Generate Videos** (`httpRequest`, POST to Runway's
   `api.dev.runwayml.com/v1/image_to_video`, model `gen3a_turbo`) turns each generated
   still into a five-second video clip. A **2 minutes** `wait` node then pauses before
   **Get Videos** (`httpRequest`, GET) polls the Runway task for the finished clip.
   A disabled alternate branch (**Generate Videos (Kling)**, **8 Minutes** wait,
   **Get Videos (Kling)**, **Split Out Parts (Kling)**) does the same job through
   PiAPI's Kling model instead of Runway; it's present in the graph but switched off.
10. **Get Videos** output fans out to two paths: **Limit** (`limit`, caps to one item)
    feeding **Video Status** (`googleSheets`, update: sets `videoStatus` to
    "Created"), and the same output feeding into **Merge** for the render step later.
11. In parallel, **Sound Agent** (`langchain.agent`, backed by **Flash 2.0**,
    `lmChatGoogleGemini`, model `gemini-2.0-flash`) writes a short ambient sound
    description from the row's `style` field. **Set Audio** (`set`) trims it, and
    **Generate Audio** (`httpRequest`, POST to
    `api.elevenlabs.io/v1/sound-generation`) generates a 20-second ambient audio clip
    from that text. This is a sound-effect/ambiance generator, not a text-to-speech
    narration voice, so the workflow does not narrate a spoken script anywhere.
12. **Upload to Drive** (`googleDrive`, upload) stores the generated audio as an mp3,
    then **Share File** (`googleDrive`, share) makes it link-viewable by anyone with
    the link, since Creatomate needs a public URL to pull the audio from.
13. **Merge** (`merge`, combine all) joins the video-clip branch and the shared-audio
    branch into one item, and **Split Out Parts** (`code`) flattens the merged output
    array into a plain list of clip URLs.
14. **Render Video** (`httpRequest`, POST to `api.creatomate.com/v1/renders`) submits
    a render job against a fixed Creatomate template ID, mapping the four video clips,
    the Drive audio link, and the four animal names into the template's slots.
15. **25 Seconds** (`wait`) pauses for the render, then **Download Video**
    (`httpRequest`, GET) fetches the rendered file by URL.
16. **Upload Video** (`youTube`, upload) posts the downloaded short to YouTube as
    unlisted, using the sheet row's title and caption as the video title and
    description.
17. **Update Sheet** (`googleSheets`, update) writes `publishStatus` to "Processed"
    and stores the video link back on the same row.
18. **Notification** (`gmail`) sends a plain-text email that a new short is ready for
    approval, though the email body has a `[Name]` placeholder and no actual review
    link filled in.

## Setup

1. In n8n: **Workflows** menu > **Import from File**, and select `workflow.json` from
   this folder.
2. Create and attach these credentials in n8n before running (all reference
   placeholders only in the exported file, real values are supplied by whoever
   configures the n8n instance):
   - Google Sheets OAuth2 (read/update the ideas sheet)
   - Google Drive OAuth2 (upload and share the generated audio file)
   - Google Gemini (PaLM) API (Gemini 2.0 Flash, used by the Sound Agent)
   - OpenAI API (GPT-4o, used by the Image Prompt Agent)
   - YouTube OAuth2 (video upload)
   - Gmail OAuth2 (notification email)
   - An API key/header credential for PiAPI (image generation, and the disabled Kling
     video branch)
3. Several HTTP Request nodes call paid third-party APIs but, as exported, carry no
   n8n credential or auth header at all: **Generate Image**/**Get Images** (PiAPI),
   **Generate Videos**/**Get Videos** (Runway), and **Generate Audio** (ElevenLabs).
   Only **Render Video** (Creatomate) shows where a key goes, and it's a placeholder
   `Bearer YOUR_API_KEY_HERE` in a header. Whoever imports this workflow has to add
   the missing authentication to those nodes themselves (Runway and ElevenLabs both
   expect an API key in a request header; PiAPI can use n8n's generic header-auth
   credential, matching the pattern already used on the disabled Kling node).
4. Point **Grab Idea**, **Video Status**, and **Update Sheet** at a real Google Sheet
   with the columns the workflow expects: `animal 1` through `animal 4`, `style`,
   `title`, `caption`, `videoStatus`, `publishStatus`, `videoLink`, and `row_number`.
5. Replace the Creatomate `template_id` in **Render Video** with a template you
   control, since the exported ID belongs to whoever built the original template and
   its slot names (`Video-1` through `Video-4`, `Audio-Track`, `Text-1` through
   `Text-4`) are specific to that template's layout.

## Usage

Run the workflow manually from the trigger node for a single test pass, or activate
the `scheduleTrigger` to have it pick a new row from the sheet and produce a short
automatically on whatever interval it's configured with. Each run consumes one row
from the ideas sheet and marks it processed so the next run picks up a fresh idea.

## Challenges

This section describes challenges inherent to this class of workflow (chaining
several paid generation APIs into one pipeline) and states plainly whether the actual
node graph addresses each one, based on reading it, not on a live run.

- **Fixed wait times instead of real polling.** The workflow uses flat `wait` nodes
  (90 seconds for images, 2 minutes for Runway video, 25 seconds for the Creatomate
  render) rather than a poll-until-ready loop. If a generation job takes longer than
  the fixed wait, the next node reads an incomplete or failed task and the pipeline
  keeps going with bad data. The graph does not address this: there's no retry, no
  status check before proceeding, and no branching on job failure anywhere in the
  chain.
- **No error handling across a long node chain.** None of the HTTP Request nodes have
  an "on error: continue" setting, an IF check on the response, or a fallback path
  visible in the exported JSON. A single failed API call (rate limit, timeout, bad
  prompt rejected by a content filter) stops the whole run with no cleanup of the
  sheet row's status.
- **Authentication left incomplete for several paid APIs.** As noted in Setup, the
  PiAPI, Runway, and ElevenLabs HTTP calls carry no credential or auth header in the
  exported file. That's a real gap, not a design choice: the workflow as exported
  cannot actually call these services until someone adds the missing keys.
- **Audio-video sync is templated, not computed.** The rendered audio track is a
  generic 20-second ambient bed dropped into a fixed Creatomate template slot; there's
  no node that measures clip length or narration timing to actually align audio to
  video content. This works because the format is a fixed four-clip template, not
  because the workflow solved timing generally.
- **Cost and rate limits are not managed.** Four image generations, four video
  generations, one sound generation, and one render happen on every single run with
  no batching control, no cost ceiling, and no check for API rate limits beyond the
  crude fixed waits. Every run against the schedule trigger burns through paid API
  calls with no guard.
- **Two parallel video-generation providers live in one graph.** Runway is active and
  PiAPI/Kling is present but disabled. Keeping both wired into the same workflow
  (rather than picking one) adds maintenance surface: any shared upstream node change
  has to be checked against two diverging downstream branches, one of which is dead
  code until someone re-enables it.

## What I learned

- Reading someone else's n8n export closely (node types, `typeVersion`, credential
  keys, and the actual JSON payloads sent to third-party HTTP APIs) is a useful way to
  reverse-engineer how a black-box "AI automation" product actually works under the
  hood: in this case, it's a chain of six or so paid HTTP APIs glued together with
  fixed-duration waits rather than anything more resilient.
- n8n's langchain agent nodes (`@n8n/n8n-nodes-langchain.agent`) separate the prompt
  logic from the model connection: the same agent node pattern is reused twice here
  (once with GPT-4o for image prompts, once with Gemini 2.0 Flash for sound prompts),
  each wired to its own `lmChat*` sub-node over an `ai_languageModel` connection
  rather than a plain `main` connection.
- n8n credentials (the `credentials: { someApi: { id, name } }` blocks) are just
  pointers into n8n's separate encrypted credential store, they never carry secret
  values themselves, which is different from the header-based auth on nodes like
  **Render Video**, where the actual bearer token has to be typed directly into the
  node's parameters and therefore ends up in the exported JSON if not scrubbed.

## What I'd do differently

- Replace every fixed `wait` node with an actual poll loop (wait, check status,
  branch on done/pending/failed, repeat with a max retry count) so the pipeline
  doesn't silently continue on a job that hasn't finished.
- Add explicit error branches after each external HTTP call so a single failed
  generation marks the sheet row as failed instead of leaving the workflow to either
  crash or continue with bad data.
- Pick one video-generation provider (Runway or Kling/PiAPI) and delete the other
  instead of carrying a second, disabled implementation in the same graph.
- Move the Creatomate bearer token and any other API keys called by raw HTTP Request
  nodes into n8n's credential store (generic header auth), the same way Google,
  OpenAI, and YouTube are already handled, instead of leaving a token pasted directly
  into node parameters.
- Add a genuine narration track (text-to-speech reading an actual script) since the
  current audio step only produces a generic ambient sound bed, not narration, despite
  the workflow's premise of producing a narrated short.
