# Credentials

External services this workflow needs. No real values are stored anywhere in this
project; add your own where noted.

- **ScreenshotOne API access key**: authenticates the screenshot request. This service
  expects the key directly in the request URL's query string rather than through an
  n8n credential type; paste your own key into the `HTTP Request` node's URL in place
  of the `YOUR_API_KEY_HERE` placeholders.
- **Telegram Bot API credential**: sends the finished screenshot to a chat. You'll
  also need the numeric chat ID to send to, set in the Telegram node in place of the
  `YOUR_TELEGRAM_CHAT_ID` placeholder.
