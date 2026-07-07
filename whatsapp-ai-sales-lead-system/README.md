# WhatsApp AI Sales Lead System

## Naming note (read this first)

The live n8n workflow this project is built from is named **"Cold Calling
Automation"** inside the exported JSON (`workflow.json`, top-level `name` field). That
name is misleading: there is no phone dialer, no call-center integration, and no
telephony node anywhere in the 48-node graph. What the workflow actually does is scrape
restaurant leads from Google Maps, build a Retrieval-Augmented Generation (RAG)
knowledge base in Supabase, and answer questions about those leads (and the company's
own documents) through an AI agent designed to sit behind WhatsApp via WAHA
(WhatsApp HTTP API). The folder name and this README describe what the workflow
actually is, not the label it shipped under.

## What it is

An n8n workflow with three independent subsystems wired into one canvas:

1. A **lead scraper** that queries a Google Maps scraping API (Apify) for restaurants
   in a given location, cleans and scores the results, and writes them to Google
   Sheets.
2. A **RAG ingestion pipeline** that watches a Google Drive folder for company
   documents and a Google Sheets tab for new leads, chunks and embeds both with
   OpenAI, and stores the vectors in two separate Supabase tables (`documents` and
   `restaurant_leads`).
3. An **AI agent** that retrieves from both Supabase tables as tools, holds
   per-conversation memory in Postgres, and is intended to answer WhatsApp messages
   through WAHA. As shipped, only a second, parallel copy of this agent (wired to
   n8n's own chat-test trigger, not WhatsApp) is actually connected to a trigger. See
   Challenges.

## Why it exists

The workflow was built for a business referred to in its own prompts and sheet titles
as "ReCharge," to turn a Google Maps search into a searchable database of restaurant
leads, and to let staff (or eventually customers) query both that lead database and
the company's own service documentation through a single WhatsApp-facing chatbot
instead of two separate tools.

## Features

- Google Maps lead scraping with a configurable search location (`Set Location`,
  default value `"Bali"`) and search term (`"Restoran"`), through an external
  scraping API called over plain HTTP.
- A JavaScript cleaning step that parses nested JSON fields (facilities, payment
  methods, advantages), formats opening hours, and computes a 0 to 100 lead score
  from rating, review count, and contact-data completeness, then buckets leads into
  High/Medium/Low quality.
- Google Sheets used as the system of record for scraped leads, both appended (new
  rows) and updated (existing rows matched on `row_number`).
- Two independent document ingestion paths into Supabase pgvector tables: one for
  general company documents (triggered by Google Drive changes) and one for
  structured restaurant lead rows (triggered by new Google Sheets rows), each with its
  own text splitter, embedder, and vector store node.
- An AI agent (LangChain agent node) with two retrieval tools (`CompanyDocuments` and
  `RestaurantLeads`), a detailed system prompt that forces tool selection by query
  type, and Postgres-backed conversation memory keyed by a per-user session ID.
- A parallel, disabled WhatsApp entry point (WAHA trigger) intended to feed the same
  agent pattern from real WhatsApp messages.

## Architecture

### 1. Lead scraping and cleaning (`Sticky Note1` region, left of canvas)

`When clicking 'Execute workflow'` (`n8n-nodes-base.manualTrigger`) starts the branch.
`Set Location` (`n8n-nodes-base.set`) hardcodes a `lokasi` field to `"Bali"`, which
feeds `Scrape Maps` (`n8n-nodes-base.httpRequest`), a POST to an Apify actor endpoint
with a JSON body specifying the search string `"Restoran"`, a max of 500 crawled
places, and Indonesian-language results. `Get Result`
(`n8n-nodes-base.httpRequest`) then GETs the run's dataset from Apify. `Append Leads`
(`n8n-nodes-base.googleSheets`, operation `append`) writes the raw scrape output
(title, rating, phone with dashes/spaces stripped, address, nested `additionalInfo`
fields) into a "Restaurant" tab. A disabled pair, `HTTP Request1` and `Webhook`
(both `disabled: true`), suggests an earlier design that pushed results to an external
webhook instead of, or in addition to, Sheets; that path is dead in the current export.

Separately, `Get Leads` (`n8n-nodes-base.googleSheets`) reads existing rows and feeds
`Clean Data` (`n8n-nodes-base.code`), a JavaScript node that parses the JSON-stringified
`Keunggulan`/`Fasilitas`/`Pembayaran` fields, builds a human-readable business summary,
and computes the lead score described above. Its output goes to `Update Data`
(`n8n-nodes-base.googleSheets`, operation `update`, matched on `row_number`), writing
the cleaned, scored version back over the same rows. `Append Leads` and `Update Data`
target the same spreadsheet and the same columns but run on different triggers and
with different source data shapes (raw Apify fields vs. cleaned/parsed fields); there
is no ordering guarantee between the two paths in this graph.

### 2. RAG ingestion into Supabase (`Sticky Note` and `Sticky Note2` regions)

**Company documents path**: `Google Drive Trigger`
(`n8n-nodes-base.googleDriveTrigger`, polls hourly, watches one folder for
`fileUpdated` events) triggers `Search File` (`n8n-nodes-base.googleDrive`, lists
files in that folder) then `Get Data` (`n8n-nodes-base.googleDrive`, operation
`download`, binary output). `Loop Over Items` (`n8n-nodes-base.splitInBatches`) batches
the downloaded files into `Supabase Vector Store`
(`@n8n/n8n-nodes-langchain.vectorStoreSupabase`, mode `insert`, table `documents`),
which pulls its embeddings from `Embeddings OpenAI`
(`@n8n/n8n-nodes-langchain.embeddingsOpenAi`), its chunks from `Default Data Loader`
(`@n8n/n8n-nodes-langchain.documentDefaultDataLoader`, binary mode), and its splitting
strategy from `Recursive Character Text Splitter`
(`@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter`, default chunk
settings).

**Restaurant leads path**: `Google Sheets Trigger`
(`n8n-nodes-base.googleSheetsTrigger`, polls hourly) feeds `Transform for Vector`
(`n8n-nodes-base.code`), which builds a business-summary string and a metadata object
per row, then `Check Existing Data` (`n8n-nodes-base.code`), which builds a
deterministic `unique_id` from name plus address and a second, more detailed
`pageContent`/`metadata` object. That output lands in `Supabase Vector Store2`
(`@n8n/n8n-nodes-langchain.vectorStoreSupabase`, table implied as `restaurant_leads`
from context; the node's own credential block is empty in the export), backed by
`small3` (an `embeddingsOpenAi` node, oddly named) and `Recursive Character Text
Splitter1` (this one explicitly sets `chunkOverlap: 200`, unlike the company-docs
splitter). The two ingestion paths duplicate almost the same summary-building logic in
two separately written Code nodes (`Transform for Vector` builds one summary shape,
`Check Existing Data` rebuilds a slightly different one from the same row) rather than
sharing one.

### 3. AI agent and retrieval (`Sticky Note3`, `Sticky Note4` regions)

There are two agent instances, not one:

- **`AI Agent`** (`@n8n/n8n-nodes-langchain.agent`) is wired to `OpenAI Chat Model`
  (`gpt-4o-mini`, `@n8n/n8n-nodes-langchain.lmChatOpenAi`), `Postgres Chat Memory`
  (`@n8n/n8n-nodes-langchain.memoryPostgresChat`, session key
  `{{ $('WAHA Trigger').item.json.payload._data.key.remoteJid }}`), and two retrieval
  tools, `RAG` and `Leads` (both `vectorStoreSupabase` nodes in `retrieve-as-tool`
  mode, against the `documents` and `restaurant_leads` tables respectively, each with
  its own `embeddingsOpenAi` node). Its prompt (`={{ $json.payload._data.key.id }}`)
  and memory key both reference WAHA's WhatsApp payload shape directly, so this agent
  was clearly designed to run behind WhatsApp.
- **`AI Agent1`** is a near-duplicate: same pattern, its own `Chat Model`, `Chat
  Memory`, and its own pair of retrieval tools `RAG1`/`Leads1` (against the same two
  Supabase tables), plus a much longer, more prescriptive system prompt ("MinCharge")
  that forces tool-selection order by keyword matching.
- `WAHA Trigger` (`@devlikeapro/n8n-nodes-waha.wahaTrigger`) exists on the canvas but
  is **disabled** and has **no outgoing connection at all** in the workflow's
  connection graph. `AI Agent` itself has no incoming `main` connection from any
  trigger, disabled or not, meaning as exported it cannot run: it is fully wired with
  a model, memory, and tools, but nothing calls it.
- The node that is actually connected to a live trigger is `AI Agent1`, fed by `When
  chat message received` (`@n8n/n8n-nodes-langchain.chatTrigger`), which is n8n's
  built-in test chat widget, not WhatsApp.
- Two `rerankerCohere` nodes (`Reranker Cohere`, `Reranker Cohere1`) exist on the
  canvas near the `AI Agent1` retrieval tools but have **zero connections**, in or
  out, anywhere in the connection graph. Cohere reranking does not run in this
  workflow as exported; see Challenges.

In short: the scraping and ingestion halves of the workflow are fully wired and would
run. The WhatsApp-facing half is designed and partially built (prompts, memory keys,
and tools all assume a WAHA payload) but the actual WAHA trigger is disconnected, and
the connected chat agent is a test-only stand-in.

## Setup

This workflow needs a self-hosted or cloud n8n instance with the LangChain node
package (`@n8n/n8n-nodes-langchain`) and the community WAHA node
(`@devlikeapro/n8n-nodes-waha`) installed, plus:

- A Google Cloud service account (or OAuth2 app) with Drive and Sheets scopes.
- An Apify account (or equivalent Google Maps scraping API) and an actor that accepts
  the job shape in `Scrape Maps`'s body (`locationQuery`, `searchStringsArray`,
  `maxCrawledPlacesPerSearch`, etc).
- A Supabase project with pgvector enabled and two tables, `documents` and
  `restaurant_leads`, matching the schema the LangChain Supabase vector store node
  expects (id, content, metadata, embedding columns).
- A Postgres database reachable from n8n for chat memory.
- An OpenAI API key.
- A Cohere API key, if reranking is wired up (it currently is not).
- A running WAHA instance and its API key/session, if the WhatsApp path is completed
  and re-enabled.

See `CREDENTIALS.md` for the full list of what each node needs.

Import `workflow.json` into n8n, then:

1. Fill in each Google Drive/Sheets node's document and folder IDs (the export has
   placeholders where real IDs were scrubbed).
