# Cal.com Trigger Workflow

## What it is

An n8n workflow named "Cal.com Trigger Workflow" that turns a Cal.com booking into a
tracked CRM row and a four-stage email/SMS follow-up sequence, from confirmation right
through to "your call is starting now." It has two independent entry points that feed
the same downstream logic: a real-time booking event, and a Schedule Trigger that
polls every 10 minutes to send timed reminders.

## Why it exists

Booking a call is only the first step, someone still has to remember to confirm it,
remind the attendee the day before, remind them again an hour out, and nudge them five
minutes before it starts, and log all of that into a CRM sheet without missing a step.
This workflow does that mechanically: one path reacts to the booking itself, the other
runs on a timer checking every scheduled call's row against its start time and firing
whichever reminder is due, then flags that reminder as sent so it never repeats.

## Features

- Writes a new CRM row (Google Sheets) the moment a booking comes in: contact details,
  company name, stated interest, notes, guests, and the Google Meet link, all pulled
  straight out of the booking payload.
- Sends an immediate confirmation email and SMS naming the date, time, and meeting
  link.
- Polls the CRM sheet every 10 minutes and sends up to three more reminders per
  booking, each gated by a time window and a "have I already sent this one" flag
  (`F2?`, `F3?`, `F4?`) so a reminder never goes out twice.
- Two of the three timed reminders also send an SMS, but only if the row actually has
  a phone number; the third (the roughly-one-hour reminder) is email-only.
- A single organizer-name check filters out any booking that isn't for this specific
  business before it touches the CRM at all.
- A workflow-wide Error Trigger emails an internal alert list if any node in the run
  fails.

## Architecture

Node-by-node, following the actual `connections` graph (node names below match the
export exactly, including n8n's own auto-numbering of duplicate node names like
`Follow-Up  4` and `If5`):

### Path 1: real-time booking

1. **Cal.com Trigger** (`n8n-nodes-base.calTrigger`, event `BOOKING_CREATED`, event
   type ID `2926528`): present in the graph, wired straight into `If`, but its
   `disabled` flag is `true`, so it does not currently run.
2. **Webhook** (`n8n-nodes-base.webhook`, POST, path `ee86d2ec-2714-4a49-a7cd-36de3ebfdbf0`):
   a generic webhook wired into the same `If` node as the disabled trigger above. Since
   the native Cal.com Trigger node is off, this is the node that has to be receiving
   the live booking events, most likely via a webhook configured directly in Cal.com's
   own account settings pointing at this URL, rather than through n8n's built-in
   Cal.com integration. That configuration lives on Cal.com's side and isn't visible in
   this export.
3. **If**: checks `organizer.name` equals exactly `"Digitalise Agency"`. True goes to
   step 4; false goes to **No Operation, do nothing**, meaning any booking for a
   different organizer on the same Cal.com account (if there is one) is silently
   dropped here with no CRM row and no notification.
4. **Update Call Scheduled Progress** (Google Sheets, `appendOrUpdate`): writes a new
   row keyed on contact email: start/end time, first/last/full name, company name,
   website, stated interest, prep notes, additional notes, guest list, the Google Meet
   link, `Call Scheduled? = true`, and every sequence flag (`F1?` through `F4?`,
   `Proposal sent?`, `Closed?`, `Contract Sent?`, `Contract Signed?`) initialized to
   `false`.
5. **Follow-Up 1** (Gmail): sends the confirmation email, referencing the booking data
   by explicit node name, `$('Cal.com Trigger').item.json...`, not `$json`.
6. **Send an SMS/MMS/WhatsApp message** (Twilio): sends the matching confirmation SMS,
   also reading straight from `$('Cal.com Trigger')`. There is no check here for
   whether the attendee's phone number is actually present before this fires.
7. **Update F1 Sheets** (Google Sheets): sets `F1? = true`, `Started Sequence? = true`,
   and stamps `Sequence Last Date` with the current time.

### Path 2: scheduled reminders

1. **Schedule Trigger** (every 10 minutes) or **When clicking 'Execute workflow'**
   (manual trigger, for testing) both feed into the same node:
2. **Get row(s) in sheet** (Google Sheets): fetches every row where
   `Call Scheduled? = true`.
3. **If1**: keeps only rows where `Start Time` is not empty (a guard against malformed
   or partial rows).
