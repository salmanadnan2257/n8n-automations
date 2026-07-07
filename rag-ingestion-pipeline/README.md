# RAG Ingestion Pipeline

## What it is

An n8n workflow (exported from n8n as `RAG System 2.0`) that watches a Google Drive
folder for new and updated files, extracts their text, splits it into chunks, embeds
those chunks with OpenAI, and writes the vectors into a Supabase (pgvector) table. A
second part of the same workflow exposes a chat-triggered AI agent that queries that
same table to answer questions about the ingested documents.

In short: it is the ingestion half and the query half of a retrieval-augmented
generation system, wired together as one n8n graph.

## Why it exists

RAG systems only work if the underlying documents are actually kept in sync with
whatever store the retrieval step reads from. Doing that by hand (watch a folder,
convert formats, extract text, chunk it, embed it, delete stale rows) is exactly the
kind of repetitive, easy-to-get-wrong process automation is for. This workflow
automates the whole ingestion side, and pairs it with a minimal chat agent so the
result is queryable end to end without extra glue code.

## Features

- Google Drive folder watch, split into two trigger types: file created and file
  updated.
- Format-aware extraction: PDF, plain text, Google Docs, Excel (`.xlsx`), and Word
  (`.doc`/`.docx`, including the older `application/vnd.ms-word` MIME type).
- Word documents get converted to Google Docs format first (via a direct Drive API
  call), because the workflow's text extraction path only handles PDF, plain text,
  Excel, and native Google Docs directly.
- Recursive character text splitting (chunk size 2000, overlap 200) before embedding.
- OpenAI embeddings written into a Supabase vector table (`documents`), queried later
  through a `match_documents` Postgres function.
- Update handling that deletes a file's previous vector rows before re-inserting fresh
  ones, so edits don't leave stale chunks behind, plus a simple version counter
  (`v1`, `v2`, ...) tracked in each row's metadata.
- A separate chat-triggered agent (OpenAI model + Postgres-backed conversation memory)
  that uses the same Supabase table as a retrieval tool to answer questions.

## Architecture

The workflow is really three loosely connected sub-graphs sharing the same Supabase
`documents` table.

### 1. New file ingestion (trigger: "File Created")

`File Created` (Google Drive Trigger, event `fileCreated`, polling every minute on a
specific folder, cached as "Projects") feeds `Set File ID1` (a Set node that pulls
`id` and `mimeType` off the trigger item into `file_id` / `file_type`). That feeds
`Loop Over Items` (Split In Batches), which is used as an iterate-and-fetch loop: its
"loop" output goes to `Download File1` (Google Drive download, with the
`googleFileConversion` option set to convert native Google formats to `text/plain`),
which feeds back into `Loop Over Items`. Once the loop finishes, its "done" output goes
to `Switch2`, a Switch node with rules matching `file_type` against `application/pdf`,
`application/vnd.google-apps.document`, the Excel `.xlsx` MIME type, and three Word
MIME type variants (`.docx`, `application/msword`, `application/vnd.ms-word`), with a
fallback to the Excel branch.

From `Switch2`:
- PDF -> `Extract PDF Text` (Extract From File, `operation: pdf`) -> `Insert into
  Supabase Vectorstore1`.
- Google Doc (already plain-text-convertible) -> `Extract from Text File` (Extract
  From File, `operation: text`) -> `Insert into Supabase Vectorstore1`.
- Excel -> `Extract from Excel` (Extract From File, `operation: xlsx`) -> `Aggregate1`
  (concatenates all rows into one field) -> `Summarize1` -> `Insert into Supabase
  Vectorstore1`.
- Any Word variant -> `Convert to Google Doc1` (HTTP Request node, `POST
  .../files/{id}/copy` against the Drive API, `mimeType:
  application/vnd.google-apps.document`) -> `Delete File` (deletes the original Word
  file). This branch has no connection onward to extraction or the vector store in the
  exported graph. The likely intent (not stated anywhere in the JSON, so this is
  inference) is that creating the Google Doc copy fires a new `fileCreated` event,
  which re-enters this same trigger with `file_type` now equal to
  `application/vnd.google-apps.document`, and gets extracted as a Google Doc on that
  second pass. That dependency on the trigger re-firing is not visible anywhere in the
  graph itself.

