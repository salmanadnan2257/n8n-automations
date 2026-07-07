# Credentials

- **Google Gemini API** (Google PaLM/Gemini credential type in n8n): used by the "Google Gemini Chat Model" node as the language model behind the Social Media Router Agent.

Note: this export contains only the chat-triggered router agent and its six tool-workflow definitions. It does not include the platform-specific posting logic (no Twitter, LinkedIn, Facebook, Instagram, Threads, or YouTube nodes are present), so no platform API credentials appear in this workflow's node graph. A complete deployment would need those added along with their respective credentials (X/Twitter API, LinkedIn API, Facebook Graph API, Instagram Graph API, Threads API, YouTube Data API).
