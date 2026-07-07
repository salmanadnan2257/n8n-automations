# Credentials

None. Every node in this workflow is either a built-in n8n trigger/response node or a
community node that runs locally without calling out to any external service:

- Webhook (built-in): receives the incoming HTTP request. No credential.
- UUID Generator (community node, `n8n-nodes-guuid-generator`): generates the UUID
  locally inside n8n. No credential, no external API call.
- Respond to Webhook (built-in): returns the JSON response. No credential.
- Manual Trigger (built-in, disabled in this workflow): lets the workflow be run by
  hand from the n8n editor for testing. No credential.

No API keys, accounts, or external service signups are required to run this workflow.
