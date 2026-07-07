# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **OpenAI API credential**: powers the slide-outline generation agent
  (`gpt-3.5-turbo`).
- **Google Slides OAuth2 credential**: creates the presentation and performs every
  slide-building `batchUpdate` call.
- **Google Sheets OAuth2 credential**: attached to two of the Slides `batchUpdate`
  HTTP Request nodes in the original build; the request bodies for those nodes only
  call the Slides API, so this looks like a carried-over credential rather than an
  active dependency, but n8n will prompt for it on import regardless.
