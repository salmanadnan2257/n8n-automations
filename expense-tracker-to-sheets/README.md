# Expense Tracker to Sheets

## What it is

An n8n workflow that runs a Telegram bot for logging expenses. A user sends a message
to the bot (either an expense like "spent $12 on coffee" or a question like "what's my
total expense"), an AI agent backed by Google Gemini decides what to do, and it either
appends a row to a Google Sheet, reads back the current rows, or both, then replies to
the user in Telegram with a plain text summary.

## Why it exists

Manually opening a spreadsheet to log every small purchase is friction most people
drop after a few days. Texting a Telegram bot in plain language ("$12 on coffee") and
getting an instant running total back removes that friction. This workflow is a small,
self-contained example of using a chat interface plus an LLM agent as the parsing layer
in front of a spreadsheet, instead of writing custom parsing code.

## Features

- Telegram chat interface: no separate app, the bot lives in an existing Telegram chat.
- Natural language expense entry: the user does not fill in a form or pick fields, the
  LLM extracts the topic and price from a free text message.
- Natural language queries: the same bot answers questions about logged expenses by
  reading the sheet, without a separate command syntax.
- Running total in every "add expense" reply, computed by combining the newly added
  row with the sheet's existing rows.

## Architecture

The workflow has five nodes, wired as one Telegram-driven request/response cycle plus
an AI Agent with two Google Sheets tools attached to it:

1. **Telegram Trigger** (`n8n-nodes-base.telegramTrigger`, listening for `message`
   updates) fires on every incoming message and passes `message.text` downstream.
2. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`) receives the message text as its
   prompt. Its system message instructs it to always call the "Get Expense" tool, and,
   if the user is adding an expense, to call "Add Expense" first, then "Get Expense",
   sum the prices, and reply in a fixed format ("Your $[X] for [Y] has been added. The
   total expense is $[X]."). If the user is only asking about expenses, it calls "Get
   Expense" and answers directly.
3. **Google Gemini Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`) is
   wired into the AI Agent's `ai_languageModel` input; this is the LLM doing the
   reasoning and tool selection.
4. **Add Expense** (`n8n-nodes-base.googleSheetsTool`, operation `append`) is wired
   into the AI Agent's `ai_tool` input. Its two columns, Topic and Expense, are filled
   using `$fromAI()` expressions, meaning the LLM itself decides what string to put in
   each column when it calls this tool (falling back to "Another" for topic or "$0"
   for expense if the message doesn't specify one).
5. **Get Expense** (`n8n-nodes-base.googleSheetsTool`, default read operation) is also
   wired into the AI Agent's `ai_tool` input, and reads back rows from the same sheet
   and tab as Add Expense.
6. **Send a text message** (`n8n-nodes-base.telegram`) takes the AI Agent's `output`
   field (the main data connection from AI Agent) and sends it back to a single, fixed
   Telegram chat ID.

Both Google Sheets tool nodes point at the same spreadsheet ("Expenses") and the same
tab (`Sheet1`, `gid=0`), one for appending, one for reading. There is no code or set
node anywhere in the graph; all parsing, categorization, and summing is done by the
LLM inside the AI Agent node, driven entirely by its system prompt.

## Setup

1. In n8n, go to Workflows menu > Import from File and select `expense-tracker.json`
   in this folder.
2. Create and attach these credentials to the corresponding nodes (see
   CREDENTIALS.md for the full list):
   - A Telegram Bot API credential (Telegram Trigger and Send a text message nodes).
   - A Google Gemini / Google PaLM API credential (Google Gemini Chat Model node).
   - A Google Sheets OAuth2 credential (Add Expense and Get Expense nodes).
3. Point the Add Expense and Get Expense nodes at your own Google Sheet: replace the
   placeholder `YOUR_SHEET_ID` document reference with your sheet, and make sure the
   sheet has a tab with Topic and Expense columns (or update the column mapping to
   match your own headers).
4. Replace the hardcoded `YOUR_TELEGRAM_CHAT_ID` in the Send a text message node with
   the chat ID the bot should reply to. As shipped, this workflow replies to exactly
   one fixed chat, not to whichever chat sent the message; see Challenges below.
5. Activate the workflow so the Telegram Trigger's webhook is live.

## Usage

Message the connected Telegram bot in plain language:

- "spent $15 on groceries" adds a row (Topic: groceries, Expense: $15) and replies with
  the new running total.
- "what have I spent on groceries" (or any other question about the log) triggers a
  read-only lookup and a direct answer, with no row added.

## Challenges

- **Arithmetic is done by the LLM, not by a deterministic node.** The system prompt
  tells the AI Agent to "combine all the prices" itself after reading the sheet back.
  There is no Code or Aggregate node doing the sum. This works for a short list of
  rows but is not something to trust as the sheet grows, since LLM arithmetic over
  many rows of text is not guaranteed to be exact.
- **Field extraction relies entirely on `$fromAI()` and prompt wording.** The Add
  Expense tool's Topic and Expense columns are filled by the model interpreting the
  raw message text, with fallbacks baked into the tool description ("Another" for
  topic, "$0" for expense) rather than validated in a separate step. An ambiguous
  message can silently log a "$0" row instead of failing loudly.
- **The reply format is enforced only by prompt instructions.** The system message
  spells out an exact reply string and says "and that's it, NOTHING ELSE", but nothing
  in the node graph checks or corrects the agent's actual output if it drifts from
  that format.
- **The workflow only replies to one hardcoded Telegram chat.** The Send a text
  message node's chat ID is a fixed value rather than being taken from the incoming
  trigger data, so as built this only works for a single user/chat, not a bot serving
  multiple people.
- **No timestamp is recorded.** The sheet schema is just Topic and Expense; there is
  no date column, so nothing in the workflow supports time-based views like "this
  month's total" without manually adding and populating a date field.
- **No error handling.** There is no branch for a failed Gemini call, a failed Sheets
  append, or a malformed tool call; a failure at any node simply fails the execution.

## What I learned

- n8n's AI Agent node treats other nodes as callable tools through `ai_tool`
  connections, separate from the regular `main` data flow; a single Google Sheets node
  type (`googleSheetsTool`) can be instantiated twice in one workflow, once configured
  for append and once for read, and both get exposed to the agent as distinct named
  tools ("Add Expense", "Get Expense").
- `$fromAI()` lets a tool node pull structured parameter values directly from the
  LLM's reasoning, which removes the need for a separate parsing or Code node, at the
  cost of that logic living entirely inside a prompt string instead of testable code.
- The `ai_languageModel` connection type is how a chat model node like
  `lmChatGoogleGemini` gets wired in as the "brain" for an Agent node, distinct from
  how the Agent's own `main` input and output connections work.

## What I'd do differently

- Replace the LLM-computed running total with a deterministic Sum or Aggregate step
  after Get Expense, so the reported total cannot drift from what is actually in the
  sheet.
- Add a timestamp column populated automatically (for example with a Set node before
  the append call) so the log supports date-based questions later.
- Take the reply chat ID from the trigger's own message data instead of hardcoding a
  single chat ID, so the bot can serve more than one Telegram chat.
- Add basic error handling around the Gemini and Google Sheets calls so a failed API
  call produces a clear message back to the user instead of a silent execution failure.

Not verified end to end here: this was reviewed from the exported workflow JSON only.
Running it live requires a working Telegram bot, a Google Gemini API key, and a real
Google Sheet with matching columns, none of which were exercised in building this
project folder.
