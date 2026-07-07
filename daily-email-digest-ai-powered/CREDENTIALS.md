# Credentials

This workflow needs the following external accounts and credentials configured inside
n8n's credential store (Credentials menu, not in this repo). No real values are ever
stored here.

- **Gmail OAuth2 account**: used by both the "Get Emails" node (reads the last 24
  hours of mail) and the "Send Digest (With Attachments)" / "Send Digest (No
  Attachments)" nodes (sends the compiled digest). Needs Gmail read and send scopes.
- **Google Vertex AI credentials (service account or OAuth2)**: used by the "Google
  Vertex Chat Model" node, which runs Gemini 2.5 Pro as the primary summarization
  model for both the per-batch and master-summary steps.
- **Google Gemini (AI Studio) API key**: used by the "Google Gemini Chat Model" node
  (gemini-2.5-flash), wired in as the fallback model if the Vertex call fails.
- **Recipient email address(es)**: the "Send Digest" nodes need at least one
  destination address configured in the `sendTo` field. The copy in this repo has
  this replaced with `YOUR_EMAIL_ADDRESS_HERE`.
