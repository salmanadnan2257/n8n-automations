# Credentials

External services and credentials the workflow's nodes reference. No real values
are stored here or in the workflow file, only n8n credential pointers.

- **Google Gemini (Google PaLM API) credential**: used by the Google Gemini Chat
  Model node as the language model that writes each quote.
- **OpenAI API credential**: used by the OpenAI node (image resource, model
  `gpt-image-1`) to turn the generated quote text into an image.
- **Telegram API credential (bot token)**: used by the Telegram node to send the
  generated image as a photo to a chat.
