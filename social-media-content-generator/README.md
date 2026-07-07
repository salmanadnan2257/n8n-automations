# Social Media Content Generator

An n8n workflow (`workflow.json`, 190 nodes) that turns a short form submission into a
finished social media post: body copy, an image prompt, a generated image, a video
prompt, and a generated video clip, tailored to one of ten different copywriting
frameworks chosen by the person filling out the form.

## What it is

A single n8n workflow, exported here as `workflow.json`, built around a form trigger
(`Submit Social Post Details`). The submitter picks one of ten content "pillars" from a
dropdown (for example "Pain Point & Solution" or the branded `Framework: "The Art of
War"`), then a follow-up form asks whether they want a "Direct Based" or "Story Line
Based" version and collects the raw facts for that pillar (a pain point and its
solution, a case study's before/after numbers, a parable's characters, and so on).
The workflow runs those facts through a Google Gemini agent to write the post, then
runs the finished post through further Gemini agents to write an image prompt and a
video prompt, calls Runware.ai to render the image and Novita.ai to render a video
clip (image-to-video or text-to-video depending on the branch), and returns everything
to the submitter as the form's own response.

## Why it exists

The workflow is built for a specific niche (the system prompts explicitly address
"a Real Estate Agent") and a specific problem: writing consistently good marketing
copy across ten distinct persuasion styles is slow and inconsistent when done by hand,
and pairing that copy with matching visuals is a second, separate job. This workflow
collapses both into one form submission by giving each content pillar its own
copywriting formula and a shared, tiered pipeline for turning the finished copy into
an image prompt, a video prompt, and rendered media.

## Features

- Ten selectable content pillars: Pain Point & Solution, How-To & Quick Win, Case
  Study & Results, Myth-Busting & Future-Gazing, three branded frameworks (`"The
  Identity Architect"`, `"The Art of War"`, `"The Experiential & Interactive"`),
  `Narratives & Mythological Frameworks`, and two named story-forms (`"The Agent and
  the Echo"`, `"The Dealmaker's Ghost"`).
- Every pillar supports two tones, "Direct Based" and "Story Line Based", each with
  its own follow-up form and its own agent system prompt, so the same pillar can
  produce either a straight-talking post or a narrative one.
- Each pillar's system prompt encodes a named copywriting formula: for example Pain
  Point & Solution uses a five-step "Aspirin Formula" (Isolate, Agitate, Bridge,
  Present, Illustrate), Quick Win uses a "Quick Win Blueprint," Case Study uses a
  "Proof Positive" blueprint, and the two story-forms use a "Parable Blueprint."
- A three-tier image/video generation stage downstream of the copy: "Level 1" (the
  four base pillars), "Level 2" (the three branded frameworks), and "Level 3" (the
  narrative and story-form pillars) each get their own art-direction system prompt,
  so a case study photo and a parable's "master shot" are styled differently even
  though they go through the same node types.
- Image generation via Runware.ai (`https://api.runware.ai/v1`), video generation via
  Novita.ai's Wan text-to-video and image-to-video models, with polling loops
  (`Wait` + `If` node pairs) that check task status until the async render finishes.
- Everything returns in one response: post text, image prompt, video prompt, and the
  final video URL, all assembled in `Set` ("Edit Fields") nodes and combined through a
  cascade of `Merge` nodes down to a single final node.

## Architecture

Entry point: `Submit Social Post Details` (`n8n-nodes-base.formTrigger`) collects the
`Type` dropdown, then a `Switch` node (`n8n-nodes-base.switch`) routes on that value
into one of ten branches, one per pillar.

Each branch follows the same shape:

1. An `- Option` form (`n8n-nodes-base.form`) asks Direct Based vs Story Line Based.
2. An `If` node reads that answer and routes to either an `- Direct` or `- Story Line`
   form, which collects the pillar-specific raw facts (different field names per
   pillar, e.g. "Pain Point"/"Solution(s)"/"Benefit(s)" versus "The Client's 'Before'
   State"/"The Quantifiable Pain"/etc for a case study).
3. That data feeds a `@n8n/n8n-nodes-langchain.agent` node (paired with its own
   `lmChatGoogleGemini` chat model node) running the pillar-and-tone-specific system
   prompt described above.
4. A `Merge` node recombines the Direct and Story Line paths back into one stream, and
   a `Set` ("Edit Fields") node normalizes the result to a common `{ Type, output }`
   shape.

The ten branches then collapse into three shared image/video pipelines by tier:
`Merge12` combines the four base-pillar outputs ("Level 1"), `Merge1` combines the
three branded-framework outputs ("Level 2"), and `Merge13` combines the narrative
pillar plus the two story-forms ("Level 3"), five total content types across those
last two merges even though the top-level form groups them into four "Framework"-style
options and two "Story-Form" options.

Downstream of each tier's merge, three more `agent` nodes (again each paired with its
own Gemini chat model) write a text-to-image prompt, a text-to-video prompt, and an
image-to-video prompt (the image-to-video agent is explicitly given the original
text-to-image prompt as extra context, not just the post text). A `Code` node
("Clean") strips the agent output down to plain strings, an `httpRequest` node
("Generate Image") posts to Runware.ai, and a second pair of `httpRequest` nodes posts
to Novita.ai's async video endpoints and then polls a `task-result` endpoint in a
`Wait` → `httpRequest` (GET) → `If` (checks `task.status == TASK_STATUS_SUCCEED`) loop
until the render is ready. Final `Set` nodes assemble `{ type, post, video_url }` (and
the equivalent image fields) per tier, three more `Merge` nodes combine the tiers, and
the workflow's single leaf node, `Merge17`, is what the form trigger returns to the
submitter (`responseMode: lastNode`).

