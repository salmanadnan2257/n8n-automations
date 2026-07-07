# Credentials

External services this workflow's nodes need, configured in n8n's credential store
(never as hardcoded values in the workflow JSON):

- **ClickUp API** (`clickUpApi`): used by the ClickUp node to fetch the full task
  details, including custom fields, by task ID.
- **Stripe API** (`stripeApi`): used by the native Stripe node to create the
  customer, and reused via `predefinedCredentialType` by the three HTTP Request
  nodes that create the invoice item, create the invoice, and finalize it.
- **ClickUp automation webhook** (not a credential, but required infrastructure):
  a ClickUp automation on the CRM list must be configured to POST to this
  workflow's webhook URL when a task's status changes to the closed-won state.
