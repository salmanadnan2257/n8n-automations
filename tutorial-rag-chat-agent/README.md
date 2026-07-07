# Tutorial-Built RAG Chat Agent

## What it is

A three-workflow n8n set: a webhook-based AI chat agent that answers questions using
a Retrieval-Augmented Generation (RAG) setup (a Supabase vector store plus Postgres
chat memory), a companion agent that critiques each finished conversation and emails
feedback when it finds something worth flagging, and a shared error handler that
emails a failure report whenever either of the other two throws an unhandled error.

## Why it exists

The live n8n workflow names for all three files carried a prefix that named a
specific YouTube creator's handle, strongly suggesting this was built while following
that creator's tutorial, rather than designed originally or built for a client. I'm
stating that plainly: this is a read-through and write-up of a tutorial-built
automation, not original design work or client work. I've dropped the creator's
handle from the public folder name, the display title, and the rest of this document
since it's someone else's handle, not something to carry into a portfolio. I did not
run these workflows end to end myself, so behavior described below comes from reading
the node graphs and their parameters, not from an observed run.

The persona baked into the main agent's system prompt (an Instagram DM assistant for
a business called "NEXUS" run by someone named "Devin," complete with lead
qualification questions and budget thresholds) is part of the original tutorial
content, not something I invented or something tied to any real business I represent.

## Features

- Answers incoming chat messages (from webhook query parameters) using an AI agent
  backed by Google Gemini, with retrieval from a Supabase vector store and a
  per-session chat history in Postgres.
- Ingests a source PDF into the same vector store through a separate manual-trigger
  branch, chunking it and embedding it with Gemini before insertion.
- After each reply, forwards that session's recent chat history to a second workflow
  that critiques the conversation for support quality and emails the critique only
  when the agent finds a real issue.
- Sends a failure report by email from a shared error workflow whenever either of the
  first two workflows throws an unhandled error, wired through n8n's workflow-level
  error handling setting rather than a visible node connection.

## Architecture

Three separate n8n workflow files, exported as JSON:

- `rag-chat-agent.json`: the main chat/RAG workflow.
- `analyze-agent.json`: the companion conversation-quality critic.
- `error-handler.json`: the shared error workflow.

### rag-chat-agent.json (main agent)

A `webhook` node (POST) receives each incoming message as query parameters
(`last_utterance` for the text, `uuid` for the session id) and triggers the AI Agent.

The **AI Agent** (`@n8n/n8n-nodes-langchain.agent`) is wired to three sub-nodes over
LangChain connection types, not plain `main` connections:

- **Google Gemini Chat Model** (`lmChatGoogleGemini`) as its language model.
- **Postgres Chat Memory** (`memoryPostgresChat`), keyed by the `uuid` query
  parameter as a custom session key, holding the last 15 messages of context.
- **Supabase Vector Store** (`vectorStoreSupabase`, mode `retrieve-as-tool`) exposed
  to the agent as a callable tool named `nexus_or_devin`, querying a table called
  `nexus_info`. This node in turn uses its own **Embeddings Google Gemini1** node
  (`gemini-embedding-001`) to embed the query text before searching.

The AI Agent node has `alwaysOutputData` set to true, which matters because its
output is read much later in the graph (see the response step below) after several
more nodes have already run.

A second, disconnected branch handles ingestion and only runs when triggered by
hand: **When clicking 'Execute workflow'** (`manualTrigger`) reads a local file
(`readWriteFile`, hardcoded path `/home/node/Downloads/NEXUS/Nexus.pdf`) and feeds it
to **Insert into Supabase Vectorstore1** (`vectorStoreSupabase`, mode `insert`,
same `nexus_info` table). That insert node pulls its document content through a
**Default Data Loader** (`documentDefaultDataLoader`, binary mode) chained to a
**Recursive Character Text Splitter1** (splitting on markdown structure), and embeds
each chunk with a separate **Embeddings Google Gemini** node (also
`gemini-embedding-001`, a different node instance from the one used at query time).

