# Credentials

External services and credentials this workflow's nodes require. No real
values are stored here or in the workflow file; configure these in n8n's own
credential store after import.

- **Apify API token** (HTTP Header Auth credential): authenticates the request
  to the `curious_coder~facebook-ads-library-scraper` actor that scrapes the
  Facebook Ad Library. Used by the "scrape_fb_ads" node.
- **Google Drive OAuth2**: used to upload the downloaded ad images to a Drive
  folder, set that file's public sharing permission, and (optionally) create
  the destination folder. Used by the "upload_files", "Google Drive" (share),
  and "create_folder" nodes.
- **OpenAI API key**: used for both the GPT-4o vision call that describes the
  scraped ad image and the GPT-4o chat call that rewrites that description
  into rebranded change-request prompts. Used by the "OpenAI" and "OpenAI1"
  nodes.
