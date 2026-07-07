# VAPI Call Trigger Utility

An n8n workflow that pulls one qualified lead from a Google Sheet, builds a personalized
cold-call script for it, updates a VAPI voice AI assistant with that script, places the
outbound call through VAPI, waits for the call to finish, and writes the call results
(transcript, recording link, cost, status) back to the sheet.

## Note on scope

This project was approved for the portfolio as two related workflows: "Trigger VAPI
Call" (this one) and a sibling named "Instant VAPI Call." The sibling workflow's source
was not available anywhere accessible for this build: not in the n8n backup export, not
on disk, and the MCP tool that could otherwise fetch it directly from the live n8n
instance is disabled for that workflow's id. Nothing about "Instant VAPI Call" is stated
here because nothing about it could be verified. This folder documents only the workflow
whose JSON was actually available: "Trigger VAPI Call."

## What it is

A manually-triggered n8n workflow ("Trigger VAPI Call") that automates one outbound
sales call at a time. It reads leads from a Google Sheet, filters down to one usable
row, assembles a long real-estate cold-call system prompt for a VAPI assistant, pushes
that prompt to VAPI, dials the lead's number, polls VAPI until the call ends, and logs
the call outcome (transcript, recording URL, cost breakdown, end reason) back to the
same sheet.

## Why it exists

Calling every lead with a pre-written, personalized voice AI script by hand means
manually editing the assistant's configuration in the VAPI dashboard before every call.
This workflow turns that into a single "Execute workflow" click: it grabs the next
untouched, qualified row from the lead sheet, reconfigures the shared VAPI assistant for
that specific prospect, starts the call, and records what happened. It exists to remove
the manual reconfiguration step between leads, not to run at scale or unattended
(there is no schedule trigger; someone has to press Execute).

## Features

- Pulls leads from a Google Sheet ("Cold Call - Lead List") and filters to rows with a
  non-empty phone number, past the header row, and matching a specific country-code
  prefix.
- Caps each run to a single lead (via a Limit node), so one click of "Execute workflow"
  processes exactly one call.
- Builds a two-part system prompt for the VAPI assistant: a data manifest (agent name,
  contact info, prospect name/company/phone) plus a long real-estate cold-calling script
  (opener, objection handling, a strict appointment-booking protocol, and a scripted
  voicemail message).
- Updates the VAPI assistant's `firstMessage` and system prompt via a PATCH request
  before every call, so the same assistant ID is reused but reconfigured per prospect.
- Places the call via VAPI's `/call` endpoint, then polls `/call/{id}` every 20 seconds
  until VAPI reports the call has ended.
- Appends or updates the lead's row in the sheet with the full call record: id,
  timestamps, transcript, recording URL, summary, cost, and end reason.

## Architecture

Node graph, in execution order for the live path:

1. **When clicking 'Execute workflow'** (Manual Trigger) starts the run.
2. **Google Sheets** (read) loads all rows from the "1000 Personal Phone Number" sheet
   inside the "Cold Call - Lead List" spreadsheet.
3. **Filter** keeps only rows where the phone number field is non-empty, the row number
   is greater than 1 (skips the header), and the cleaned phone number starts with
   `+92`. In this exported version that is a Pakistan country-code prefix; there is no
   indication in the workflow of why that specific prefix is enforced, and nothing in
   the graph explains it further, so it is stated here as observed, not interpreted.
4. **Limit** keeps only the first item that survives the filter, so one execution
   processes one lead.
5. **Set Vars** (Set node) extracts `first_name`, `last_name`, `company`, `title`, and a
   whitespace/hyphen-stripped `phone_number` from the sheet row. It also assembles
   `first_part` (a static data manifest: agent name, agent email, agent phone, company
   name, plus prospect placeholders) and `second_part` (the full real-estate cold-call
   script: opener, discovery questions, objection handling, and a step-by-step
   appointment-booking protocol for a VAPI tool-calling assistant). It also rolls a
   random `type` value (1 or 2).
