# Credentials

External services this workflow needs. No real values are stored anywhere in this
project; add your own where noted.

- **Google Gemini (PaLM API) credential**: powers the AI Agent that generates the
  daily health tip.
- **Telegram Bot API credential**: sends the finished tip as a message. You'll also
  need the numeric chat ID to send to, set in the Telegram node in place of the
  `YOUR_TELEGRAM_CHAT_ID` placeholder.
