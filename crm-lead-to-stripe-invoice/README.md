# CRM Lead to Stripe Invoice

## What it is

An n8n workflow that listens for a webhook from a ClickUp CRM automation and, when a
deal is marked "Lead Won," automatically creates a Stripe customer, builds an invoice
item, creates the invoice, and finalizes (sends) it. No manual Stripe work required
after a deal closes.

## Why it exists

Closing a deal in ClickUp and then manually switching to Stripe to create a customer
and an invoice is a repetitive step that's easy to forget or delay. This workflow
removes the manual handoff: the moment a ClickUp task's status changes to "won," the
first deposit invoice is created and sent without anyone touching Stripe.

## Features

- Webhook trigger that accepts the ClickUp automation payload (POST, JSON body).
- Pulls the full ClickUp task, including all custom fields, via the native ClickUp
  node using the task ID from the webhook payload.
- Creates a Stripe customer from the task name and an email pulled out of a specific
  ClickUp custom field.
- Adds a Stripe invoice item with an amount pulled from a ClickUp currency custom
  field, converted from dollars to cents.
- Creates a Stripe invoice set to `send_invoice` collection with a 2 day due date.
- Finalizes the invoice, which triggers Stripe to email it to the customer, with no
  manual finalize step.

## Architecture

Six nodes, one straight chain, no branching:

```
Webhook -> ClickUp -> Stripe -> Create Invoice Item Stripe -> Create Invoice Stripe -> Finalize Invoice Stripe
```

- **Webhook** (`n8n-nodes-base.webhook`, POST): entry point. Expects the ClickUp
  automation to POST a payload shaped like ClickUp's task webhook event, with the
  task ID at `body.payload.id`.
- **ClickUp** (`n8n-nodes-base.clickUp`, operation `get`): fetches the full task by
  ID, including its `custom_fields` array, which is where the deal amount and
  contact email live.
- **Stripe** (`n8n-nodes-base.stripe`, resource `customer`, operation `create`): the
  only step using n8n's native Stripe node. Creates a customer using the task name
  and `custom_fields[19].value` as the email.
- **Create Invoice Item Stripe** (`n8n-nodes-base.httpRequest` to
  `POST /v1/invoiceitems`): a raw HTTP call against Stripe's REST API using
  `predefinedCredentialType: stripeApi` so it reuses the same Stripe credential as
  the native node. Amount comes from `custom_fields[5].value * 100` (dollars to
  cents), description is the hardcoded string `"1st Deposit"`.
- **Create Invoice Stripe** (`n8n-nodes-base.httpRequest` to `POST /v1/invoices`):
  creates the invoice against the customer from the Stripe node, set to
  `auto_advance: true`, `collection_method: send_invoice`, `days_until_due: 2`,
  `pending_invoice_items_behavior: include` so it picks up the invoice item created
  in the previous step.
- **Finalize Invoice Stripe** (`n8n-nodes-base.httpRequest` to
  `POST /v1/invoices/{id}/finalize`): finalizes the invoice, which is what actually
  makes Stripe send it to the customer.

The invoice item, invoice, and finalize steps all go through raw HTTP Request nodes
instead of the native Stripe node. That's a real pattern visible in the JSON; I can't
confirm from the file alone whether it's because n8n's Stripe node lacked invoice
support at the time this was built, but the effect is that customer creation and
invoicing use two different integration styles against the same API.

## Setup

1. An n8n instance (cloud or self-hosted) to import `workflow.json` into.
2. A ClickUp API credential, added in n8n's credential store, then attached to the
   ClickUp node (the credential reference in the JSON won't resolve on import; you
   have to reselect or recreate it).
3. A Stripe API credential, added in n8n's credential store, then attached to the
   Stripe node and all three HTTP Request nodes that use `predefinedCredentialType`.
4. A ClickUp automation on the CRM list, configured to fire "when status changes to
   Lead Won (or whatever the closed-won status is named), send webhook," pointed at
   this workflow's webhook URL once the workflow is active.
