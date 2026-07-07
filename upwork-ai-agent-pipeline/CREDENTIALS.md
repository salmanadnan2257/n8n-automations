# Credentials

External services this workflow (orchestrator plus all three sub-workflows) needs
configured in n8n before it will run. No real values are stored here or anywhere in
this folder; these are n8n credential store entries you create yourself on import.

- **OpenAI API**: used by the orchestrator's chat model and by all three
  sub-workflows (`gpt-4o-mini` for application copy, Google Doc proposal fields, and
  Mermaid diagram generation).
- **Google Drive API**: used by sub-workflow 2 to copy the proposal template document
  and to set the copy's sharing permission to "anyone with the link, reader."
- **Google Docs API**: used by sub-workflow 2 to replace placeholder tokens in the
  copied document with the AI-generated proposal content.
