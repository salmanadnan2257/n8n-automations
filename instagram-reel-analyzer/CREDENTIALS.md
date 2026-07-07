# Credentials required

- Apify account and API token: used by the "Extract Reels" node to run the
  `apify~instagram-reel-scraper` actor and pull reel stats (views, likes, comments,
  caption, video URL) for the requested Instagram account.
- CloudConvert account and API token: used by the "Get Video" node to import each reel's
  video from its URL, convert it from MP4 to MP3, and export the converted file.
- OpenAI API credential: used by the "Video -> Text" node (`openAi`, resource `audio`,
  operation `transcribe`) to transcribe each reel's converted audio.
- Google Gemini (Google PaLM API) credential: used by the "Google Gemini Chat Model"
  node as the language model backing the "Generate Insights" agent.
- Google Sheets OAuth2 credential: used by "Store Video's Data" to append each reel's
  stats and transcript to a spreadsheet, and by "Store Insights" to append each
  generated performance breakdown to a second tab of the same spreadsheet.

No credential is required for the form trigger itself; it only collects the Instagram
username and reel count typed into the n8n form.
