# Presentation Generator Tool

## What it is

An n8n chat-triggered workflow that takes a presentation topic typed into an n8n chat
window and builds a Google Slides deck from it: an LLM plans a slide-by-slide outline
(title, subtitle, five-plus bullet points per slide), then a loop of Google Slides API
calls creates each slide with hand-crafted layout, backgrounds, and typography.

This is course-derived, not an original design: it comes from the paid course "Build a
Slide Deck Agent in n8n," and the workflow's internal name and sticky notes credit that
course's author. Per the terms this entry was approved under, the course author's name
is dropped from this project's folder name, title, and this document; the README below
describes the workflow by what it functionally does. The underlying JSON workflow
file itself still contains the original author's branding in its internal `name`
field, a `logo_name` value baked into the generated slide footer, and a course-promo
sticky note, since none of that is a secret or personal data, it's the course
provider's own public self-promotion inside their own template; only the public-facing
naming in this Portfolio (folder, title, this README) omits it.

## Why it exists

Turning a topic into a full slide deck by hand (writing content per slide, then
manually laying out title/subtitle/bullets/backgrounds in Google Slides) is repetitive.
This workflow automates both halves: the content outline via an LLM, and the visual
layout via direct Google Slides API batch-update calls with fixed styling.

## Features

- Chat-based intake: type a topic into n8n's built-in chat trigger and the workflow
  starts from there.
- Creates a new Google Slides presentation per run.
- LLM-generated outline: a fixed slide count (10, hardcoded) with a title, subtitle,
  and at least five bullet points per slide, returned as JSON.
- Loops over the generated slides one at a time (`Split In Batches`), building each
  slide with a raw Google Slides `batchUpdate` HTTP call: background fill, several
  decorative ellipse shapes with custom colors/opacity, a title text box, a subtitle
  text box, and a bulleted body text box, all with explicit font, size, and color
  styling.
- Two different slide-styling HTTP calls exist in the graph (`Google Slide BASIC
  Generation` and `Google_Slides_Create_Slide` with a more elaborate "HQ Style 1"
  layout plus a third alternate style block), representing visual-design iterations
  kept side by side rather than one final version replacing the others.
- A `Wait` node paces the loop between slide-creation calls, likely to avoid hitting
  the Google Slides API's per-second rate limit when generating many slides quickly.

## Architecture

Trigger: `When chat message received` (`@n8n/n8n-nodes-langchain.chatTrigger`).

1. `Google Slides` node creates a new presentation titled "AI Generated Slide Deck" and
   returns its `presentationId`, referenced by every later Slides API call.
2. `Total_Slides_To_Generate` (Set) fixes the slide count to 10.
3. `AI Agent` (`@n8n/n8n-nodes-langchain.agent`, backed by `OpenAI Chat Model` running
   `gpt-3.5-turbo`) receives the chat topic and the slide count, and returns a JSON
   array of slide objects (`title`, `subtitle`, `bullets`).
4. `Code` (JS) parses that JSON string into an actual array and emits one n8n item per
   slide; `onError: continueErrorOutput` routes malformed JSON to a separate branch
   (which reaches an `If` node) instead of crashing the run.
