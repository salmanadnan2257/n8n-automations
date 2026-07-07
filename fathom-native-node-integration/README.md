# Fathom Native Node Integration

## What it is

An n8n workflow that listens for Fathom.ai call recordings through Fathom's
dedicated n8n trigger node (`n8n-nodes-fathom.fathomTrigger`), looks the caller up
in a Google Sheets CRM, and, for a first sales call, extracts proposal content
from the call transcript with an LLM and drops it into a Google Slides template.
The finished draft is emailed to the workflow owner for review, not sent straight
to the client. It uses Fathom's own community node to receive the webhook, rather
than a generic Webhook node that would need to parse Fathom's raw payload by hand.

## Why it exists

After a sales call, someone still has to open the recording, pull out the client's
problem, the proposed solution, the phases, and the pricing, and turn all of that
into a proposal document. This workflow does that first pass automatically: it
takes the structured data Fathom already provides for a finished call and turns it
into a populated slide deck ready for a human to review and send.

## Features

- Uses Fathom's own trigger node instead of a generic webhook, so meeting title,
  transcript, summary, action items, and attendee list all arrive as parsed
  fields on the webhook body, not raw JSON that needs to be reverse-engineered.
- Looks up the caller in a Google Sheets CRM by matching the first calendar
  invitee's email address.
- Branches on whether this is a lead's first sales call or a later closing call,
  based on whether a transcript ID is already on file for that lead.
- On a first sales call, runs the transcript through an LLM to extract 19
  structured fields (proposal title, client bottlenecks, solution headings and
  descriptions, four project phases, and payment terms).
- Copies a Google Slides template and replaces each placeholder token with the
  extracted content, so every proposal starts from the same layout.
- Emails a link to the generated slide deck for manual review before it goes
  anywhere near the client.
- Writes the outcome back to the CRM row (call shown, proposal sent, transcript
  ID) so the sheet stays the source of truth for where each lead stands.
- Ships a second, fully disabled copy of the entire pipeline wired to OpenAI's
  `gpt-5-mini` instead of the live branch's OpenRouter/Claude Sonnet 4 model,
  kept as an inert alternate LLM configuration rather than something that runs.

## Architecture

Node-by-node, in execution order, for the live (enabled) branch:

1. **Webhook** (`n8n-nodes-fathom.fathomTrigger`): the entry point. Fathom calls
   this node's webhook when a recording finishes processing, authenticated with a
   webhook secret configured on the node. The payload lands as parsed fields
   under `body`: `meeting_title`, `created_at`, `default_summary.markdown_formatted`,
   `transcript` (an array of `{speaker, text}` entries), `calendar_invitees`,
   `action_items`, `url`, `share_url`, and `recording_id`.
2. **Get Lead Info** (`googleSheets`): reads the "CRM" sheet, filtering for the
   row whose `Contact Email` column matches `calendar_invitees[0].email` from the
   webhook body.
3. **Sales Call or Closing Call?** (`if`): checks whether that row's
   `Sales Transcript ID` field is empty.
   - **True** (no transcript ID on file yet, so this is treated as the lead's
     first sales call) leads into the proposal-generation chain (steps 4 to 9).
   - **False** (a transcript ID already exists) skips straight to
     **Update row with latest call ID** (`googleSheets`, `appendOrUpdate`),
     which writes the new `recording_id` into `Latest/Closed Transcript ID` for
     that lead and stops there. No proposal is generated on this path.
4. **Clean Up Fathom Data** (`code`): pulls the raw fields back out of the
   original **Webhook** node's output (not the CRM lookup), strips markdown
   links out of the summary, collapses repeated blank lines, and re-groups the
   transcript array into per-speaker blocks (`**Speaker:**\ntext`). Also reduces
   `calendar_invitees` down to `{name, email}` pairs. Outputs a flat object with
   `meeting_title`, `date`, `attendees`, `recording_url`, `playback_url`,
   `summary`, `transcript`, and `action_items`.
5. **Extract Information for the Proposal** (`@n8n/n8n-nodes-langchain.informationExtractor`):
   fed the lead's company name plus the cleaned transcript, and asked to extract
   19 named attributes: proposal title and description, client bottlenecks (capped
   at 120 words), the project's aim and goal, three solution headings and
   descriptions, four project phases, and four pricing/deadline fields for a
   two-part payment. Backed by:
