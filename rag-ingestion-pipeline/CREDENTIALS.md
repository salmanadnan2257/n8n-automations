# Credentials required

- **Google Drive OAuth2** (node type `googleDriveOAuth2Api`): used by the Drive
  triggers (file created / file updated), file download, the Word-to-Google-Doc
  conversion HTTP request, and file deletion nodes.
- **OpenAI API** (node type `openAiApi`): used by both embeddings nodes (ingestion),
  both chat model nodes (the query agent and its vector store tool's language model),
  and the `Set Version` node's `gpt-4o-mini` call.
- **Supabase API** (node type `supabaseApi`): used by the vector store insert nodes,
  the stale-row delete node, and the query-side Supabase Vector Store node. All point
  at the same `documents` table.
- **Postgres** (node type `postgres`): used by the chat memory node to store and
  retrieve conversation history for the query agent.
