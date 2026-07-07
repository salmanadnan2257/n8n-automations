# Credentials

External services and credentials this workflow's nodes require. No real values are
stored anywhere in this project; wire these up in n8n's own credential store after
importing `workflow.json`.

- **OpenRouter API**: used by every `OpenRouter Chat Model*` node (7 total), the LLM
  backend for topic planning, intro/chapter generation, per-section writing, the
  sources list, and the table of contents. All nodes are configured to call
  `anthropic/claude-3.5-sonnet` through OpenRouter.
- **Tavily API** (HTTP Header Auth, `Authorization: Bearer <token>`): used by the five
  `Tavily*` HTTP Request nodes to run a web search per subtopic.
- **Google Sheets OAuth2**: used by every Google Sheets node (`Google Sheets1..5`,
  `Get Sources`, `Send Sources`, `Get All Content`, `Get All Content1`, `Send Intro`,
  `Send ToC`). Acts as shared intermediate storage across the five parallel research
  branches; rows are matched on a `Search Topic` column.
- **APITemplate.io API**: used by the `Generate PDF` node to render the combined HTML
  report into a downloadable PDF.
- **Gmail OAuth2**: used by the `Send Report` node to email the finished PDF to the
  address collected in the form submission.

The **On form submission** trigger node needs no external credential; it is an n8n
form webhook.
