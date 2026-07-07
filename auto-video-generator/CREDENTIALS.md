# Credentials

External services this workflow's nodes need, configured in n8n's credential store
(never as hardcoded values in the workflow JSON):

- **Google Sheets**: used by `video_data_from_sheets` to read the source video rows
  (video URLs and captions) from a Google Sheet.
- **Google Gemini API**: used by `Google Gemini Chat Model` as the language model
  behind the caption-generating agent.
- **Creatomate API key**: used by `render_creatomate` and `get_render_status` (as a
  generic HTTP Header Auth credential) to submit and check the status of video
  renders. Also requires a Creatomate template configured with the expected
  `Video-1`, `Text-1`, and `Text-2` layers.
- **Blotato API key**: used by `ready_video_blotato` and `social_app_posts` (sent as
  a `blotato-api-key` header) to upload the rendered video and publish it to a
  connected social account.
- **Blotato account/media IDs**: platform-specific IDs hardcoded in
  `set_blotato_ids`, needed to tell Blotato which connected account to post
  through.