No spreadsheet, database, CMS, or social-platform API is called anywhere in the graph.
The workflow's only output channel is the form response itself.

## Setup

1. Import `workflow.json` into a running n8n instance (self-hosted or n8n Cloud) that
   supports the LangChain node package (`@n8n/n8n-nodes-langchain`).
2. Create three credentials in n8n and attach them to the matching nodes (see
   `CREDENTIALS.md` for exactly which nodes need which credential):
   - a Google Gemini API credential for every `lmChatGoogleGemini` node,
   - a generic HTTP header credential holding a Runware.ai API key for the
     `Generate Image` nodes,
   - a generic HTTP header credential holding a Novita.ai API key for the
     `Image-to-Video` and `Text-to-Video` `httpRequest` nodes.
3. Activate the workflow so the form trigger is reachable, or run it manually from the
   n8n editor for testing.

## Usage

1. Open the form served by `Submit Social Post Details` and pick a `Type` (one of the
   ten pillars listed above).
2. On the next form, choose Direct Based or Story Line Based, then fill in the fields
   that form asks for (they differ per pillar, since each pillar's copywriting formula
   needs different raw inputs).
3. Submit. The workflow runs the copy agent, then the image and video prompt agents,
   then calls Runware.ai and Novita.ai, and returns the finished post text, the image
   prompt and video prompt used, and the rendered video URL as the form's response.
   Render time depends entirely on Novita.ai's queue and polling cadence and was not
   benchmarked here.

## Challenges

- **Ten near-identical branches invite drift.** Because n8n has no native way to loop
  a form wizard over a list of content types, each of the ten pillars is a fully
  copy-pasted subgraph (its own Option form, Direct/Story Line forms, agent pair, and
  Merge). The node names show the seams: many downstream nodes still carry the name of
  whichever pillar was built first (for example the shared Level 1 image-prompt agent
  is still named "Pain Point - Text-To-Image" even though it also reads Quick Win,
  Case Study, and Myth-Busting output through `Merge12`). That naming mismatch is real
  and visible in the exported JSON, not a guess.
- **A form option is grouped with a different tier than its label implies.**
  "Narratives & Mythological Frameworks" sits in the same top-level dropdown group as
  the three branded "Framework:" options, but its output is merged into `Merge13`
  alongside the two "Story-Form:" pillars, i.e. it runs through the Level 3
  (narrative) art-direction prompts, not the Level 2 (framework) ones. Whether that
  was intentional or a copy-paste artifact isn't verifiable from the JSON alone; it's
  simply what the connections graph shows.
- **Async video rendering needs a hand-rolled poll loop.** Novita.ai's video endpoints
  return a task ID from a POST call and require a separate GET call against
  `task-result` to check progress. The workflow implements this with `Wait` → GET →
  `If` (checking for `TASK_STATUS_SUCCEED`) node triples that loop back on themselves.
  There's no cap visible on how many times that loop can run, and no explicit
  handling of a failed or timed-out render; if Novita.ai never returns success, the
  execution appears to wait indefinitely rather than fail cleanly.
- **Prompt chaining across nodes is reference-fragile.** Every agent prompt pulls
  prior-node output by literal node name, e.g. `{{ $('Merge12').item.json['Type'] }}`.
  Renaming any upstream node in the editor (n8n does not always auto-update these
  expressions) would silently break a downstream prompt, producing an empty or wrong
  value rather than a visible error. With 190 nodes this is a real, not hypothetical,
  maintenance hazard.
- **No error handling anywhere in the graph.** There isn't a single error-trigger,
  try/catch, or fallback branch across all 190 nodes. A Runware.ai or Novita.ai
  outage, rate limit, or malformed response would surface as a raw failed execution
  with no graceful message back to whoever submitted the form.
- **Field-name coupling between forms and prompts.** Each pillar's Direct/Story Line
  form defines its own field labels (e.g. "The Client's 'Before' State"), and the
  paired agent's prompt template references those exact labels. A typo in either place
  wouldn't throw an error in n8n, it would just resolve to `undefined` in the prompt
  text and quietly produce a worse post. This is inherent to how form field references
  work in n8n expressions, not a bug introduced by this workflow specifically, but the
  ten-pillar scale here makes it a real risk.

## What I learned

- Reading a large n8n export means walking the `connections` object, not just the
  node list. The node names alone (`Merge12`, `Edit Fields27`) are meaningless until
  you trace which nodes actually feed them; the auto-incrementing default names n8n
  assigns make the raw node list read like noise until you do that.
- A three-tier "shared pipeline downstream of many branches" pattern (ten copy
  branches collapsing into three image/video pipelines) is a reasonable way to avoid
  duplicating the expensive part (image/video generation) ten times over, and it's
  visible directly in the merge topology once you trace it.
- Async third-party rendering APIs (Novita.ai here) push real complexity into the
  workflow in the form of polling loops that n8n itself has no first-class node for;
  it's built from generic `Wait`, `httpRequest`, and `If` nodes strung together.

## What I'd do differently

- I would extract the repeated per-pillar subgraph (Option form → Direct/Story Line
  form → agent pair → Merge → Edit Fields) into an n8n sub-workflow called once per
  pillar with different parameters, instead of copy-pasting it ten times. That would
  remove the naming drift and reference-fragility issues described above at the
  source instead of documenting around them.
- I would add at least one error-handling branch around the Runware.ai and Novita.ai
  calls (an n8n error trigger or an `If` on the HTTP status code) so a failed render
  returns a clear message to the form submitter instead of a raw failed execution.
- I would cap the Novita.ai polling loop with a maximum retry count so a stuck or
  failed render can't leave an execution running indefinitely.