6. **OpenRouter Chat Model** (`@n8n/n8n-nodes-langchain.lmChatOpenRouter`, model
   `anthropic/claude-sonnet-4`): the LLM behind the extraction node on the live
   branch.
7. **Copy existing template** (`googleDrive`, operation `copy`): duplicates a
   fixed Google Slides file ("The Proposal Agent Slides") and names the copy
   `Proposal for {Company Name}`.
8. **Replace text in the proposal** (`googleSlides`, operation `replaceText`):
   swaps 19 placeholder tokens in the copied deck (`{{proposalTitle}}`,
   `{{proposalDescription}}`, `{{bottlenecks}}`, `{{aimdescription}}`,
   `{{goaldescription}}`, `{{firstsolutionheading}}` through
   `{{thirdsolutiondescription}}`, `{{phaseonedescription}}` through
   `{{phasefourdescription}}`, and the four cost/deadline tokens) with the
   extracted values.
9. **Send the proposal for review and edits** (`gmail`): emails a single fixed
   address (the workflow owner's own inbox, scrubbed to a placeholder in this
   repo) with a link to the generated presentation, asking for review and edits.
   This is a draft-review step, not delivery to the client.
10. **Update row in sheet** (`googleSheets`, `appendOrUpdate`, matched on
    `Contact Email`): writes `Showed Call? = true`, `Proposal sent? = true`, and
    `Sales Transcript ID = recording_id` back to the CRM row.

Separately, a second, structurally identical pipeline exists in the same
workflow (`Webhook1` through `Update row in sheet2`), wired to an
**OpenAI Chat Model** node (`gpt-5-mini`) instead of OpenRouter. Its trigger node
(`Webhook1`) is disabled, so this branch does not run; it appears to be kept
around as an alternate model configuration rather than a live path.

## Setup

Import `workflow.json` via n8n's Workflows menu, Import from File.

Before it can run for real:

- **Fathom webhook.** The `Webhook` node's `webhookSecret` parameter has been
  replaced with `YOUR_FATHOM_WEBHOOK_SECRET_HERE` in this repo. Generate a real
  secret in your Fathom account's webhook settings, set it on the node, and point
  Fathom's webhook at this workflow's production URL (n8n shows that URL once the
  workflow is active).
- **Google Sheets CRM.** Point `Get Lead Info`, `Update row in sheet`,
  `Update row with latest call ID`, and their duplicate-branch counterparts at
  your own spreadsheet. The sheet needs at minimum a `Contact Email` column
  (used as the lookup and match key), a `Company Name` column, a
  `Sales Transcript ID` column, a `Latest/Closed Transcript ID` column, and
  `Showed Call?` / `Proposal sent?` columns.
- **Google Slides template.** `Copy existing template` points at a specific
  Google Drive file ID. Build your own deck with the 19 placeholder tokens
  listed under step 8 above, get its file ID, and update that node. Note: an
  in-workflow sticky note ("Customization Guide") lists a different, shorter set
  of placeholder names (`{{text}}`, `{{description}}`, `{{companyname}}`,
  `{{problem}}`, `{{projectaim}}`, `{{projectgoal}}`, and so on) than what the
  `Replace text in the proposal` node actually replaces. That sticky note appears
  to be stale; the tokens in the node itself are what the workflow really uses,
  and the ones I list in step 8 are the ones a real template needs.
- **Gmail.** The "Send the proposal for review and edits" node had a personal
  address hardcoded (`sendTo`), scrubbed to `YOUR_EMAIL_HERE@example.com` here.
  Set it to wherever proposal drafts should land for review.
- **LLM credential.** The live branch needs an OpenRouter API credential for
  the `OpenRouter Chat Model` node. The disabled backup branch would need an
  OpenAI API credential if it were ever re-enabled.

## Usage

Once the Fathom webhook is wired up and the workflow is active, it runs
automatically whenever Fathom finishes processing a call recording for a lead
already present in the CRM sheet. A first sales call produces a proposal draft
and an email to the reviewer; a later call for the same lead just updates the
CRM with the newest transcript ID.

