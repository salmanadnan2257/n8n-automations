# Credentials required

- **SMTP credential**: used by the "Send email" node to send the finished digest
  (host, port, username, password for any SMTP-capable mail provider).
- **Google Gemini / Google AI API credential**: used by the "Google Gemini Chat
  Model" node to call the Gemini API (model `gemini-2.0-flash-lite`) for
  summarizing each article.

No credential is needed for the Hacker News fetch itself; that node calls
Algolia's public Hacker News search API, which is unauthenticated.