4. **If2**: true when the minutes until the call's start time are between 120 and 1440
   (2 to 24 hours out) and `F2?` is not yet true. Given the 10-minute poll, this first
   fires close to the 24-hour mark and stays eligible until 2 hours out, but the `F2?`
   flag stops it firing more than once.
   - True: **Follow-Up 2** (Gmail reminder, also carbon-copies any `Guests` on the
     row) then **If5** (does `Contact Phone` have a value?) then, if yes,
     **Send an SMS/MMS/WhatsApp message1** (Twilio, with inline JS that strips
     non-digit characters and normalizes a leading `00` to `+`) before
     **Update F2 Sheets**; if no phone, it goes straight to **Update F2 Sheets**.
   - False: falls through to **If3**.
5. **If3**: true when minutes-to-start are between 11 and 60 and `F3?` is false, so
   this fires around the one-hour mark. True routes to **Follow-Up 3** (Gmail only,
   subject line literally computes and states the exact minutes remaining) then
   **Update F3**. Unlike If2 and If4, this branch has no phone check and sends no SMS.
   False falls through to **If4**.
6. **If4**: true when minutes-to-start are between 0 and 10 and `F4?` is false, firing
   in the final ten minutes before the call. True routes to **Follow-Up  4** (Gmail,
   "starting in 5 minutes") then **If6** (phone check) then, if yes,
   **Send an SMS/MMS/WhatsApp message2** before **Update F4 **; if no phone, straight
   to **Update F4 **. If this last condition is also false, the branch ends in an
   empty connection: the row is left untouched until the next 10-minute poll.

### Workflow-wide error handling

**Error Trigger** fires on any node failure anywhere in this workflow and feeds
**Send a message** (Gmail), which emails a short alert to an internal distribution
list. The workflow's own settings also name this same workflow as its `errorWorkflow`,
so it is configured to catch its own failures.

### A note on "Cal.com" naming that isn't the live path

Every downstream node in Path 1 (`Update Call Scheduled Progress`'s `Contact Phone`
field, `Follow-Up 1`, and the first Twilio node) reads booking data through an
explicit reference to the node named `Cal.com Trigger`, not the generic `$json` that
would follow the actual incoming connection. In n8n, `$('NodeName')` only returns data
if that specific node ran during the current execution. Since `Cal.com Trigger` is
disabled and the graph shows a separate `Webhook` node feeding the same `If`, it's not
possible to confirm from this export alone whether those `$('Cal.com Trigger')`
references still resolve correctly when the `Webhook` node is the one that actually
receives the event. This reads like the workflow was originally wired to the native
Cal.com Trigger node, then switched to a plain webhook without updating the downstream
expressions, but that is inference, not something this export can confirm; testing it
live was not done here.

## Setup

1. In n8n: Workflows menu > Import from File, pointing at `workflow.json`.
2. Configure credentials (see CREDENTIALS.md): a Google Sheets credential, a Gmail
   credential, and a Twilio credential.
3. Replace `YOUR_GOOGLE_SHEET_ID_HERE` (it appears in every Google Sheets node) with
   your own spreadsheet ID. The sheet needs at minimum the columns this workflow reads
   and writes: `Contact Email`, `Call Scheduled?`, `Start Time`, `End Time`,
   `First Name`, `Last Name`, `Full Name`, `Company Name`, `Website (Optional)`,
   `Main Interest`, `Preparation Notes`, `Additional Notes`, `Guests`,
   `Contact Phone`, `Location`, `Proposal sent?`, `Closed?`, `Contract Sent?`,
   `Contract Signed?`, `F1?`, `F2?`, `F3?`, `F4?`, `Started Sequence?`,
   `Sequence Last Date`.
4. Replace `YOUR_TWILIO_PHONE_NUMBER` (three Twilio nodes) with your own Twilio
   sending number.
5. Replace the alert addresses in the **Send a message** node with your own
   error-notification recipients.
6. If you want the real-time path live, either re-enable and configure the
   **Cal.com Trigger** node (event type ID `2926528` in this export, replace with your
   own), or point a Cal.com webhook at this workflow's **Webhook** node URL for the
   `BOOKING_CREATED` event and reconcile the `$('Cal.com Trigger')` references
   described above so they read from whichever node actually receives the data.
7. Set the workflow to Active.

## Usage

Once active, it needs no manual triggering: bookings for the configured organizer
trigger Path 1 automatically, and the Schedule Trigger drives Path 2 on its own every
10 minutes. The manual trigger node exists only to let someone re-run the reminder
scan on demand from the n8n editor while testing.

## Is this connected to booking-time-utility-set?