5. No environment variables or `.env` file are used. All configuration lives in the
   n8n credential store and the node parameters themselves.

## Usage

Activate the workflow in n8n so its webhook goes live, then wire the ClickUp
automation to call that webhook URL. From that point, every task moved to the
"won" status on the configured ClickUp list triggers the chain automatically: a
Stripe customer is created, an invoice item and invoice are built from the deal's
custom fields, and the invoice is finalized and sent, with no manual step.

## Challenges

1. **Custom fields are read by array index, not by field ID or name.** The Stripe
   node's email expression is `custom_fields[19].value` and the invoice amount
   expression is `custom_fields[5].value * 100`. Both are direct index lookups into
   the `custom_fields` array on the ClickUp task. If anyone reorders, adds, or
   removes a custom field on that ClickUp list, these indexes shift silently, and
   the workflow starts pulling the wrong data into an email or invoice amount field
   with no error thrown. This is a real fragility visible directly in the node
   parameters, not a hypothetical one.
2. **The dollars-to-cents conversion assumes a clean USD amount.** The amount
   expression is `$('ClickUp').item.json.custom_fields[5].value * 100`. Stripe wants
   integer cents. This works for a plain 2-decimal USD number but there's nothing in
   the graph checking the field's currency type or rounding the result, so any value
   with more precision than cents, or a differently configured currency field, would
   produce an invoice amount that's off.
3. **No status check on the trigger itself.** The workflow has no IF or Switch node
   validating that the incoming webhook actually represents a "won" status change
   before it creates a customer and an invoice. It trusts that only the intended
   ClickUp automation ever calls this webhook. If the same webhook URL were reused
   for a different automation, or ClickUp retried a delivery, the workflow would
   process it exactly the same way.
4. **No duplicate protection.** Every node is a single straight chain with no
   idempotency check, no search for an existing Stripe customer by email before
   creating a new one, and no check for an existing invoice for the same deal. A
   webhook retry from ClickUp, or a task accidentally moved to "won" twice, creates
   a second Stripe customer and a second invoice rather than reusing the first.
5. **Hardcoded invoice line description.** The invoice item description is the
   literal string `"1st Deposit"` (not an expression), so every invoice this
   workflow creates carries the same line item text regardless of deal type,
   contract type, or amount.
6. **Mixed integration style against one API.** Customer creation goes through n8n's
   native Stripe node while invoice item creation, invoice creation, and finalizing
   all go through raw HTTP Request nodes hitting the Stripe REST API directly. Both
   paths share the same Stripe credential, but they don't share the native node's
   response normalization, so downstream expressions have to reach into raw Stripe
   API response shapes (for example `$json.id` on the invoice response) rather than
   a normalized n8n output.

## What I learned

Reading this workflow closer made a few things concrete: how n8n's HTTP Request node
can reuse an existing native-node credential type (`predefinedCredentialType` plus
`nodeCredentialType: stripeApi`) to hit endpoints the native node doesn't cover,
without configuring a second credential. Also, that Stripe's invoicing flow is
genuinely three separate REST calls chained together (create the invoice item,
create the invoice against pending items, then finalize it), not a single "create
invoice" call, which explains why this workflow needs three HTTP Request nodes back
to back instead of one.

## What I'd do differently

I'd reference ClickUp custom fields by their field ID (each one has a stable UUID in
the task JSON) instead of array index, so reordering fields on the ClickUp list
can't silently corrupt the invoice amount or the customer's email. I'd add a
Switch node right after the webhook that checks the incoming status is actually the
closed-won status before doing anything else, since nothing currently stops this
chain from running on an unrelated webhook call. I'd also add a lookup step that
searches Stripe for an existing customer by email before creating a new one, so a
retried webhook or a task moved to "won" twice doesn't produce duplicate customers
and duplicate invoices. Finally, I'd pull the invoice line description from a
ClickUp field instead of hardcoding "1st Deposit," since not every deal is actually
a first deposit.
