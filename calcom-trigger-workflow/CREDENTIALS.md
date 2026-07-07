# Credentials required

- **Google Sheets credential**: used by every Google Sheets node (`Update Call
  Scheduled Progress`, `Get row(s) in sheet`, `Update F1 Sheets` through
  `Update F4 `) to read and write the CRM spreadsheet.
- **Gmail credential**: used by all four `Follow-Up` nodes and by `Send a message`
  (the error-alert notification) to send email.
- **Twilio credential**: used by the three `Send an SMS/MMS/WhatsApp message` nodes
  to send confirmation and reminder SMS. Also needs a Twilio phone number to send
  from (replace `YOUR_TWILIO_PHONE_NUMBER` in the workflow file with your own).
- **Cal.com API access**: only needed if you re-enable the disabled `Cal.com Trigger`
  node. As exported, the live entry point is the generic `Webhook` node instead,
  which needs no n8n-side Cal.com credential, but does need Cal.com's own webhook
  settings pointed at this workflow's webhook URL for the `BOOKING_CREATED` event.

No credential objects were present in the exported workflow JSON (the n8n API this
was pulled from does not return credential bindings), so credential names/IDs aren't
listed here; assign each node its credential after import.
