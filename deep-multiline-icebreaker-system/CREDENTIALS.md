# Credentials

External services this workflow needs configured before it will run. No real values
are stored here or anywhere in this folder.

- **OpenAI API**: used to summarize each scraped website page and to generate the
  final multi-line cold-email icebreaker from the combined summaries.
- **Google Sheets API**: used to read the queue of lead-search URLs (the "Search
  URLs" tab) and to append each processed lead's contact details plus generated
  icebreaker (the "Leads" tab).
- **Apify API**: called directly via an HTTP Request node (bearer token in the
  request header, not stored as an n8n credential) to run an Apify actor that returns
  lead/contact records for a submitted search URL.