6. **Final Prompts** (Set node) reads directly from Set Vars and produces `opener`
   (a template string built from `first_name`), `system_prompt` (`first_part` +
   `second_part` concatenated), and `company`.
7. **Loop Over Items1** (Split In Batches) feeds one item at a time into the call loop.
8. **Update VAPI** (HTTP Request, PATCH to `api.vapi.ai/assistant/{id}`) rewrites the
   assistant's `firstMessage`, transcriber settings (Deepgram, `nova-2-phonecall`),
   model (OpenAI `gpt-5-mini` with four tool IDs attached), and system prompt using the
   values from Final Prompts.
9. **Call VAPI** (HTTP Request, POST to `api.vapi.ai/call`) starts the outbound call,
   passing the prospect's phone number, a truncated company name as the call name, the
   assistant ID, and a phone number ID.
10. **Get Call** (HTTP Request, GET `api.vapi.ai/call/{id}`) fetches the current call
    record.
11. **If1** checks whether `status` equals `"ended"`. If not, **Wait** pauses 20 seconds
    and loops back to Get Call. If yes, it proceeds to log the result.
12. **Edit Fields2** maps the finished call's fields (id, timestamps, transcript,
    recording URL, summary, cost breakdown, status, end reason, and more) into a flat
    object, plus the original phone number to match against.
13. **Google Sheets3** appends or updates the lead's row (matched on phone number) with
    all of the call-result fields from step 12.
14. Loop Over Items1 advances to the next batch item (there is only one, given the
    Limit node upstream, so the loop ends after this single call).

A second branch exists in the same workflow file (**Loop Over Items** with batch size
25, feeding a disabled **Google Sheets1** node, an **AI Agent** node backed by Google
Gemini, an **If**, two **Edit Fields** variants, and a **Merge** node) that produces an
"icebreaker" line via an LLM and would choose between two different call-opener scripts
based on the random `type` value. Reading the `connections` block in the JSON, this
branch is not reachable from the Manual Trigger: its only inbound connection comes from
the disabled Google Sheets1 node, which itself has no inbound connection either. It is
dead code left in the canvas, not part of the live execution path, and the random
`type` value set in Set Vars currently has no effect on the call that actually runs.
This is documented rather than fixed, since the deliverable is what the workflow
demonstrably does, not a cleaned-up rewrite of it.

## Setup

