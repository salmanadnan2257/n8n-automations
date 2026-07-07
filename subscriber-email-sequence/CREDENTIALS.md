# Credentials required

- **Header Auth credential** (n8n's built-in header-auth type): used by the
  **Webhook** node to check an `Authorization` header on every inbound request
  before the workflow runs. Set this to whatever shared secret your form or
  intake system will send.
- **Google Sheets OAuth2 credential**: used by the **Append or update row in
  sheet**, **Append or update row in sheet1**, **Get row(s) in sheet**, and all
  seven **Update F...** nodes to read and write the CRM spreadsheet that tracks
  each contact's sequence progress (name, email, phone, and F1 through F8
  status flags).
- **Gmail OAuth2 credential**: used by the **Send a message** node (the initial
  welcome email) and all seven **Follow-Up** nodes (F2 through F8) to send
  email through a Gmail account.

No SMS, WhatsApp, or other messaging credential is required despite what the
workflow's own sticky-note documentation claims (see README, Challenges). Every
outbound message in this graph, including the "welcome" step, goes out through
the Gmail node.

A real Google Sheet with the CRM's column layout (Full Name, First Name, Last
Name, Contact Email, Contact Phone, Started Sequence?, Closed?, Contract Sent?,
Contract Signed?, F1? through F8?, Sequence Last Date) needs to exist and be
pointed at by `documentId`/`sheetName` in the Google Sheets nodes; the id shipped
in `workflow.json` is a placeholder.