2. Replace `<your apify url>` and `<your apify get>` in `Scrape Maps` and `Get Result`
   with real Apify actor run/dataset endpoints, including your Apify token.
3. Attach real credentials (OpenAI, Supabase, Postgres, Cohere, WAHA) to every node
   that needs one; the JSON only carries credential name/id references, not secrets.
4. Decide whether to finish and re-enable the WAHA path (wire `WAHA Trigger` into
   `AI Agent`'s main input, and confirm `AI Agent`'s prompt and memory session key
   still match WAHA's actual payload shape in your n8n version) or keep using the
   chat-trigger test path (`AI Agent1`).

## Usage

- Run the manual trigger to scrape one location's worth of restaurant leads into
  Google Sheets.
- Uploading or updating a file in the watched Drive folder triggers ingestion into
  the `documents` Supabase table within the hourly poll window.
- A new row appended to the Restaurant Sheets tab triggers ingestion into the
  `restaurant_leads` Supabase table within the hourly poll window.
- Open the workflow's chat panel in n8n (or, once completed, message the connected
  WhatsApp number) to query `AI Agent1` (or `AI Agent`, once wired to a trigger) about
  company documents or restaurant leads.

## Challenges

- **The WhatsApp trigger is disconnected.** `WAHA Trigger` is disabled and has no
  outgoing connection, and `AI Agent`, the instance whose prompt and memory key are
  built for WAHA's payload shape, has no incoming trigger at all. The workflow, as
  exported, cannot receive a WhatsApp message and respond; only the test chat path
  (`AI Agent1` behind `When chat message received`) is live. Any deployment of this
  workflow needs that wiring finished and tested against a real WAHA payload before it
  can be called a working WhatsApp bot.
