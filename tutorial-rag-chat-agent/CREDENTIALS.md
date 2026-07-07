# Credentials required

- **Google Gemini (PaLM) API** (n8n credential type `googlePalmApi`): used four times
  across the two active workflows. In the main agent: the chat model behind the AI
  Agent, and the embeddings model used both when inserting the source PDF into the
  vector store and when embedding a query for retrieval. In the analyze agent: the
  chat model (`gemini-2.0-flash-lite`) that scores the conversation transcript.
- **Postgres** (n8n credential type `postgres`): backs the Postgres Chat Memory node
  in the main agent, which stores and retrieves conversation history keyed by a
  session id (the last 15 messages of context per session).
- **Supabase API** (n8n credential type `supabaseApi`): used three times in the main
  agent. The Supabase Vector Store node retrieves from the `nexus_info` table as an
  agent tool. A separate insert branch writes PDF chunks into the same table. A plain
  Supabase node also reads rows straight from an `n8n_chat_histories` table for a
  session, independent of the vector store.
- **SMTP** (n8n credential type `smtp`): used by the Send Email node in both the
  analyze agent (sends the transcript critique) and the error handler (sends the
  failure report). Both nodes reference the same SMTP credential in the export.

No other external API or credential is used. The main agent's HTTP Request node calls
the analyze agent's webhook directly over HTTP rather than through an n8n credential,
so that call needs no separate entry here, only a reachable URL for the analyze
workflow's webhook once both are imported and activated.
