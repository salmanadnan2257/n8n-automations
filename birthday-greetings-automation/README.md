# Birthday Greetings Automation

## What it is

A small n8n workflow, "Happy Birthday Greetings," that receives a webhook call
with a date of birth, checks whether that date matches today, and if so sends a
birthday email either immediately or after a short delay.

## Why it exists

Sending birthday messages by hand doesn't scale past a handful of people, and
it's easy to forget one. This wraps the check-and-send logic behind a webhook so
another system (a CRM, a scheduled cron job that iterates a contact list, an
external database trigger) can call it once per contact with that contact's date
of birth, and it handles the "is it actually their birthday, and if so, send the
email" part.

## Features

- Single webhook endpoint takes a `dob` field and decides whether to send a
  birthday email based on comparing it against the current date.
- Two parallel paths after the date check, one with a short indefinite Wait and
  one with a fixed 10-unit Wait, before both converge on the same email send (see
  Architecture and Challenges for what this actually does versus what it looks
  like it's meant to do).
- Plain-text email send over SMTP.

## Architecture

Node-by-node:

1. **Webhook** (`n8n-nodes-base.webhook`, POST): the entry point. Expects a JSON
   body containing at least a `dob` field (a date string).
2. **If** (`n8n-nodes-base.if`): compares `$now` formatted as `MM-dd` against
   `$json.body.dob` (parsed as a date and reformatted to `MM-dd`) using an
   "afterOrEquals" date comparison. In practice this checks whether today's
   month-day is on or after the birthday's month-day within the same comparison,
   which is a same-day check for `afterOrEquals`, not a reliable birthday match
   (see Challenges: this expression only works cleanly if the workflow runs
   exactly on the birthday, not before or after).
3. **Wait** (true branch, no parameters set): an indefinite wait node with no
   duration configured. As exported, an unparameterized `n8n-nodes-base.wait`
   node defaults to waiting a fixed short interval, but with no explicit
   `amount`/`unit` set, this is effectively an unconfigured placeholder rather
   than a deliberate delay.
4. **Wait1** (false branch, `amount: 10`, no unit specified so it falls back to
   the node's default unit): a second Wait node on the other branch of the If.
   Both the true and false branches of the If lead to a Wait node and then
   converge on the same "Send email" node, meaning this workflow sends the
   birthday email regardless of which branch the If takes, just after a
   different (or unconfigured) delay. That makes the If node currently
   decorative: it doesn't gate whether the email sends, only which Wait node it
   passes through first.
5. **Send email** (`n8n-nodes-base.emailSend`): sends a fixed plain-text message,
   "Happy Birthday, my G! WOOOOOOOO", to a single hardcoded recipient (scrubbed
   to a placeholder in this copy) via SMTP.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials this workflow needs:

- An SMTP credential for the **Send email** node (any SMTP provider).

The webhook itself needs no credential; it's a public POST endpoint by default,
so if you deploy this, put authentication or a shared secret in front of it
yourself (see Challenges).

## Usage

POST a JSON body like `{"dob": "1990-07-07"}` to the webhook URL n8n assigns on
activation. If the month-day matches today, the fixed "Happy Birthday" email
gets sent to whatever address is configured on the Send email node, currently a
single hardcoded recipient rather than the caller's own address.

## Challenges

- **The email recipient and message are hardcoded, not derived from the
  request.** The webhook accepts a `dob`, but nothing in the graph captures a
  name or a per-contact email address from the incoming payload. As exported,
  this only ever emails one fixed address with one fixed message, so it can't
  actually serve more than one person without editing the node directly.
- **The If node doesn't gate the send.** Both its true and false outputs lead to
  a Wait node and then the same Send email node, so the date check doesn't
  currently prevent an email from going out on a non-birthday call; it only
  changes which Wait node is used. Anyone extending this needs to notice that
  before assuming the date logic is actually protecting against false sends.
- **The date comparison itself is fragile.** `afterOrEquals` between today's
  and the DOB's `MM-dd` string only reliably matches when the workflow is
  triggered on the actual day. It doesn't correctly express "is today this
  person's birthday" across year boundaries or when the webhook fires more than
  once a day; a straight equality check on the formatted month-day would be
  more correct than `afterOrEquals`.
- **No authentication on the webhook.** As exported, the webhook path is a bare
  POST endpoint with no header check, no shared secret, and no rate limit. Since
  the node only reads a `dob` field, the worst case is spam sends of the fixed
  email, but this still needs a secret token or n8n's built-in webhook auth
  before it's exposed publicly.
- **The two Wait nodes are inconsistent and one is unconfigured.** "Wait" has no
  amount or unit set (an oversight rather than an intentional indefinite pause),
  while "Wait1" waits for `10` of whatever n8n's default unit is (minutes,
  unless changed). Neither branch's delay is documented anywhere in the
  workflow, so the reason two different delays exist for the "birthday is
  today" vs. "not yet" cases isn't recoverable from the JSON.

## What I learned

Reading connections, not just node types, matters more than expected here: the
If node looks like it should be the gate that decides whether an email sends,
but tracing both of its outputs shows they both terminate at the same Send
email node. A workflow can look conditional from its node list while actually
being unconditional once you check where every branch actually leads.

## What I'd do differently

I'd make the If node's false branch actually terminate the run (a NoOp with
nothing downstream, instead of another path back to Send email), fix the date
comparison to use exact equality on the formatted month-day rather than
`afterOrEquals`, and pull the recipient email and name from the webhook payload
instead of hardcoding them, so the same workflow can serve more than one
contact without edits. I'd also put a shared secret check right after the
Webhook node before doing anything else.
