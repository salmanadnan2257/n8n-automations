# Credentials required

- Google Slides OAuth2: used by the Replace Text node to fill placeholder tokens into
  a copied proposal deck.
- Google Drive OAuth2: used by the Google Drive node to copy the Slides proposal
  template file for each submission.
- OpenAI API: used by both OpenAI nodes (OpenAI, OpenAI1) to turn form input into
  structured proposal copy.
- Gmail OAuth2: used by both Gmail nodes (Gmail, Gmail1) to email the client a link to
  their finished proposal document.
- PandaDoc API key: used by the HTTP Request node (passed as a manual
  `Authorization: API-Key ...` header, not an n8n credential type) to create a
  PandaDoc document with a pricing table from the AI-generated copy.