5. `Loop Over Items` (`Split In Batches`) processes one slide item at a time.
6. `Add Additional Slide Info` (Set) stamps a fixed `logo_name` string ("n8n.io -
   [course site]") onto each slide item, used as a footer/section label in the
   generated slide.
7. `Google_Slides_Create_Slide` (HTTP Request, POST to the Slides API's `batchUpdate`
   endpoint, `predefinedCredentialType` auth) sends a large batch of requests for the
   current slide: create the slide, set a background fill, create four decorative
   ellipse shapes with distinct colors, create and style a section-label text box, a
   title text box, a subtitle text box, and a bulleted body text box.
8. `Wait` pauses briefly, then loops back to `Loop Over Items` for the next slide,
   until all slide items are processed.
9. A separate `If` node (checking `$runIndex >= 2`) and a second, near-duplicate
   `batchUpdate` HTTP node (`Google Slide BASIC Generation`, simpler single-ellipse
   "accent" style) sit alongside the main loop; based on the connections graph, this
   branch is reachable from the JSON-parse error path rather than the main happy path,
   consistent with it being an earlier, simpler styling iteration kept in the file
   rather than deleted.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- OpenAI API credential, for the slide-outline generation agent (`gpt-3.5-turbo`).
- Google Slides OAuth2 credential, for creating the presentation and for the
  `batchUpdate` HTTP calls (both the node-level Slides credential on the `Google
  Slides` node and the `predefinedCredentialType` auth on the HTTP Request nodes).
- A Google Sheets OAuth2 credential is also attached to two of the HTTP Request nodes
  in this workflow, though the request bodies for those nodes only call the Slides
  API; this looks like a leftover credential attachment from how the node was cloned
  in the original build rather than an active dependency, but n8n will still prompt
  for it on import.

## Usage

Activate the chat trigger, open the chat panel in n8n, and send a topic (for example,
"the history of the internet"). The workflow creates a new Google Slides presentation,
generates a 10-slide outline via the LLM, and builds each slide in place via the
Slides API. The finished presentation's link is available from the `Google Slides`
node's output (`presentationId`) once the run completes.

## Challenges

- **Fixed slide count with no user control.** `Total_Slides_To_Generate` hardcodes 10
  slides; there's no chat parameter or form field to request a shorter or longer deck,
  so every topic gets the same length regardless of how much content it actually
  supports.
- **JSON-parsing the LLM's output is a real failure point.** `gpt-3.5-turbo` is asked
  to return a JSON array in its prose response, then a Code node does
  `JSON.parse(input)` on it directly. Any preamble text, trailing commentary, or
  malformed JSON from the model breaks the parse; the `onError: continueErrorOutput`
  routing handles this by diverting to a separate branch, but that branch is a partial
  duplicate of the main slide-styling path rather than a real retry-with-correction
  step.
- **Duplicate/parallel styling implementations.** The workflow contains at least two
  distinct Slides `batchUpdate` HTTP nodes with materially different visual designs
  (a "BASIC" single-accent style and an "HQ Style 1" four-shape style), which suggests
  design iteration was kept side by side in the same file rather than the earlier
  version being removed once the newer one worked. This makes the actual "happy path"
  harder to read from the canvas alone without tracing the `connections` object.
- **No handling for Slides API rate limits beyond a fixed `Wait`.** The `Wait` node
  between slide-creation calls is a blunt fixed delay rather than a response-based
  backoff; a longer deck or a slower API day could still hit per-minute quota limits
  that the workflow wouldn't detect or retry around.
- **Bullet formatting is a single joined string, not real paragraph splitting for
  variable-length content.** `bullets.join('\n')` inserted into one text box works for
  the fixed five-or-so-point deck this was designed around, but very long bullet lists
  would overflow the fixed-size text box the `batchUpdate` call defines, with no
  auto-resizing logic in the request bodies.

## What I learned

Reading a workflow that builds output via raw Google Slides API `batchUpdate` calls
(rather than n8n's built-in Slides node operations) made clear how much manual layout
math (`translateX`/`translateY`/`magnitude` in points) a "simple" AI slide generator
actually requires once you want real visual design instead of a plain text dump per
slide. It also showed a concrete example of prompt-to-JSON parsing being the fragile
joint in an LLM pipeline: the moment a model wraps its JSON in a sentence, the whole
downstream loop breaks.

## What I'd do differently

I'd add a slide-count input so the deck length matches the topic, use n8n's built-in
structured-output parsing (as the sibling `youtube-agent-starter-template` project in
this Portfolio does) instead of a raw `JSON.parse()` on model text, consolidate the
two competing slide-styling HTTP calls into one chosen design, and replace the fixed
`Wait` delay with real rate-limit-aware retry handling.
