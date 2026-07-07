# Credentials and external services

This workflow does not run without every one of these configured in the n8n instance's
credential store. No real values are stored anywhere in this repository; `workflow.json`
only contains credential *references* (name/id pointers) or, where a node had a
hardcoded value in the original export, an obvious placeholder like `<your apify url>`.

- **Google Drive (service account or OAuth2)**: used to watch a specific Drive folder
  for new or updated files (`Google Drive Trigger`), list files in that folder
  (`Search File`), and download a file's binary content (`Get Data`) for the RAG
  ingestion pipeline.
- **Google Sheets (service account)**: used to read leads (`Get Leads`), append newly
  scraped leads (`Append Leads`), write back cleaned/scored leads (`Update Data`), and
  poll a spreadsheet for new rows to push into the vector store (`Google Sheets
  Trigger`).
- **Apify (or equivalent Google Maps scraping API)**: called directly over HTTP, not
  through a dedicated n8n credential. `Scrape Maps` POSTs a search job to an Apify
  actor endpoint (URL was hardcoded in the original export as `<your apify url>`, now a
  placeholder) and `Get Result` GETs the run's output (`<your apify get>`). Needs an
  Apify API token appended to those URLs or sent as a header/query param.
- **OpenAI API key**: used for chat completion (`gpt-4o-mini` via `OpenAI Chat Model`
  and `Chat Model`) and for every embeddings node (`Embeddings OpenAI`, `Embeddings
  OpenAI1` through `Embeddings OpenAI4`, `small3`) that turns document chunks and
  queries into vectors.
- **Supabase project URL + service role key**: backs every vector store node
  (`Supabase Vector Store`, `Supabase Vector Store2`, `RAG`, `Leads`, `RAG1`, `Leads1`).
  Two tables are used: `documents` (company knowledge base) and `restaurant_leads`
  (scraped lead data).
- **Postgres connection (host, database, user, password)**: backs the chat memory
  nodes (`Postgres Chat Memory`, `Chat Memory`), which store per-conversation message
  history keyed by a session identifier.
- **Cohere API key**: required by the two reranker nodes (`Reranker Cohere`,
  `Reranker Cohere1`). Note: in this exported graph these two nodes exist on the
  canvas but have no incoming or outgoing connections, so reranking is not actually
  wired into the retrieval path as shipped. See the README's Challenges section.
- **WAHA (WhatsApp HTTP API) instance URL + API key**: required by `WAHA Trigger`,
  the intended entry point for real WhatsApp messages. This node is present but
  disabled in the export.
- **n8n instance itself**: `When chat message received` (the LangChain Chat Trigger)
  exposes a webhook-backed chat UI used to test `AI Agent1` without WhatsApp. The
  generic `Webhook` node and its paired `HTTP Request1` node are both disabled in the
  export and their URLs were already placeholders (`<your webhook>`) in the source
  file; no credential is needed for the disabled webhook path itself.