Both this workflow and the `book-available-time.json` workflow in
`booking-time-utility-set` hardcode the exact same Cal.com `eventTypeId`, `2926528`.
That is real, concrete evidence they target the same underlying Cal.com event type:
a booking made through `booking-time-utility-set`'s "Book Available Time" workflow
would be a booking against the same appointment type this workflow's (disabled)
Cal.com Trigger is configured to listen for.

Beyond that shared ID, there is no direct reference between the two: no shared
webhook path, no shared credential name, and no node in either project that calls into
the other by URL or workflow ID. `booking-time-utility-set`'s three workflows call
Cal.com's REST API directly to check availability and create bookings; this workflow
is what would react afterward, if its native Cal.com Trigger were turned on, or if
Cal.com's own webhook settings are pointed at this workflow's `Webhook` node instead.
Whether that live wiring actually exists on the Cal.com account side is outside what
either exported JSON file can show, so this README states the one fact the graphs
prove (the shared event type ID) and stops there rather than assuming a live
connection.

## Challenges

- **A disabled native trigger sitting next to a live generic webhook, with downstream
  expressions still pointing at the disabled one.** As described above, Path 1's
  Gmail and Twilio nodes reference `$('Cal.com Trigger')` by name even though that
  node is disabled. Reading the graph alone cannot confirm whether this still works
  under the currently-active `Webhook` node; it would need to be tested against a real
  Cal.com booking event to know for sure.
- **The confirmation SMS has no phone-number guard.** `Send an SMS/MMS/WhatsApp
  message` (the booking-confirmation Twilio node) fires unconditionally, unlike its
  two reminder counterparts, which are each gated behind an `If` node that checks
  `Contact Phone` is not empty first. If an attendee books without a phone number,
  this node has nothing to send to.
- **A stray character in a stored field.** The `Contact Phone` column mapping in
  `Update Call Scheduled Progress` is set to `='{{ $('Cal.com Trigger')...}}`,
  an `=` expression prefix followed by a literal single-quote character before the
  `{{ }}` expression. Read literally, that leading apostrophe is not part of the
  expression and gets written into the sheet ahead of the actual phone number.
- **One reminder stage skips the SMS gate the other two use.** `If2` and `If4` both
  check `Contact Phone` before sending an SMS; `If3`, the roughly-one-hour reminder,
  has no such branch and only ever sends email. Whether that's a deliberate choice
  (maybe to keep the message count reasonable) or a gap next to the two nodes it sits
  between isn't stated anywhere in the graph.
- **Sticky-note documentation drifted from the actual time windows.** The sticky
  notes label Follow-Up 3 "5-Minute Alert" and Follow-Up 4 "Call Started
  Notification," but the actual `If` conditions and the email/SMS copy in those two
  nodes put Follow-Up 3 at roughly one hour before the call and Follow-Up 4 in the
  final ten minutes ("starting in 5 minutes"). Anyone reading only the sticky notes
  would get the timing wrong.
- **No end state once all four reminders are sent.** Nothing clears `Call Scheduled?`
  or otherwise stops the row from being re-fetched every 10 minutes indefinitely.
  Once `F4?` is true, `If4` is simply false forever and the row falls through the
  final empty connection each cycle, harmless but an ever-growing sheet gets rescanned
  in full every ten minutes with no upper bound.

## What I learned

The clearest lesson here is that a disabled node in n8n does not mean "dead code" the
way a commented-out line would; other nodes can still reference it by name, and
whether that reference resolves depends entirely on whether that specific node ran in
the current execution, not on whether it's drawn in the same picture. Reading the
`connections` object side by side with which nodes are `disabled` was the only way to
notice that Path 1 has two competing entry points feeding the same `If`. I also found
it useful to check an `If` node's actual `leftValue`/`rightValue`/`operator` fields
rather than trust the sticky note sitting next to it: the sticky notes here describe
timings that don't match what the expressions actually compute.

## What I'd do differently

I would replace every `$('Cal.com Trigger')` reference in Path 1 with plain `$json`
(or an explicit reference to whichever node is confirmed live), so the workflow
doesn't silently depend on a disabled node's name resolving correctly. I would add
the same phone-number check the two reminder SMS nodes already use in front of the
confirmation SMS, and fix the stray leading apostrophe in the `Contact Phone` mapping.
I would also add the missing SMS branch to `If3` if that omission wasn't deliberate,
and update the sticky notes to state the real time windows instead of labels that
no longer match the logic underneath them.
