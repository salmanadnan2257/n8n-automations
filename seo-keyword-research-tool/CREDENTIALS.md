# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **DataForSEO account and API credential** (HTTP header auth): powers all six
  research HTTP Request nodes (related keywords, keyword suggestions, keyword ideas,
  autocomplete, subtopics, SERPs/People Also Ask).
- **Google Sheets OAuth2 account**: reads the Main Keyword input row and appends
  results to the per-run results sheet's seven tabs.
- **Google Drive OAuth2 account**: creates the per-run results folder and copies the
  results-sheet template into it at the start of each run.
