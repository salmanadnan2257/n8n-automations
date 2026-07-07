# Credentials

- **Google Gemini API** (Google PaLM/Gemini credential type in n8n): used by the "Google Gemini Chat Model" node as the language model behind the AI Agent that writes the workout plan.
- **SMTP** (mail server credential): used by the "Send email" node to deliver the finished plan to the requester's email address. Needs a real "From" address configured to replace the placeholder in `workflow.json`.
