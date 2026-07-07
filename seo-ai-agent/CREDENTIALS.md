# Credentials

External services this workflow needs, configured as n8n credentials after import.
No real values are stored anywhere in this project; add your own in n8n's credential
manager.

- **Google Gemini (PaLM API) credential**: powers both the technical-audit and
  content-audit LLM agent nodes.
- **Gmail credential (OAuth2)**: sends the finished audit report by email. Set your
  own recipient address in the workflow's Gmail node (`sendTo`); it ships with a
  placeholder.
