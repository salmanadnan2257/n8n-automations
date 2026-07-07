# Booking Time Utility Set

## What it is

Three separate n8n workflows, each triggered by its own webhook, that together form a
small scheduling API: one returns a near-term list of open appointment slots, one
checks whether a specific slot a caller wants is actually open, and one books a chosen
slot. All three call the Cal.com v2 API for the real availability and booking data,
and all three were also built with a parallel, currently disabled, path for the
Calendly API that never went live. Because every caller can be in a different time
zone, each workflow does its own timezone offset math using the caller's reported
local clock time against the workflow's own UTC clock, rather than relying on a fixed
timezone setting.

## Why it exists

A booking-capable chat agent or another automated system needs three separate
capabilities to run a full "check availability, then book" conversation: list what's
open soon, confirm a specific requested time is actually free, and commit to a
booking once the human picks one. Each of those is a distinct HTTP call with distinct
inputs and outputs, so instead of one workflow branching on an operation parameter,
this project splits them into three independent webhook-triggered workflows that any
orchestrator (a voice agent, a chatbot, another n8n workflow) can call directly by
hitting the right URL with the right body.

## Features

- **Get Available Times**: returns open slots for a fixed near-term window (2 to 5
  days out from the moment the webhook fires), converted into the caller's local
  time, plus which weekday that window starts on.
- **Specific Available Booking Times**: takes a caller-supplied preferred time (in
  the caller's local time) and returns nearby open slots (from 30 minutes before that
  time to 3 days after), so a caller can check "is my preferred time actually open,
  and what's close to it" in one call.
- **Book Available Time**: takes a caller-supplied booking time, a name, an email, a
  phone number, and a reason, converts the booking time to UTC, books it against
  Cal.com, and returns a plain success/fail JSON response, distinguishing an actual
  API error message from a clean success.
- Manual timezone reconciliation in every workflow: each one computes the hour
  difference between the server's own UTC clock and a caller-reported local clock,
  then uses that difference to convert times in both directions (local to UTC before
  calling the API, UTC back to local before responding), without ever setting the
  workflow's own timezone to the caller's.
- A disabled, parallel Calendly integration node group (account lookup, event type
  lookup, and an available-times call) present in all three workflows but not wired
  into the active path, alongside the one Cal.com integration that is actually live.

## Architecture

All three files are independent n8n workflows; they do not call each other, and there
is no orchestrator workflow among the three files here. Each is meant to be called
directly, over its own webhook, by an external system such as a voice or chat agent
that needs booking capability. They share the same event type ID on Cal.com and the
same Calendly event type URI in their disabled nodes, meaning they all target the
same underlying calendar and appointment type; they are three views onto one
bookable resource, not three unrelated schedules.

**get-available-times.json ("Get Available Times")**

1. `Webhook1` (`n8n-nodes-base.webhook`, POST) is the entry point. A disabled
   `n8n-nodes-base.manualTrigger` node exists alongside it for manual testing inside
   the n8n editor.
2. `Set Date and Time` (`n8n-nodes-base.set`) computes `start_time` (now + 2 days,
   UTC midnight) and `end_time` (now + 5 days, UTC midnight), and also carries
   forward `current_time` (the workflow's own UTC now) and `time_there` (read from
   the webhook body's `current_time` field, the caller's self-reported local clock).
3. `Get Available Times - Cal.com` (`n8n-nodes-base.httpRequest`) calls Cal.com's
   `GET /v2/slots` with `eventTypeId`, `start`, and `end` query parameters and a
   `cal-api-version` header. This is the only live availability call; a matching
   `Get Available Times - Calendly` node exists but is disabled.
4. `Split Out` (disabled, so it passes its input through unchanged) feeds
   `Hours Difference` (`n8n-nodes-base.dateTime`, `getTimeBetweenDates`), which
   computes the hour gap between the workflow's `current_time` and the caller's
   `time_there`, i.e. the caller's UTC offset.
5. `Add Hours Difference` (disabled, passthrough) feeds `Code`
   (`n8n-nodes-base.code`, JavaScript, run once per item): this parses Cal.com's raw
   `/v2/slots` response (a dictionary keyed by date, each value an array of slot
   objects with a `start` field), and for every slot adds the hour offset from step 4
   to shift each UTC slot time into the caller's local wall-clock time, collecting
   the results into an `adjusted_result` array.
6. `Aggregate` (disabled, passthrough) feeds `Days Difference`
   (`getTimeBetweenDates`, `current_time` vs `time_there`), then `Add Days Difference`
   adds that day count to `start_time` to get `new_date`, and `Get Day`
   (`formatDate`, custom format `cccc`) turns that into a weekday name.
7. `Return Variables` (`n8n-nodes-base.set`) builds the final response: `reference`
   (a string like "2025-08-01 is Friday") and `adjusted_result` (the localized slot
   times from step 5).
8. `Respond to Webhook` (`respondWith: allIncomingItems`) returns that item as the
   HTTP response.

