# Credentials

External services and credentials this workflow's nodes require, with no real values
ever stored here.

- **Telegram Bot API**: used by the Telegram Trigger node (`n8n-nodes-base.telegramTrigger`)
  to receive incoming messages from a Telegram bot. Needs a bot token, created via
  [@BotFather](https://t.me/BotFather) on Telegram.
- **Google Gemini API**: used by the Google Gemini Chat Model node
  (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`) to run the `gemini-2.0-flash-lite-001`
  model that powers the AI Agent's responses. Needs an API key (Google AI Studio) or a
  Google Cloud service account with the Generative Language / Vertex AI API enabled.
- **Whatever service the HTTP Request tool is meant to call**: the workflow's name and
  stated purpose point at VAPI (a voice AI calling API), but the HTTP Request tool node
  (`n8n-nodes-base.httpRequestTool`) has no URL, method, or credential set in the
  exported JSON, so this could not be confirmed from the file. If wired up to VAPI as
  intended, it needs a VAPI API key, typically sent as a bearer token in the request's
  Authorization header, plus the specific call-creation endpoint URL and a target phone
  number supplied at call time.

No other credentials are attached in this export. The AI Agent, Simple Memory, and the
workflow's trigger/tool connection graph itself do not require separate credentials
beyond the three above.
