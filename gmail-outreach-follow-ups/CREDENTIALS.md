# Credentials required

- **Google Sheets OAuth2 credential**: used by every "Get row(s) in sheet", "Append or
  update row in sheet", and "Google Sheets Trigger" node to read and write the
  prospect tracking spreadsheet.
- **Gmail OAuth2 credential**: used by every "Get many messages" and "Reply to a
  message" node to search the sender's Sent folder and reply in-thread to prospects.

Both credentials need access to the same Google account, since the workflow replies
from the account that sent the original outreach message and reads/writes the same
tracking sheet that account owns.

No other external service or API key is used anywhere in this workflow.
