# Credentials required

- **ScrapeGraphAI API**: used by the four `n8n-nodes-scrapegraphai.scrapegraphAi` nodes ("AI Social Trend Scraper", "AI Google Trends Scraper", "AI Viral Content Analyzer", "AI Reddit Insights Scraper") to run AI-driven scraping and extraction against social platforms, Google Trends, BuzzSumo, and Reddit.
- **Slack API**: used by the "Team Notification Sender" node to post the daily trend report message to a Slack channel.
- **Google Sheets OAuth2**: used by the "Content Calendar Updater" node to append new rows to a content calendar spreadsheet.

No credential objects are present in the workflow JSON itself (the four scraper nodes and the Slack/Sheets nodes carry no `credentials` block), so which named credential entry in an n8n instance would map to each node cannot be verified from this file alone. Each node needs the credential type above assigned to it after import, before the workflow can run.
