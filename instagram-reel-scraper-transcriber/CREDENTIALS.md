# Credentials required

- Apify API token: used by the Run Actor Synchronously node (passed as a manual
  `Authorization: Bearer ...` header, not an n8n credential type) to run the Instagram
  Reel scraping actor.
- Google Sheets OAuth2: used by Search for Entries, Add Entries, and Update Entries to
  read and write the Instagram Reel Database sheet.
- OpenAI API: used by Transcribe Video (Whisper transcription), Filter & Generate
  Suggestions, and Write New Script (both GPT-4o).
- Perplexity API key: used by Search Perplexity (passed as a manual
  `Authorization: Bearer ...` header, not an n8n credential type) to fetch supporting
  facts about the tool identified in a transcript.
