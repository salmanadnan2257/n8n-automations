# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **SerpAPI key** (HTTP query auth): powers both the Google Trends lookup (finding
  rising/top queries) and the Google Images search used to find a cover image.
- **OpenAI-compatible API key(s)**: powers every LLM step (topic selection, research-
  link cleanup, writing, internal linking, HTML formatting, slug, title, meta
  description). The original ran this across two separate credentials (an OpenRouter
  key and a direct OpenAI key); one provider covering all referenced model IDs is
  enough if you consolidate.
- **Perplexity API key** (HTTP header auth): powers the research step that finds
  citable sources for the chosen trending topic.
- **Google Sheets OAuth2 account**: reads and appends to the shared completed-posts
  log sheet used for internal linking and tracking.
- **WordPress REST API credential**: publishes the finished post as a draft to the
  target WordPress site.