**specific-available-booking-times.json ("Specific Available Booking Times")**

Same overall shape as Get Available Times, with the query window anchored to a
specific caller-requested time instead of a fixed near-term range:

1. `Webhook` receives `preferred_time` and `current_time` in the body.
2. `Initial` (`n8n-nodes-base.set`) stores `preferred_time`, `time_there` (the
   caller's reported current time), and the workflow's own UTC `current_time`.
3. `Hours Difference` computes the hour gap between `time_there` and `current_time`
   (note the operands are in the opposite order from Get Available Times' equivalent
   step), and `Add Hours Difference` applies that offset to `preferred_time` to
   convert it from the caller's local time into UTC, producing `new_time`.
4. `Set Date and Time` builds a query window from 30 minutes before `new_time` to 3
   days after it, so the workflow checks availability around the specific time the
   caller asked for, not a fixed calendar range.
5. `Get Available Times - Cal.com` calls the same `/v2/slots` endpoint with that
   window. `Split Out`, `Hours Difference2`, and `Add Hours Difference3` are all
   disabled passthroughs (`Hours Difference2` and `Add Hours Difference3` are unused
   duplicates left in the graph; the live `Code` node instead reuses the original
   `Hours Difference` node from step 3 by name).
6. `Code` runs the same slot-flattening logic as Get Available Times but subtracts
   the hour offset instead of adding it, converting the returned UTC slots back into
   the caller's local time (the sign is reversed here because the earlier step
   already flipped local-to-UTC in the other direction).
7. `Aggregate` (disabled, passthrough), `Days Difference`, `Add Days Difference`,
   `Get Day`, `Return Variables`, and `Respond to Webhook` work exactly as in Get
   Available Times, producing a weekday `reference` string and the localized
   `adjusted_result` slot list.

**book-available-time.json ("Book Available Time")**