Back on the main reply path, once the AI Agent responds, the flow continues (it does
not respond to the caller yet): a **Supabase** node (`getAll` on table
`n8n_chat_histories`, filtered to the current session id, limited to 20 rows) reads
that session's history, an **Aggregate** node combines all returned items into one,
and a **Code** node reshapes each row into a `{ role: content }` object. That
reshaped array is POSTed by an **HTTP Request** node directly to the analyze agent's
webhook URL (a plain HTTP call to another workflow's webhook, not n8n's native
Execute Workflow node). Only after that HTTP call returns does a **Respond to
Webhook** node send the original caller their answer, reading it back from
`$('AI Agent').item.json.output`, the earlier node's output, addressable here
specifically because of the `alwaysOutputData` flag noted above.

### analyze-agent.json (companion critic)

A separate **webhook** node receives the chat-history array forwarded by the main
agent as its POST body. An **AI Agent** node (backed by its own **Google Gemini Chat
Model**, model `gemini-2.0-flash-lite`, no memory, no tools) is prompted as a
customer-support quality analyst: it reviews the transcript for empathy, clarity,
resolution, and tone, and its entire output is required to be either constructive
feedback or the literal word "None" if the conversation needed no improvement. An
**If** node checks whether the output does not start with "None"; if there's real
feedback, a **Send Email** node emails it. If the output is "None," the If node's
false branch is empty and the workflow simply ends. This workflow has no response
node at all, so it never returns anything to the main agent's HTTP Request call
regardless of outcome.

### error-handler.json (shared error workflow)

A single small graph: an **Error Trigger** node (n8n's built-in trigger for workflow
execution failures) feeds a **Code** node that repackages the incoming execution data
into a flat object, which feeds a **Send Email** node that emails the error's keys,
values, message, and stack trace. This workflow is inactive on its own (n8n error
workflows aren't meant to run standalone); it only fires because both
`rag-chat-agent.json` and `analyze-agent.json` set it as their
`settings.errorWorkflow`, referencing this workflow's id. That link is a workflow
setting, not a node-to-node connection, so it does not appear anywhere on either
workflow's canvas.

## Setup

1. In n8n: **Workflows** menu > **Import from File**. Import each of the three JSON
   files separately (`rag-chat-agent.json`, `analyze-agent.json`,
   `error-handler.json`), one import per file.
2. After importing, open `rag-chat-agent.json` and `analyze-agent.json`'s **Settings**
   panel and set each one's error workflow to the imported `error-handler.json`
   workflow (the id in the export refers to the original instance and will not
   resolve on a new one).
3. Create and attach these credentials before activating anything (see
   `CREDENTIALS.md` for the full list with descriptions):
   - Google Gemini (PaLM) API
   - Postgres
   - Supabase API
   - SMTP
4. Point the ingestion branch's **read_nexus_research** node at a real file path
   reachable from wherever n8n runs; the exported path
   (`/home/node/Downloads/NEXUS/Nexus.pdf`) is specific to the original builder's
   container and will not exist elsewhere.
5. Create the Supabase table the vector store expects (`nexus_info`, matching
   whatever schema n8n's Supabase vector store node requires for embeddings plus
   metadata) and a `n8n_chat_histories` table with at least `session_id` and
   `message` columns, since the main agent's plain Supabase node reads directly from
   that table by name.
6. After importing `analyze-agent.json`, copy its webhook's production URL and update
   the **HTTP Request** node inside `rag-chat-agent.json` (currently a placeholder,
   `https://YOUR_N8N_HOST/webhook/YOUR_ANALYZE_WEBHOOK_PATH`) to point at it.
7. Activate `rag-chat-agent.json` and `analyze-agent.json`. Leave `error-handler.json`
   inactive; it is only invoked through the other two workflows' error-workflow
   setting.

## Usage

Send a POST request to the main agent's webhook with `last_utterance` (the user's
message) and `uuid` (a session identifier used for both chat memory and history
lookup) as query parameters. The response body is JSON: `{ "response": "..." }`,
the AI Agent's reply. Each call also triggers, in the background, a chat-history
hand-off to the analyze agent, which may send a critique email if it finds the
conversation lacking; the caller receives no indication either way. To load or
refresh the knowledge base, run the manual-trigger ingestion branch inside
`rag-chat-agent.json` by hand against a source PDF.

## Challenges

These are genuine technical difficulties this kind of workflow runs into, each tied
to whether the actual node graph addresses it, based on reading the JSON, not a live
run.

