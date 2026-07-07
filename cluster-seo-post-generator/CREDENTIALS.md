# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **Google Sheets OAuth2 account**: reads the keyword-cluster sheet (the source of new
  posts) and reads/appends to the completed-posts log sheet.
- **OpenAI-compatible API key(s)**: powers every LLM step (preliminary plan, detailed
  plan, blog draft, internal linking, HTML formatting, slug, title, meta description).
  The original ran this across two separate credentials (an OpenRouter key and a
  direct OpenAI key); one provider covering all referenced model IDs is enough if you
  consolidate.
- **Perplexity API key** (HTTP header auth): powers the research step that finds
  citable sources for the post topic.
- **SerpAPI key** (HTTP query auth): powers the Google Images search used to find a
  cover image.
- **WordPress REST API credential**: publishes the finished post as a draft to the
  target WordPress site.