`Insert into Supabase Vectorstore1` is a Supabase Vector Store node (`mode: insert`,
table `documents`, `queryName: match_documents`) with three attached sub-nodes:
`Recursive Character Text Splitter` (chunk size 2000, overlap 200, with a `markdown`
split-code option set), `Embeddings OpenAI1` (OpenAI embeddings, no model override in
the node, so whatever n8n's node default resolves to), and `Enhanced Default Data
Loader1` (a Document Default Data Loader whose `jsonData` expression reads
`$json.data || $json.text || $json.concatenated_data`, i.e. whichever of those fields
the upstream extraction node happened to produce). The loader also attaches metadata
to each chunk: `file_id`, a hardcoded `version: "v1"`, `creator` (Drive file owner
display name), `created_at`, `last_modified`, a hardcoded `folder_path: "projects"`,
`file_name`, and `file_extension` (which is actually populated with the MIME type, not
a file extension).

### 2. File update handling (trigger: "File Updated", disabled)

This mirrors the created-file flow but is **disabled** in the exported workflow (the
node itself has `"disabled": true`, and the whole workflow's `active` flag is also
`false`). `File Updated` (Google Drive Trigger, event `fileUpdated`, same folder) would
feed `Set File ID`, then an `If` node that checks two things: is `file_type` equal to
the Google Doc MIME type, and was the file created less than 60 seconds ago. If both
are true, the branch does nothing (this appears to be there specifically to ignore the
Google Doc copy created by the Word-conversion step above, so it doesn't get
double-processed as an "update"). Otherwise it proceeds to `Delete Old Doc Rows`
(Supabase delete, `metadata->>file_id ilike '*<file_id>*'` against the `documents`
table), then `Limit`, then `Set Version` (an OpenAI `gpt-4o-mini` call, prompted to
read a version string like `v1` out of `$json.metadata.version` and return `v2`), then
into the same download-loop / format-switch / extraction pattern as the created-file
flow (`Loop Over Items1`, `Switch`, `Extract PDF Text1` / `Extract from Text File1` /
`Extract from Excel1` -> `Aggregate` -> `Summarize`, `Convert to Google Doc2` ->
`Delete File1`), ending at `Insert into Supabase Vectorstore` with its own splitter
(`Recursive Character Text Splitter1`, chunk size 2000, overlap 200, no `markdown`
option this time), `Embeddings OpenAI2`, and `Enhanced Default Data Loader2` (same
metadata shape, but `version` comes from the `Set Version` node's output instead of a
hardcoded `"v1"`).

### 3. Query agent

`When chat message received` (Langchain Chat Trigger) feeds `New RAG Agent` (Langchain
Agent node), which has three attached sub-nodes: `OpenAI Chat Model` as its language
model, `Postgres Chat Memory` (context window 10 messages) for conversation history,
and `Vector Store Tool` (named `database`, described as "retrieves data about
projects") as its retrieval tool. `Vector Store Tool` itself is backed by `OpenAI Chat
Model1` and `Supabase Vector Store` (table `documents`, `queryName: match_documents`),
with `Embeddings OpenAI` providing the query-time embedding. This is the read side: it
queries the exact same `documents` table the two ingestion flows write to.

## Setup

1. Import the workflow: in n8n, **Workflows -> Import from File**, select
   `workflow.json`.
2. Create and attach these credentials in n8n (see `CREDENTIALS.md` for the full
   list): a Google Drive OAuth2 credential, an OpenAI API credential, a Supabase API
   credential, and a Postgres credential (used only by the chat memory node).
3. In Supabase, create a `documents` table with a vector column and a `match_documents`
   Postgres function. This is the standard Supabase + pgvector RAG setup (Supabase
   publishes a reference SQL script for this); nothing in the JSON defines the table
   schema itself, so it has to be created independently.
4. Point the `folderToWatch` parameter on the `File Created` (and, if you enable it,
   `File Updated`) trigger at your own Google Drive folder ID.
5. The `File Updated` trigger node is disabled and the workflow's `active` flag is
   `false`. Both need to be turned on deliberately if you want update handling and live
   polling.

## Usage

Once active, dropping a PDF, Word doc, Excel file, or Google Doc into the watched
Drive folder triggers ingestion within a minute (the trigger polls every 60 seconds).
The chat agent is used separately, by sending a message to the workflow's chat trigger
webhook, and it answers using whatever has been ingested into the `documents` table.

## Challenges

- **Word document handling doesn't close the loop in the graph.** As described above,
  `Convert to Google Doc1` / `Convert to Google Doc2` copy a Word file into Google Docs
  format and delete the original, but neither branch connects forward to extraction or
  insertion. The only way this produces an embedded chunk is if the newly created
  Google Doc copy causes the Drive trigger to fire again, which is an implicit
  dependency on trigger behavior, not something enforced by the graph.
- **The update path is disabled by default.** `File Updated` has `disabled: true` and
  the whole workflow is inactive (`active: false`). A workflow that looks feature
  complete on paper (create and update handling, versioning, stale-row deletion) is
  actually only running the create path unless someone explicitly flips both switches.
- **Inconsistent chunking between the two insert paths.** The created-file splitter
  (`Recursive Character Text Splitter`) has `splitCode: markdown` set; the
  updated-file splitter (`Recursive Character Text Splitter1`) does not, despite both
  otherwise using the same chunk size and overlap. Whether that's intentional or a
  copy-paste gap between the two branches isn't stated anywhere in the JSON.
- **No pagination or batching limits on Drive polling.** The trigger polls the folder
  every minute with no explicit page size or backoff configuration visible in the
  node's parameters, so behavior under a large influx of files (a folder getting
  hundreds of files at once) isn't something this graph addresses.
- **Metadata field naming is misleading.** The document loader stores the file's MIME
  type in a field called `file_extension`, and hardcodes `folder_path: "projects"`
  regardless of which Drive folder the file actually came from. Any downstream
  filtering on those metadata fields would need to account for that.
- **Stale-row deletion relies on a string match, not an exact key.** `Delete Old Doc
  Rows` filters with `metadata->>file_id ilike '*<file_id>*'` (a wildcard `LIKE`), not
  an equality check. If one file's ID happened to be a substring of another's, this
  could delete more rows than intended. Google Drive file IDs are long random strings
  so a collision is unlikely in practice, but the filter as written doesn't guarantee
  it can't happen.

## What I learned

- Reading n8n's Split In Batches (`splitInBatches`) node in a real export clarified how
  the two-output loop pattern actually works: the "loop" output does the per-item work
  and feeds back into the same node, and the "done" output only fires once every batch
  has been processed, carrying the accumulated items forward.
- Langchain-style n8n nodes (the `@n8n/n8n-nodes-langchain.*` node types here:
  text splitter, embeddings, document loader, vector store, agent, chat memory) attach
  to a "root" node (an Insert/Vector Store node or an Agent node) through typed
  connection kinds (`ai_textSplitter`, `ai_embedding`, `ai_document`, `ai_tool`,
  `ai_languageModel`, `ai_memory`) rather than the plain `main` data connections used
  between regular nodes. Tracing those was necessary to understand which embeddings
  model and splitter actually feed which vector store insert.
- A single ingestion table doubling as both the write target (ingestion flows) and the
  read target (the agent's retrieval tool) is a simple, workable pattern for a small
  RAG setup, as long as both sides agree on the same `match_documents` query
  signature.

## What I'd do differently

- Wire the Word-document conversion branches all the way through to extraction and
  insertion explicitly, instead of depending on the Drive trigger re-firing on the
  converted copy. That dependency should either be documented in the workflow itself
  (a sticky note noting it) or removed by extracting text from the converted file
  directly in the same run.
- Use an exact-match filter (`eq`) instead of a wildcard `ilike` for the stale-row
  deletion, since there's no reason a substring match is needed when Drive file IDs are
  already exact identifiers.
- Make the two text splitters consistent (both markdown-aware or both plain), and pick
  the embedding model explicitly on both `embeddingsOpenAi` nodes rather than leaving
  it on the node default, so the choice is visible in the workflow itself instead of
  depending on whatever n8n resolves it to.
- Add an explicit connection (or at least a sticky note) clarifying whether the update
  flow is meant to be enabled together with the create flow, since right now a fresh
  import looks like it has update handling but silently doesn't run it.