- **Reranking is built but not wired in.** Both `Reranker Cohere` nodes sit on the
  canvas with no connections anywhere in the graph. Retrieval from Supabase currently
  returns raw vector-similarity results straight into the agent, with no reranking
  step actually applied, despite the nodes existing and a Cohere credential being
  implied by their presence.
- **Duplicate, drifting logic between the two agents and two ingestion paths.**
  `AI Agent` and `AI Agent1` are separately configured copies of the same idea (same
  two tools, same memory pattern, different prompts), and `Transform for Vector` and
  `Check Existing Data` independently rebuild very similar business-summary strings
  from the same Google Sheets row in two different Code nodes. Any prompt or schema
  change has to be made twice, correctly, in both places, or the two paths silently
  diverge.
- **Two Google Sheets write paths hit the same rows with different data shapes.**
  `Append Leads` writes fields straight from the Apify response (including
  JSON-stringified nested objects), while `Update Data` writes the parsed, human
  readable version of those same fields, matched by `row_number`. There is no
  explicit ordering or locking between the append-on-scrape and update-on-clean paths,
  so a row can sit in the Sheet in its raw, unparsed form for however long it takes the
  second branch to run and correct it.
- **The lead scoring logic is hardcoded thresholds inside a Code node.** `Clean Data`'s
  lead score (rating and review-count breakpoints, fixed point values) is a business
  decision buried in JavaScript rather than a config value, so tuning what counts as a
  "High" quality lead means editing and redeploying the node's code.