## Challenges

- **A likely field-name mismatch on the sales/closing branch.** The `If` node
  checks `$json['Sales Transcript ID']` (no trailing space), but the CRM column
  actually written to by `Update row in sheet` is named `'Sales Transcript ID '`
  (with a trailing space), per that node's column schema. If the live Google
  Sheet's header really has that trailing space, the lookup key the `If` node
  reads won't match the column n8n returns, meaning the field would read as
  empty on every run and the "closing call" branch (step 3's False path) might
  never actually be reached. I can't confirm the live sheet's exact header from
  the export alone, so I'm flagging this as observed, not fixed.
- **A full duplicate pipeline sits disabled in the graph.** Roughly half the
  workflow's 29 nodes are a second copy of the entire chain, differing only in
  which chat model backs the extraction step. It's disabled at the trigger, so
  it doesn't run, but it doubles the node count anyone reading this graph has
  to get through to find the one live path.
- **The in-workflow customization guide doesn't match the real template
  tokens.** The "Customization Guide" sticky note tells whoever sets this up to
  build a template with placeholders like `{{text}}`, `{{companyname}}`, and
  `{{problem}}`, but the `Replace text in the proposal` node's actual token list
  is entirely different (`{{proposalTitle}}`, `{{bottlenecks}}`,
  `{{aimdescription}}`, and so on). Anyone following the sticky note's guidance
  literally would build a template that never gets filled in.
- **No error handling on any external call.** The Google Sheets lookup, the
  Slides copy, the text replacement, and the Gmail send all run with default
  settings; none has retry or continue-on-fail configured. A transient auth
  expiry or rate limit on any one of them kills the run after the transcript has
  already been cleaned and the LLM extraction has already run, with nothing
  written back to the CRM to show a proposal was attempted.
- **The proposal never reaches the client inside this graph.** The final Gmail
  step sends the deck link to the workflow owner's own inbox for review, not to
  the client. That's clearly deliberate given the node's name, but it means this
  workflow automates proposal drafting, not proposal delivery; sending the
  reviewed version to the client is a separate step outside what's exported here.
- **n8n's own trigger diagnostics didn't recognize the Fathom trigger as a
  production trigger.** Querying this workflow's details reported "no production
  triggers (Schedule, Webhook, Form, or Chat)," despite the graph starting from a
  Fathom Trigger node with a webhook ID attached. This is most likely because
  that check only recognizes n8n's built-in trigger types and doesn't classify
  the community Fathom package's trigger node as one of them, but I can't verify
  from the export alone whether the workflow reliably receives live Fathom
  webhook calls once deployed, so I'm stating that plainly rather than assuming
  it works end to end.

## What I learned

Fathom's dedicated n8n node hands over already-parsed fields (a transcript array
of `{speaker, text}` objects, a `calendar_invitees` list, a markdown-formatted
summary) directly on the webhook body. That's a real difference from a
webhook-based integration built on n8n's generic Webhook node, which would
receive Fathom's raw payload shape and need its own parsing code before any of
this was usable. Reading the `If` node's condition against the schema of the
Sheets node that writes that same field was the only way to catch the trailing
space mismatch; the field names looked identical at a glance in the n8n editor
but are not identical strings. I also hadn't seen a fully-disabled duplicate
branch used this way before, as a way to keep an alternate LLM configuration on
hand without deleting the working pipeline or leaving two active paths that
could both fire.

## What I'd do differently

I'd fix the trailing-space mismatch on `Sales Transcript ID` (or confirm it
isn't actually a problem by checking the live sheet's real header) before
trusting the sales/closing branch logic. I'd update the sticky note's
customization guide to list the placeholder tokens the `Replace text in the
proposal` node actually uses, since as written it would send someone to build
the wrong template. I'd delete the disabled OpenAI branch rather than leave a
full second copy of the pipeline sitting inert, or at minimum collapse it to a
single shared sub-workflow so there's only one place to maintain the logic. I'd
also add continue-on-fail to the Sheets, Slides, and Gmail nodes so a transient
API error doesn't silently drop a proposal that had already been generated.
