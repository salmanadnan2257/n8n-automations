# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **Google Sheets OAuth2 account**: reads the tracked-channels list and writes back
  updated stats/growth numbers each run.
- **YouTube Data API credential (OAuth2)**: powers both YouTube tool nodes (get a
  channel, list a channel's videos). Requires the YouTube Data API enabled on the
  underlying Google Cloud project.
- **OpenAI API credential**: powers the Channel Agent's language model. The unbuilt
  Video Agent would need this too once its tools and prompt are filled in.