- **The system prompts assume a specific business context that isn't parameterized.**
  Both agents' system prompts hardcode "ReCharge" as the company name and describe a
  single fixed set of two knowledge sources; reusing this workflow for a different
  business or a third data source means rewriting the prompt text, not changing a
  variable.

## What I learned

- In LangChain-style n8n workflows, a node being present, fully configured, and
  connected to a model, memory, and tools does not mean it will ever run: the trigger
  wiring (the `main` connection type) is a separate, easy-to-miss layer from the
  AI-specific connection types (`ai_tool`, `ai_memory`, `ai_languageModel`,
  `ai_embedding`, `ai_textSplitter`, `ai_document`). This workflow has a fully-dressed
  agent node with no trigger at all.
- `retrieve-as-tool` mode on the Supabase vector store node is what turns a plain
  vector search into something an agent can call selectively, mid-conversation,
  rather than always injecting retrieved context up front; the tool's name and
  description strings (`CompanyDocuments`, `RestaurantLeads`) are what the agent
  actually reads to decide when to call it, so they carry real weight in the prompt
  design.
- Splitting one conceptual ingestion pipeline into per-source Code nodes (one for
  Drive documents, one for Sheets rows) instead of a single shared transform makes it
  easy for the two paths' output shape to drift apart over time, exactly as happened
  here between `Transform for Vector` and `Check Existing Data`.

## What I'd do differently

- Wire `WAHA Trigger` into `AI Agent`'s main input and delete or clearly mark `AI
  Agent1`/`When chat message received` as a test-only path, instead of leaving two
  parallel, half-finished agents in the same file with no note distinguishing
  "the real one" from "the test one."
- Either connect the two Cohere reranker nodes into the retrieval path or remove them;
  leaving fully configured but disconnected nodes on the canvas makes the workflow
  look more capable than it is.
- Merge `Transform for Vector` and `Check Existing Data` into one Code node (or one
  shared sub-workflow) so the business-summary format has a single definition instead
  of two that can quietly diverge.
- Move the lead-scoring thresholds and the company name/knowledge-source description
  out of hardcoded JavaScript and system-prompt text into workflow static data or
  environment-style parameters, so reusing this for another business or another
  location doesn't require editing code and prompt strings by hand.
- Add an explicit ordering or idempotency check between `Append Leads` and `Update
  Data` so a lead row is never left in the Sheet in its raw, unparsed form.
