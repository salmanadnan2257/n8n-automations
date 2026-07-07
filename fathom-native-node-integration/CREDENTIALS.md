# Credentials required

- **Fathom.ai webhook secret**: used by the "Webhook" (and disabled "Webhook1")
  node to verify incoming Fathom call-recording webhooks. Generate this in your
  Fathom account's webhook settings and set it on the node's `webhookSecret`
  parameter.
- **Google Sheets credential**: used by "Get Lead Info," "Update row in sheet,"
  "Update row with latest call ID," and their duplicate-branch counterparts to
  read and write the CRM spreadsheet.
- **Google Drive credential**: used by "Copy existing template" (and
  "Copy existing template2") to duplicate the Slides proposal template.
- **Google Slides credential**: used by "Replace text in the proposal" (and
  "Replace text in the proposal2") to fill the copied template with
  AI-extracted content.
- **Gmail credential**: used by "Send the proposal for review and edits" (and
  its duplicate-branch counterpart) to email the generated proposal link for
  review.
- **OpenRouter API credential**: used by the "OpenRouter Chat Model" node
  (model `anthropic/claude-sonnet-4`), the LLM behind the live extraction
  branch.
- **OpenAI API credential** (only needed if the disabled backup branch is
  re-enabled): used by the "OpenAI Chat Model" node (model `gpt-5-mini`) as an
  alternate LLM for the same extraction step.
