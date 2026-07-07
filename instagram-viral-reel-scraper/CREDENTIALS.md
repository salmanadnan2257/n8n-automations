# Credentials required

- OpenAI API key (used by the "OpenAI" audio transcription node and the "OpenAI Chat Model" node backing the AI Agent; referenced in this file only as a credential pointer named "Open AI Arete Key", no key value present).
- Google Sheets OAuth2 credential (used by both "Google Sheets1" and "Google Sheets2" append nodes; referenced only as a credential pointer named "Google Sheets account", no token present). Neither node has a target spreadsheet ID or sheet name saved in this file.
- CloudConvert API key (used by "HTTP Request4" to call `https://sync.api.cloudconvert.com/v2/jobs`; the Authorization header is saved as an empty "Bearer " value, so no key is present in this file, but a real key is required to run it).
- Third-party Instagram scraping API of some kind (used by "HTTP Request", the first HTTP call in the chain). The node has no URL, headers, or credential saved in this file, so the specific provider (Apify, RapidAPI, or another service) could not be identified. Whoever configures this workflow will need to supply that endpoint and its authentication.
