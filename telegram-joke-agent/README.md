# Telegram Joke Agent

## Note on the name

This folder is named "telegram-joke-agent" but the actual workflow file does not
contain any Telegram nodes. Its trigger is n8n's built-in Chat Trigger node
(`@n8n/n8n-nodes-langchain.chatTrigger`), which opens n8n's own test chat window,
not a Telegram bot. There is nothing in the node graph, credentials, or sticky note
that references Telegram. The README below describes what the workflow actually
does rather than inventing a Telegram integration that isn't there.

## What it is

A small n8n workflow that runs a conversational AI agent whose job is to tell jokes.
The agent is backed by an OpenAI chat model, has a short-term conversation memory,
and can call two HTTP-based tools: one that fetches jokes from a public joke API and
one that fetches that API's own documentation page, so the agent can figure out how
to filter its joke requests based on what the user asks for.

## Why it exists

This reads as a small demo or learning exercise for exploring n8n's AI Agent node
and tool-calling pattern, not a production client build. The workflow has five
functional nodes plus one sticky note, no error handling, no persistent storage
beyond in-memory chat history, and the sticky note's own text describes it as a
pattern to copy and adapt ("You can apply this pattern to any website or API").
That framing, combined with the size of the workflow, is why it is presented here
as a build and learning exercise rather than a finished product.

## Features

- Conversational joke-telling agent triggered from n8n's built-in chat window
- Tool-calling: the agent decides on its own when to fetch a joke versus when to
  read the API's documentation versus when to just reply in text
- Short-term memory so the agent can refer back to jokes already told in the same
  session
- A system prompt that defines tone, joke categories, and a few example exchanges
  to keep responses consistent

## Architecture

The workflow has five active nodes, wired through n8n's LangChain-based node set:

- **When chat message received** (`@n8n/n8n-nodes-langchain.chatTrigger`): starts
  the workflow when a message comes in through n8n's own chat interface.
- **Joke agent** (`@n8n/n8n-nodes-langchain.agent`): the AI Agent node. Holds the
  system prompt and orchestrates the model, memory, and tools below.
- **Model** (`@n8n/n8n-nodes-langchain.lmChatOpenAi`): the language model
  connected to the agent, configured for `gpt-4.1-mini`.
- **Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`): a rolling window of
  recent conversation turns, connected to the agent so it has short-term recall
  within a session.
- **Joke API** (`n8n-nodes-base.httpRequestTool`): an HTTP tool wired into the
  agent that calls `https://v2.jokeapi.dev/joke/`, with query parameters supplied
  by the model at call time via n8n's `$fromAI` expression.
- **API docs** (`n8n-nodes-base.httpRequestTool`): a second HTTP tool that fetches
  `https://v2.jokeapi.dev/` itself (the API's landing/docs page, response
  optimized down to page content) so the agent can look up how to filter jokes
  before calling the Joke API tool.
- **Sticky Note**: a plain text note in the canvas explaining the pattern and
  telling whoever opens the workflow to configure credentials on the Model node.

Flow: chat trigger fires, the agent node receives the message, consults its model
and memory, optionally calls the API docs tool and/or the Joke API tool (zero, one,
or both, at the model's discretion), and returns a text reply in the chat window.
There is no Telegram node, no webhook to an external messaging platform, and no
database or file storage node in this workflow.

## Setup

1. In n8n: **Workflows** menu > **Import from File**, and select `workflow.json`.
2. The workflow needs one external credential, attached on the **Model** node:
   - **OpenAI API** (or whichever OpenAI-compatible credential your n8n instance
     uses for the `lmChatOpenAi` node), used to run the `gpt-4.1-mini` model.
3. The two HTTP tool nodes (Joke API, API docs) call a public API
   (`v2.jokeapi.dev`) that requires no authentication, so no credential is needed
   for them.
4. No Telegram credential, webhook, or bot token is required, because there is no
   Telegram node in this workflow.
5. Activate the workflow, then open it in the n8n editor and use the built-in
   "Chat" test panel that the Chat Trigger node exposes to talk to the agent.

## Usage

Open the workflow's chat panel in n8n and type something like "tell me a joke" or
"got any programming jokes?" The agent will decide whether to call the Joke API
tool, consult the API docs tool first, or just respond directly, then reply in the
chat panel. Conversation history persists for the length of that chat session via
the Memory node.

## Challenges

- **Deciding when to call a tool versus just replying.** With two tools attached
  (Joke API and API docs) plus free-form chat, the agent has to judge when a
  message needs a live joke fetch, when it needs to check API docs first to filter
  a request (e.g. "give me a dad joke" mapping to the API's category/type
  parameters), and when it should just answer conversationally. The workflow
  addresses this only through the system prompt's instructions ("Use the Joke API
  tool whenever users ask for jokes... check the API docs if you need to
  understand how to filter") and the tools' own `toolDescription` fields. There is
  no explicit routing logic (no IF node, no separate classifier) in the graph;
  tool selection is left entirely to the model's judgment at runtime, which was
  not verified end to end here since the workflow was not actually executed.
- **Prompt design for a consistent joke tone.** The system prompt is long and
  detailed, it lists interaction styles, joke categories, and worked examples of
  good responses ("Coming right up! Let me grab a good one for you..."). That is
  the workflow's only mechanism for keeping tone consistent; there is no
  temperature setting, few-shot examples node, or output parser constraining the
  model's phrasing beyond the prompt text itself.
- **No conversation continuity across sessions.** The Memory node is a
  `memoryBufferWindow`, which keeps a rolling window of recent messages in memory
  for the current run. It is not backed by a database or external store, so once
  the workflow execution or chat session ends, that history is gone. The
  workflow does not address longer-term memory or user-specific joke history at
  all.
- **Chaining two HTTP tools that both target the same API.** The API docs tool
  fetches the joke API's own documentation page and asks the model to read it in
  order to build correct query parameters for the second tool. This depends on
  the model being able to parse an HTML documentation page (the node sets
  `optimizeResponse: true` and `responseType: "html"` with `onlyContent: true` to
  strip the page down to readable content first) and then translate that into the
  right query parameter name/value pairs for the Joke API tool, which are
  generated dynamically via `$fromAI` expressions rather than fixed in the node.
  Whether this actually produces correctly filtered jokes in practice was not
  verified here.

## What I learned

- How n8n's AI Agent node wires together a model, a memory node, and one or more
  tool nodes purely through the node graph's connection types (`ai_languageModel`,
  `ai_memory`, `ai_tool`) rather than code.
- How `httpRequestTool` nodes use `$fromAI(...)` expressions to let the model
  supply parameter names and values at call time, instead of hardcoding a fixed
  request shape.
- That an HTTP tool can be pointed at a plain documentation page (not just a JSON
  API endpoint) and have its response trimmed to page content, so the model can
  read docs as part of its own reasoning before calling another tool.

## What I'd do differently

- I would not name a project folder "telegram-joke-agent" for a workflow that
  never had a Telegram node in it. That mismatch should have been caught before
  the folder was created, and it is called out plainly above rather than papered
  over.
- I would add at least basic error handling. If the Joke API call fails or times
  out, there is nothing in the graph to catch that and give the user a fallback
  reply.
- I would actually run the workflow end to end with a real OpenAI credential and
  record example transcripts, rather than describing the intended behavior from
  the node graph alone. Nothing here was executed to confirm the agent picks
  tools reliably or that the docs-reading tool improves joke filtering in
  practice.
- I would replace the in-memory buffer with a persistent memory backend if this
  were ever meant to be used by more than one person in more than one sitting.