- **The webhook response waits on an unrelated round trip.** The caller's answer is
  already sitting in the AI Agent's output right after it runs, but **Respond to
  Webhook** only fires after the chat-history fetch, aggregate, code transform, and a
  full HTTP call to the analyze agent's webhook all complete. The graph does address
  getting at that early output (via `alwaysOutputData` and the `$('AI Agent')`
  reference), but it does not address the added latency of forcing every reply to
  wait on a side workflow that has nothing to do with answering the user.
- **The analyze agent is a fire-and-forget call with no acknowledgment.** The main
  agent's HTTP Request node posts to the analyze agent's webhook and uses whatever
  comes back only to feed the next node in its own chain; the analyze workflow itself
  has no Respond to Webhook node at all. If the analyze agent or its email send fails,
  the main agent has no way to know or react to that beyond the HTTP call itself
  succeeding or failing.
- **Ingestion is entirely manual and tied to one hardcoded local path.** Refreshing
  the knowledge base requires opening the workflow and clicking the manual trigger,
  and the source file must exist at the exact path baked into the
  **read_nexus_research** node. There's no schedule, no file-drop trigger, and no
  check for whether the same content was already inserted, so re-running ingestion
  appends duplicate chunks rather than updating existing ones.
- **Two separate embeddings nodes have to stay in lockstep.** Insertion uses
  **Embeddings Google Gemini** and retrieval uses **Embeddings Google Gemini1**, two
  distinct node instances that both happen to use `models/gemini-embedding-001`
  today. Nothing in the graph enforces that they stay on the same model; if one gets
  changed and the other doesn't, similarity search would degrade without any visible
  error.
- **Error handling is invisible on the canvas.** Both `rag-chat-agent.json` and
  `analyze-agent.json` route failures to `error-handler.json` purely through the
  `settings.errorWorkflow` field, which does not show up as a connection anywhere in
  the node graph. Anyone reviewing just the visual workflow would not know error
  emails exist without checking each workflow's Settings panel separately.
- **The lead-qualification logic lives entirely in a prompt, not in nodes.** The main
  agent's system message encodes multi-step lead qualification (budget over $5,000,
  more than 10 employees, more than 10,000 followers) as instructions to the language
  model rather than as any deterministic node logic (no `if`, `switch`, or code node
  enforces these thresholds). Whether a lead actually gets correctly qualified or
  rejected depends entirely on the model following those instructions consistently.

## What I learned

- n8n's `$('NodeName')` expression syntax lets a downstream node pull data from any
  earlier node in the same execution, not just its immediate predecessor, and the
  `alwaysOutputData` flag is what keeps an early node's output available for that
  kind of lookup even after several more nodes run afterward.
- There's a real difference between n8n's native workflow-to-workflow call (an
  Execute Workflow node) and what this pipeline actually does: a plain HTTP Request
  node POSTing to another workflow's own webhook URL. The latter is a normal HTTP
  call with no built-in retry or shared execution context.
- `settings.errorWorkflow` is a workflow-level setting, entirely separate from the
  visual node graph, so error handling can be wired into a workflow without adding
  a single node or connection to its canvas.
- The `vectorStoreSupabase` node type is reused for two different roles in the same
  vector store: `insert` mode for writing chunks in, `retrieve-as-tool` mode for
  handing retrieval to an agent as a callable tool, each configured as its own node
  instance pointed at the same table.

## What I'd do differently

- Reorder the main agent so **Respond to Webhook** runs immediately after the AI
  Agent, and move the chat-history fetch and analyze-agent hand-off to run after the
  response instead of before it, so the caller isn't waiting on a side process.
- Give the analyze agent a response node (even a minimal acknowledgment) so failures
  there are observable instead of silently swallowed by the main agent's HTTP call.
- Replace the manual-trigger ingestion branch with a scheduled or file-drop trigger,
  and add a check (by content hash or source id) before inserting so repeated runs
  update existing vectors instead of duplicating them.
- Consolidate the two separate Gemini embeddings nodes into a single shared
  reference (or at minimum, name them so it's obvious they must be kept identical)
  so ingestion and retrieval can't silently drift onto different embedding models.
- Move the lead-qualification thresholds (budget, employee count, follower count)
  out of the prompt and into an actual node (an `if` or `code` node evaluating
  structured fields extracted from the conversation) so qualification doesn't depend
  entirely on the model reliably following written instructions.