1. `Webhook` receives `booking_time`, `name`, `email`, `phone_number`, and `reason`
   in the body, plus `current_time` (the caller's local clock).
2. `Initial` stores `booking_time`, `time_there`, and the workflow's own UTC
   `current_time`.
3. `Hours Difference` computes the hour gap between `current_time` and `time_there`.
   `Add Hours Difference` applies that offset, negated, to `booking_time`, converting
   it from the caller's local time to UTC as `new_time`.
4. `Set Date & Time` rounds `new_time` to the start of the hour after adding 30
   minutes (snapping the requested time to an hour boundary) and carries forward
   `name`, `email`, `phone_number`, and `reason` from the webhook body.
5. `Book Time` (`n8n-nodes-base.httpRequest`, `onError: continueErrorOutput`) POSTs
   to Cal.com's `POST /v2/bookings` with the attendee's name, email, phone number,
   the UTC booking time, the shared event type ID, a fixed Google Meet location, and
   the caller's stated reason passed through Cal.com's custom booking fields.
6. On success, `Success Response` sets `response: success`, and `Respond Success`
   returns `{"response": "success", "error": "None"}`.
7. On error, `Error Status` extracts the HTTP status and Cal.com's `error.description`
   from the failed call. An `If` node checks whether that description contains "User
   either already has booking at this time or is not available", but both its true
   and false branches connect to the same `Respond Fail` node, so the check does not
   currently change what the caller receives either way; `Respond Fail` always
   returns `{"response": "fail", "error": "<Cal.com's error description>"}`.
8. A separate `Reserve Time` node (`POST /v2/slots/reservations`, Cal.com's two-step
   reserve-then-book pattern) exists in the graph but is disabled and has no outgoing
   connections wired to the rest of the flow. It reads as an earlier, abandoned
   attempt at reserving a slot before booking it, left in place but not active.

## Setup

1. In n8n: Workflows menu > Import from File. Import `get-available-times.json`,
   `specific-available-booking-times.json`, and `book-available-time.json`
   separately, one import per file. They do not depend on each other at import time.
2. Accounts and credentials needed (see CREDENTIALS.md for the full list):
   - A Cal.com account with API v2 access, for the availability and booking calls
     that are actually active in all three workflows.
   - A Calendly account with API access, only if you plan to finish and re-enable the
     disabled Calendly nodes present in all three workflows; not required to run them
     as shipped.
3. Each workflow's `Get Available Times - Cal.com` (or `Book Time`) node has a fixed
   `eventTypeId` (Cal.com) and a fixed Calendly event type URI hardcoded into it. Both
   point at one specific appointment type on the original Cal.com and Calendly
   accounts; replace these with your own event type's ID and URI after import.
4. Each workflow has its own webhook path baked into its `Webhook` node. n8n
   generates a new production URL for each after import; use n8n's webhook node UI
   to copy the live URL for whatever system will call it.
5. Set each workflow to Active once its credentials and event type IDs are updated.

## Usage

Each workflow expects a JSON POST body and returns JSON. Based on what each graph
actually reads from `$json.body`:

- **Get Available Times**: POST `{ "current_time": "<ISO 8601 local time>" }`.
  Returns `{ "reference": "<date> is <weekday>", "adjusted_result": [<local slot
  times>] }` for a fixed 2-to-5-day-out window.
- **Specific Available Booking Times**: POST `{ "preferred_time": "<ISO 8601 local
  time>", "current_time": "<ISO 8601 local time>" }`. Returns the same shape as
  above, but for a window from 30 minutes before `preferred_time` to 3 days after it.
- **Book Available Time**: POST `{ "booking_time": "<ISO 8601 local time>",
  "current_time": "<ISO 8601 local time>", "name": "...", "email": "...",
  "phone_number": "...", "reason": "..." }`. Returns `{ "response": "success",
  "error": "None" }` on a successful booking, or `{ "response": "fail", "error":
  "<Cal.com's error message>" }` on failure.

In all three, `current_time` is the caller's own local wall-clock time at the moment
of the call; the workflow diffs it against its own UTC clock to work out the caller's
offset, so a caller that sends its local time inaccurately will get times converted
against the wrong offset.

## Challenges

- **Doing timezone conversion by hand, three times, with inconsistent sign
  conventions.** Every workflow computes an hour offset by diffing the caller's
  reported local time against the workflow's own UTC time, then adds or subtracts
  that offset to convert times. Get Available Times adds the offset when localizing
  Cal.com's UTC results; Specific Available Booking Times subtracts it in the
  equivalent step, and separately computes the local-to-UTC offset with the diff
  operands in the opposite order from Get Available Times; Book Available Time
  negates the offset again in its own local-to-UTC step. None of the three share a
  single conversion helper, so each one's correctness depends on its own hardcoded
  sign, which is easy to get backwards during a future edit.
- **No timezone validation on the caller's input.** Every workflow trusts the
  `current_time` field in the incoming webhook body as ground truth for the caller's
  offset. There is no check that this value is well-formed, current, or even
  plausible (for example, off by a day). A caller sending a stale or wrong
  `current_time` silently produces wrong slot times or a wrong booking time with no
  error surfaced anywhere in the graph.
- **A conditional branch that doesn't actually branch.** In Book Available Time, the
  `If` node checks whether the Cal.com error message matches a specific "already
  booked" string, but both its true and false outputs connect to the same
  `Respond Fail` node. Whatever this check was meant to do differently for that
  specific error (a friendlier message, a retry, a suggestion of nearby times) never
  happens; the workflow currently treats every booking failure identically regardless
  of cause.
- **An abandoned two-step booking path left in the graph.** `Reserve Time` calls
  Cal.com's slot-reservation endpoint, which exists to hold a slot briefly before
  confirming a booking, but it's disabled and disconnected from the rest of the flow.
  `Book Time` books directly with a single call instead. The reserve step was
  apparently tried and dropped, but the node (and its own credential pointer) is
  still sitting in the file, which is exactly the kind of half-finished branch that
  is easy to mistake for live logic when reading the graph later.
- **A second integration built, then never turned on.** All three workflows include
  a full Calendly path: an account lookup (`user_uri`), an event type lookup
  (`event_uri`), and an availability call (`Get Available Times - Calendly`), each
  wired to feed the next and each disabled. Cal.com is the only integration that
  actually runs. Nothing in the workflow indicates why Calendly was dropped in favor
  of Cal.com, or whether the disabled path is still meant to be finished later.
- **Slot rounding is a fixed rule with no visibility into why.** Book Available Time
  snaps the requested booking time to the start of the hour after adding 30 minutes,
  which only makes sense if the underlying event type's slots are aligned to the
  hour; there's no comment or check confirming that assumption, so a differently
  configured event type (say, 20-minute slots) would silently get booked at the
  wrong time.

## What I learned

Splitting a multi-step API capability (check availability, check a specific slot,
book) into separate single-purpose webhook workflows makes each one easy to reason
about in isolation, but it also means any shared logic, timezone offset math here,
has to be either duplicated correctly in every copy or centralized in a
sub-workflow; duplicating it three times with three different sign conventions is
exactly the failure mode that centralizing it would have prevented. I also learned
that n8n's "disabled node passes its input through unchanged" behavior is easy to
lean on for quick experiments (several nodes here, like `Split Out` and `Aggregate`,
are disabled no-ops left in the live path), but it makes the graph harder to read
later because a disabled node still shows up as if it does something.

## What I'd do differently

I would pull the offset calculation and both directions of time conversion into one
shared sub-workflow called by all three, so there is exactly one place that decides
whether the offset gets added or subtracted, instead of three independently
maintained copies. I would remove the disabled Calendly nodes and the disconnected
`Reserve Time` node once it was clear they weren't going to be finished, rather than
leaving unused branches in a workflow meant to be read by someone else later. I would
also fix the `If` node in Book Available Time so a caller actually gets a different,
more useful response when the failure is "already booked" versus any other Cal.com
error, since right now the check runs but changes nothing about what's returned.
