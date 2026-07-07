# Credentials required

- Google Sheets OAuth2 (n8n credential type `googleSheetsOAuth2Api`): used by the "Google Sheets" node to read the list of search topics, and by the "Store Emails in Sheets" node to append or update each topic's scraped emails. Needs read and write access to the target spreadsheet.

No other external API or credential is used. The Google Maps search and the per-website scraping both run through n8n's built-in HTTP Request node against public pages, with no API key.
