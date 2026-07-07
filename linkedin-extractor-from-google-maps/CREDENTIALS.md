# Credentials required

- **Apify API credential**: used by the "Run an Actor and get dataset(Google Maps)"
  node to run the Google Maps Scraper actor (`compass/crawler-google-places`) and its
  Lead Enrichment add-on. Apify billing applies per actor run and per enriched result.
- **Google Sheets credential (OAuth2)**: used by all four Google Sheets nodes ("Get
  row(s) in sheet1", "Get row(s) in sheet2", "Append or update row in sheet", "Append
  or update row in sheet2", "Update row in sheet") to read and write the "Location" and
  "Leads" tabs of the target spreadsheet.
- **Perplexity API credential**: used by the "Message a model" node to research each
  lead's company and return a Qualified/Disqualified verdict.

The exported workflow JSON does not include credential bindings (n8n's export strips
them), so every node above needs its credential selected manually in the n8n editor
after import.
