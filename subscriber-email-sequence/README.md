# Subscriber Email Sequence

## What it is

An n8n workflow that takes a new subscriber (name, email, phone) in through a
webhook, logs them into a Google Sheets CRM, sends them an immediate welcome
email, and is wired to run a further seven-stage email follow-up cascade (F2
through F8) gated by a Google Sheets flag per stage and a time-elapsed check.
The workflow is exported here under its live internal name, "DA - Subscribe
Email Sequence" ("DA" is Digitalise Agency's internal prefix); the public title
above drops that prefix and folder name reflects it.

The workflow is currently active on the live n8n instance it was pulled from,
but only the webhook side of it is actually running: the Schedule Trigger that
is supposed to drive the seven-stage follow-up cascade is disabled (see
Challenges). As exported, new subscribers get the welcome email and a CRM row,
and that's it, until someone re-enables or manually runs the follow-up half.

## Why it exists

This is Digitalise Agency's subscriber intake and nurture pipeline: capture a
lead from a form (the header-auth credential is literally named "Digitalise
Agency - Blog Post", so the source is almost certainly a blog opt-in form),
get them into the CRM immediately, and follow up with a scripted sequence of
emails over the following days without anyone manually sending them. The email
copy itself is written for e-commerce founders, warning about over-reliance on
paid ads and pitching organic/diversified acquisition, so this is a real
outbound nurture sequence for Digitalise Agency's own lead funnel, not a demo.

## Features

- Webhook intake, protected by a header-auth credential, that accepts a
  subscriber's name, email, and phone number as JSON.
- Formats the submitted name into title case and splits it into first/last
  name fields, and normalizes the phone number into E.164-ish form (strips
  everything but digits and `+`, converts a leading `00` to `+`, adds a
  missing `+`).
- Upserts the contact into a Google Sheets CRM keyed on email, seeding
  `Started Sequence?`, `Closed?`, `Contract Sent?`, `Contract Signed?`, and
  eight per-stage flags (`F1?` through `F8?`), all initialized to `false`.
- Sends an immediate welcome/first-touch email (Gmail) styled as an HTML
  template, then marks `F1?` true and stamps a `Sequence Last Date`.
- Seven further follow-up emails (F2 to F8), each gated by its own IF node
  that checks two things: the stage's flag is still `false`, and between
  roughly 3 and 4 days (4320 to 5760 minutes) have passed since
  `Sequence Last Date`. Each stage node sends its email, marks its flag
  true, and refreshes `Sequence Last Date` for the next stage's check.
- Every follow-up subject line is written as a distinct hook (ad-account-ban
  horror story, organic vs. paid framing, urgency, social proof, and so on),
  not a generic templated reminder.

## Architecture

Node-by-node, in execution order. There are 31 nodes in total: two triggers,
one field-mapping node, three Google Sheets read/write nodes for the intake
side, seven Google Sheets read/update nodes for the follow-up side, seven IF
gates, eight Gmail send nodes (the welcome email plus F2 to F8), and two
sticky notes.

**Intake path (Webhook trigger):**

1. **Webhook** (`webhook`, POST, header auth on an `Authorization` header):
   the live entry point. Responds immediately with "Workflow got started."
   and passes the body through. There is also a disabled
   **"When clicking 'Execute workflow'"** manual trigger wired to the same
   next node, for testing from the editor.
2. **Edit Fields** (`set`): pulls `body.name`, `body.email`, and
   `body.phone_number` out of the webhook payload into flat `name`, `email`,
   `phone number` fields. No validation of format or required-ness happens
   here.
3. **Append or update row in sheet** (`googleSheets`, `appendOrUpdate`,
   matched on `Contact Email`): writes the contact into the CRM sheet.
   Full Name, First Name, and Last Name are derived from `name` with an
   expression that trims, collapses whitespace, splits on spaces, and
   title-cases each word. Contact Phone runs through the normalization
   expression described above. `Started Sequence?`, `Closed?`,
   `Contract Sent?`, `Contract Signed?`, and `F1?` through `F8?` are all
   set to the literal string `"false"` at this point.
4. **Send a message** (`gmail`): sends the welcome email to `email`, subject
   "Most e-commerce founders don't know their biggest risk," with an HTML
   body about e-commerce brands being 70-80% dependent on paid ads for
   acquisition. Signed "From: Salman."
5. **Append or update row in sheet1** (`googleSheets`, `appendOrUpdate`,
   matched on `Contact Email`): sets `Started Sequence?` and `F1?` to
   `"true"` and stamps `Sequence Last Date` to `$now` in
   `yyyy-MM-dd - hh:mm:ss a` format. This is the row the follow-up cascade
   later reads to decide timing.

**Follow-up path (Schedule Trigger, currently disabled):**

6. **Schedule Trigger** (`scheduleTrigger`): configured with an empty
   `interval` object, i.e. no explicit cron/interval fields were ever set on
   it beyond n8n's default, and the node is disabled outright. This is the
   node meant to drive the whole follow-up cascade below; as exported, it
   never fires (see Challenges).
7. **Get row(s) in sheet** (`googleSheets`): reads every row from the CRM
   sheet, no filter applied. Each row becomes one item flowing into the IF
   cascade, so the seven-stage check below runs once per contact per
   (theoretical) schedule tick.
8. **If2** through **If8** (`if`, one per stage, all with identical logic):
   each checks, for the row's `Sequence Last Date`, that the minutes elapsed
   since then are `<= 5760` (4 days) AND `>= 4320` (3 days), AND that this
   stage's flag (`F2?` through `F8?` respectively) is `false`. All seven IF
   nodes use the exact same 3-to-4-day window regardless of stage number
   (see Challenges: the sticky note describes this as "Day 2," "Day 3," etc.
   which the actual expressions don't implement).
9. **Follow-Up 2** through **Follow-Up 8** (`gmail`, one per stage): on a
   true branch, sends that stage's email to
   `$('Get row(s) in sheet').item.json["Contact Email"]`. Each has its own
   subject and HTML body (e.g. Follow-Up 2: "How one founder lost $280K when
   his ad account got banned"; Follow-Up 8: "Most founders wait until it's
   too late to diversify revenue").
10. **Update F2 Sheets**, **Update F3**, **Update F4  ** (trailing spaces in
    the name), **Update F4 2**, **Update F4 3**, **Update F4 4**, and
    **Update F4 1** (`googleSheets`, one per stage): each marks its stage's
    flag true and refreshes `Sequence Last Date`. The node names are
    inconsistent with what they actually do: despite the "Update F4 1/2/3/4"
    naming, these five nodes set `F4?`, `F5?`, `F6?`, `F7?`, and `F8?`
    respectively, not four separate F4 updates (see Challenges).
11. On the false branch, each IF node (except If8, which has no further
    branch) chains to the next stage's IF node, so a contact who isn't yet
    due, or has already had that stage, falls through to be checked against
    the next stage instead. The cascade has no explicit end node after F8;
    once `F8?` is true, none of the seven IF nodes evaluate true for that
    contact again, and nothing further happens.

Two sticky notes document the intended design (Sticky Note describes the
whole workflow; Sticky Note6 describes the follow-up section specifically).
Their claims don't fully match the live graph; the discrepancies are called
out in Challenges below rather than repeated as fact.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at
`workflow.json`. After import, wire up in n8n's credential store:

- A header-auth credential for the **Webhook** node (see CREDENTIALS.md).
- A Google Sheets OAuth2 credential for the six Google Sheets nodes, pointed
  at a real spreadsheet with the CRM's column layout. The `documentId` and
  `sheetName` shipped in `workflow.json` are placeholders; replace them with
  your own sheet.
- A Gmail OAuth2 credential for the eight Gmail nodes.

The exported JSON has the Schedule Trigger and the manual trigger both
disabled, matching the live workflow's actual state. If you want the
follow-up cascade to run automatically, you need to configure the Schedule
Trigger's interval (it currently has no interval fields set beyond an empty
default) and enable it.

## Usage

Send a POST request to the Webhook's path with an `Authorization` header
matching your header-auth credential, and a JSON body of
`{ "name": ..., "email": ..., "phone_number": ... }`. That creates or updates
the contact's CRM row and sends the welcome email immediately.

For the follow-up cascade to actually send F2 through F8, either enable and
correctly configure the Schedule Trigger, or manually execute the workflow
from the "Get row(s) in sheet" node in the n8n editor while contacts sit in
the 3-to-4-day window since their last touch.

## Challenges

- **The follow-up cascade's trigger is disabled.** The Schedule Trigger node
  that is supposed to run the F2-F8 sequence has `disabled: true` in the
  export, and its `interval` parameter is an empty object with no fields set.
  As shipped and as live on n8n, subscribers get the welcome email and
  nothing else automatically; the "8-email nurture sequence" the workflow's
  own sticky note describes only half runs.
- **Sticky-note documentation doesn't match the graph.** The workflow's
  own top-level sticky note claims it "sends WhatsApp welcome message" and
  lists a "WhatsApp Business API credential" as a prerequisite. There is no
  WhatsApp node anywhere in this 31-node export; the welcome step is a Gmail
  node ("Send a message"). The same note also describes the schedule as
  "daily at 9:00 AM UTC," which the actual (disabled, unconfigured) Schedule
  Trigger node does not implement.
- **Every follow-up stage uses an identical time window.** Sticky Note6
  describes the cascade as "Day 2," "Day 3," through "Day 8," implying
  increasing delays per stage. The actual IF node expressions (If2 through
  If8) all check the exact same 3-to-4-day (4320 to 5760 minute) window
  against `Sequence Last Date`, regardless of which stage is being
  evaluated. Whether that's an intentional fixed cadence or a copy-paste
  artifact that was supposed to scale per stage isn't something the JSON
  can answer; it's stated here as what the graph literally does.
- **Update-node names don't match what they update.** "Update F4 1," "Update
  F4 2," "Update F4 3," and "Update F4 4" look like four variations on
  updating the F4 flag, but they actually set F8, F5, F6, and F7
  respectively (confirmed by reading each node's `columns` parameter, not
  its name). Anyone maintaining this graph by node name alone would
  misread which stage each one advances.
- **No validation on webhook input.** The Edit Fields node maps
  `body.name`/`body.email`/`body.phone_number` straight into CRM columns
  with no check that email looks like an email or that required fields are
  present. A malformed submission still creates a CRM row and can still
  trigger a welcome email to whatever the "email" field contained.
- **The cascade only advances on a schedule tick that touches every row.**
  Because "Get row(s) in sheet" has no filter, every run reads the entire
  CRM and re-evaluates all seven IF gates for every contact. That's fine at
  small scale, but there's no batching, pagination, or per-contact indexing;
  it would need rework before this could handle a CRM with many thousands of
  rows.

## What I learned

Reading the IF node expressions directly, rather than trusting the sticky
notes describing the workflow, was the only way to catch that the "Day
2...Day 8" cadence the documentation claims doesn't exist in the actual
conditions; every stage checks the same 3-to-4-day window. It's a reminder
that in-workflow documentation (sticky notes, node names) is a claim about
intent, not a guarantee about behavior, the same way code comments can drift
from the code they describe. The node-naming drift ("Update F4 1" actually
setting F8) was only catchable by reading each node's `columns` parameter,
confirming that in a large n8n graph, names are not a reliable map of
what a node does.

## What I'd do differently

I'd rename the "Update F..." nodes to match the flag they actually set
(Update F8, Update F5, and so on) so the graph is readable at a glance
instead of requiring a parameter-by-parameter audit. I'd fix or remove the
Schedule Trigger so the follow-up half of the sequence either runs as
documented or is clearly marked as not yet wired up, instead of leaving a
disabled node with an empty interval sitting behind a sticky note that
claims it runs daily. I'd also add basic input validation on the webhook
(at minimum, a regex check that `email` looks like an email) before it ever
reaches the CRM write, and I'd either implement genuinely increasing delays
per follow-up stage or update the documentation to stop implying a cadence
the conditions don't enforce.