1. In n8n: **Workflows** menu > **Import from File**, select `trigger-vapi-call.json`.
2. Create or attach the following credentials in n8n and reassign them on the imported
   nodes (the JSON only contains credential name/ID pointers, not the credentials
   themselves):
   - A Google Sheets OAuth2 credential, used by **Google Sheets**, **Google Sheets1**
     (disabled), and **Google Sheets3**.
   - A generic HTTP Header Auth credential holding a VAPI private API key, used by
     **Update VAPI**, **Call VAPI**, and **Get Call** (sent as the `Authorization`
     header VAPI expects; the header itself is not configured in the exported node and
     would need to be added or confirmed in n8n's credential settings).
   - A Google PaLM/Gemini API credential, used by **Google Gemini Chat Model** (only
     reachable through the dead branch described above; not required for the live call
     path to function, but the workflow will not import cleanly without some credential
     assigned, even a placeholder one).
3. Replace the placeholder spreadsheet ID and sheet reference in the **Google Sheets**,
   **Google Sheets1**, and **Google Sheets3** nodes with your own sheet's ID, or rebuild
   the reference by picking your sheet from n8n's Google Sheets node UI.
4. Set up a VAPI assistant, phone number, and (if you keep the booking-protocol tools
   from the system prompt) any external tools it calls; note their IDs, and replace the
   assistant ID in the **Update VAPI** URL and body, and the `phoneNumberId` in the
   **Call VAPI** body.
5. Point the lead sheet at your own data: columns matching `First Name`, `Last Name`,
   `Company`, `Title`, and `Personal Numbar 1` (the phone number column; the sheet in
   this workflow uses that exact, misspelled column name). Adjust or remove the `+92`
   country-code filter in the **Filter** node for your own lead list.

## Usage

Open the workflow in n8n and click **Execute workflow**. Each click processes exactly
one lead: it pulls the next row that passes the filter, reconfigures the VAPI assistant
for that prospect, places the call, waits for it to end, and writes the outcome back to
the sheet. To call more than one lead, click Execute workflow again; there is no
schedule trigger and no batch-calling loop across multiple rows in this version.

## Challenges

- **Sequential polling instead of a webhook.** The workflow checks call status by
  polling `Get Call` every 20 seconds until `status` is `"ended"`, rather than reacting
  to a VAPI webhook event. This is simple to build in n8n and easy to follow, but it
  ties up an execution for the full duration of the call (VAPI calls in this script can
  run several minutes given the multi-step booking protocol), and 20-second granularity
  means the logged `endedAt` timestamp could lag the real end time by up to that long.
- **One lead per manual click, with a hardcoded Limit node.** The Limit node has no
  configured value, which in n8n means it defaults to keeping exactly one item. Combined
  with the manual trigger, this means the workflow cannot be used for volume outreach
  without either removing the Limit node or wrapping the whole workflow in an outer
  scheduling loop, neither of which is present here.
- **A second, disconnected branch left inside the same canvas.** The AI Agent/Gemini
  icebreaker branch and the `type`-based two-variant opener selection (If, Edit Fields,
  Edit Fields1, Merge) are wired together but never receive input from the live trigger
  path, because their only upstream node (Google Sheets1) is disabled and itself has no
  inbound connection. The random `type` field computed in Set Vars is consequently
  unused by the call that actually goes out. Reading the `connections` object in the
  raw JSON was the only way to confirm this; visually in the n8n canvas it would look
  like a working alternate path.
- **A narrow, unexplained country-code filter.** The Filter node only allows phone
  numbers starting with `+92`, while the underlying lead list is a US real-estate
  contact sheet. Nothing in the workflow (node names, notes, or values) explains why;
  it reads like a testing constraint (calling a known personal or team number) that was
  left in place rather than reverted before the workflow was archived.
- **Credential-shaped strings the export does not carry.** Google Sheets, VAPI, and
  Gemini credentials are referenced only by internal n8n ID and label; none of the
  actual keys are in the JSON, which is correct for portability but means this workflow
  cannot be executed as-is without recreating all three credentials from scratch in the
  importing n8n instance.
- **A visible, unpolished `opener` value.** Because Final Prompts builds `opener` as a
  bare `{first_name}???` template rather than a natural sentence for the assistant's
  first message, the assistant would open every real call with just the prospect's
  first name followed by three question marks. This is either an in-progress edit that
  never got a proper opening line, or a placeholder left over from earlier testing; it
  is documented as observed rather than corrected, since correcting it would be
  inventing behavior the workflow does not currently have.

## What I learned

Reading `connections` directly in the exported JSON, rather than trusting how the
canvas would render, was the only reliable way to determine which of two branches was
actually live. n8n's Split In Batches node has two outputs (`done` at index 0, `loop`
at index 1), and getting the ordering backwards while reading the file would have led
to describing Edit Fields3 as the per-call step and Update VAPI as the finishing step,
which is the reverse of what the connections array shows. Also, n8n's Limit node with
no configured parameters silently defaults to keeping one item, which is easy to miss
when skimming a node that has an empty `parameters: {}` block.

## What I'd do differently

I would remove the dead icebreaker/Gemini branch entirely rather than leave it wired
into the canvas unreachable, since it adds a Gemini credential requirement to the
import step for a path that never runs. I would also replace the polling loop with a
VAPI webhook-based end-of-call trigger so the workflow doesn't hold an n8n execution
open for the full call duration, and I would fix or remove the `+92`-only filter and
the bare `{first_name}???` opener before treating this as call-ready rather than a
working prototype.
