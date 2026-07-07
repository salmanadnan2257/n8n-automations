# Credentials required

- **Telegram Bot API token**: used by the Telegram Trigger node (listens for incoming messages) and the Send a text message node (sends the reply back to the user).
- **Google Gemini API key** (via Google PaLM/Gemini credential type in n8n): used by the Google Gemini Chat Model node, which is the language model behind the AI Agent.
- **Google Sheets OAuth2 credential**: used by both the Add Expense tool node (appends rows) and the Get Expense tool node (reads rows), pointed at the same spreadsheet.
