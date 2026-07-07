# Credentials

External services and credentials required to run this system. No real values are
stored anywhere in this folder; all references in the workflow JSON files are n8n
credential pointers (an id and a display name), not the credentials themselves.

- **Telegram Bot API**: bot token for the Telegram bot that receives user messages
  (text and voice), downloads voice files, and sends responses back to the user.
- **OpenAI API**: used for GPT-4o chat completions in the orchestrator, calendar
  agent, contact agent, and email agent, and for audio transcription of incoming
  voice messages in the orchestrator.
- **Anthropic API**: used for the content creator agent's chat model (Claude), which
  generates the HTML blog post content.
- **Google Calendar OAuth**: used by the calendar agent's Create Event, Create Event
  with Attendee, Get Events, Update Event, and Delete Event tools.
- **Gmail OAuth**: used by the email agent's Send Email, Create Draft, Email Reply,
  Get Emails, Get Labels, Label Emails, and Mark Unread tools.
- **Airtable Personal Access Token**: used by the contact agent's Get Contacts and Add
  or Update Contact tools, against a Contacts base/table.
- **Tavily API key**: used by the web search tool in both the orchestrator and the
  content creator agent. This one is not an n8n credential object: it is sent as a
  literal value in the HTTP Request tool node's JSON body, so it must be pasted in
  directly (or refactored into an expression pulling from an n8n credential) rather
  than attached through n8n's credential picker.
