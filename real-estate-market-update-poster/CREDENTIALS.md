# Credentials required

- **Google Sheets OAuth2**: used by the trigger node to poll the tracking sheet
  for new topics marked "In Progress," and by the write-back node to update the
  same row with the finished post, image URL, video URL, and status.
- **newsdata.io API key**: used to search for news articles matching the topic
  pulled from the sheet.
- **Google Gemini API key**: used by all three LLM chat model nodes
  (`gemini-2.0-flash-lite`) that generate the social post text, the image
  prompt, and the video prompt.
- **Runware.ai API key**: used to generate the still image from the image
  prompt via Runware's image inference API.
- **Novita.ai API key**: used by both the image-to-video submission call and the
  status-polling call to animate the generated image into a short video.
