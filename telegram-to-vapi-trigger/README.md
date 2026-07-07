# Telegram to VAPI Trigger

## What it is

An n8n workflow, named "TG -> VAPI" in the export, that wires a Telegram bot to a
LangChain AI Agent so incoming Telegram messages can be handled by an LLM, with one
generic HTTP tool attached that the agent can call. The workflow's own name and the
build manifest both describe its purpose as starting a VAPI voice call from a Telegram
conversation, but the exported JSON does not configure that HTTP tool with any URL,
method, body, or credential: `parameters` on the HTTP Request node is just `{"options":
{}}`. There is nothing in the file (no `url`, no header, no `toolDescription`, no sticky
note) that names VAPI, sets a VAPI endpoint, or attaches a VAPI credential. This README
describes what the exported graph actually contains and states plainly where the VAPI
integration is inferred from naming rather than shown in the node configuration.

## Why it exists

Read as a template or in-progress build for an assistant that can be messaged on
Telegram and, when appropriate, use a tool to trigger a phone call through VAPI (an
API for building voice AI agents that place and receive calls). The five-node graph
matches the shape of that idea: a Telegram trigger feeding an AI Agent with an attached
model, memory, and one HTTP tool. Whether that tool actually reaches VAPI in a working
deployment depends entirely on configuration that either lived in a separate, unsaved
draft of the node, or was never filled in before this export was taken.

## Features

- Receives Telegram messages as the workflow's trigger, no polling required
- Routes each incoming message into a LangChain AI Agent for LLM-driven handling
- Short-term conversational memory so the agent has context across a session
- One HTTP Request tool available for the agent to call, in principle able to hit any
  REST API (VAPI's call-creation endpoint, per the workflow's name and stated purpose)

## Architecture

Five nodes, connected through n8n's LangChain node set:

- **Telegram Trigger** (`n8n-nodes-base.telegramTrigger`, v1.2): starts the workflow on
  incoming Telegram `message` updates. Uses a `telegramApi` credential (a bot token) and
  an n8n-managed webhook.
- **AI Agent** (`@n8n/n8n-nodes-langchain.agent`, v2): the LangChain agent node.
  `parameters` is just `{"options": {}}`, meaning no custom system prompt, text
  template, or output parser is set in this export; it runs on the agent node's
  defaults. It receives the Telegram message on its main input.
- **Simple Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`, v1.3): connected to
  the AI Agent via the `ai_memory` link, giving it a rolling window of prior turns. No
  session key or window-length parameter is set beyond defaults.
- **Google Gemini Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`, v1):
  connected via `ai_languageModel`, configured to `models/gemini-2.0-flash-lite-001`
  with a `googlePalmApi` credential. This is the LLM the agent reasons with.
- **HTTP Request** (`n8n-nodes-base.httpRequestTool`, v4.2): connected via `ai_tool`,
  meaning the agent can invoke it as a callable tool. No URL, HTTP method, headers, body,
  or credential are set in `parameters`; it is an empty tool shell.

Flow: a Telegram message arrives, the Telegram Trigger fires, the AI Agent receives it,
consults the Gemini model and the memory buffer, and may call the HTTP Request tool if
the model decides to. There is no node in this graph that sends a reply back to
Telegram; nothing routes the agent's output to a Telegram "send message" action, so as
exported, the workflow can read a Telegram conversation and (in principle) fire an
outbound HTTP call, but it does not answer the user back inside Telegram.

## Setup

1. In n8n: **Workflows** menu > **Import from File**, and select
   `telegram-to-vapi-trigger.json`.
2. Attach credentials on the nodes that need them:
   - **Telegram Trigger**: a Telegram Bot API credential (bot token from
     [@BotFather](https://t.me/BotFather)).
   - **Google Gemini Chat Model**: a Google Gemini (`googlePalmApi`) credential, an API
     key from Google AI Studio or a Vertex AI service account.
   - **HTTP Request**: has no credential in the export. If the intent is to call VAPI's
     API, this needs a VAPI API key set on the node (as a header, typically
     `Authorization: Bearer YOUR_VAPI_API_KEY`), plus the node's URL and method filled
     in to point at VAPI's call-creation endpoint. None of that is present in this file
     and had to be added manually to make the workflow functional for its stated
     purpose.
3. The workflow is exported inactive (`"active": false`). Activate it in n8n once
   credentials and the HTTP tool's target are configured.

## Usage

Message the connected Telegram bot. The AI Agent receives the message, reasons over it
with Gemini and the conversation memory, and can call the HTTP Request tool if its
(currently unconfigured) tool description and the model's judgment lead it to. As
exported, no reply is sent back into the Telegram chat, so from the user's side nothing
visibly happens after sending a message unless the HTTP tool's target endpoint has an
externally visible side effect, such as VAPI placing an outbound call.

## Challenges

- **The HTTP tool has no destination.** The core piece implied by the workflow's name,
  an HTTP call that starts a VAPI voice call, is not present as configuration: the
  `httpRequestTool` node's `parameters` object contains only `{"options": {}}`, no URL,
  method, body, or auth. The workflow's connections prove the agent can call this tool,
  but the file gives no evidence of what it calls. This was left exactly as found rather
  than guessing a VAPI endpoint shape into the JSON.
- **No system prompt for the agent.** The AI Agent node has no `text` or system message
  parameter set, so its behavior (when to call the HTTP tool, what to say, what
  parameters to pass via `$fromAI` expressions) is entirely the Gemini model's default
  judgment. Any real deployment of this pattern needs a prompt that tells the agent when
  a message warrants placing a call and what information (a phone number, a reason) to
  extract from the conversation first.
- **No reply path back to the user.** There is no Telegram "send message" node and no
  connection routing the AI Agent's output anywhere visible to the person messaging the
  bot. A user would send a message and see nothing come back inside Telegram, regardless
  of what the HTTP tool does.
- **No error handling.** If the HTTP tool call fails, times out, or the target service
  rejects the request, nothing in the graph catches that. There is no IF node, no error
  trigger, and no retry/backoff configuration on the HTTP Request node.
- **Memory is session-only.** `memoryBufferWindow` keeps recent turns in memory for the
  life of the execution; there is no external memory store, so conversation context does
  not persist between separate Telegram sessions or workflow restarts.

## What I learned

- How n8n's `ai_tool` connection type lets any generic node, here a plain
  `httpRequestTool` with zero configuration, become a callable tool for a LangChain
  agent purely through the connection graph, independent of whether the node's own
  parameters are filled in.
- That an exported n8n workflow can carry a name (`"TG -> VAPI"`) that describes intent
  without the node graph itself containing any evidence of that intent; reading the
  actual `parameters` on each node, not the workflow's title, is what tells you what a
  workflow does.
- The specific credential and connection-type wiring an n8n LangChain agent needs at
  minimum: one `ai_languageModel` link, optionally one `ai_memory` link, and zero or
  more `ai_tool` links, all separate from the trigger's own `main` connection.

## What I'd do differently

- I would not treat a workflow's title as a substitute for reading its node
  configuration; the gap between "TG -> VAPI" as a name and an unconfigured HTTP tool
  is exactly the kind of mismatch that should be caught and stated plainly, as it is
  here, rather than describing a VAPI integration that isn't actually in the file.
- I would add the missing pieces before calling this workflow usable: a URL, method,
  and auth on the HTTP Request node targeting VAPI's actual call-creation endpoint, a
  system prompt on the AI Agent describing when to place a call and what to extract
  from the conversation, and a Telegram "send message" node so the bot replies to the
  user.
- I would add basic error handling around the HTTP tool call so a failed or rejected
  call attempt does not just disappear silently.
- I would run the completed workflow against a real Telegram bot and a real VAPI
  sandbox call to confirm the agent actually decides to call the tool at the right
  moments and that the call gets placed; none of that was verified here since the
  workflow, as exported, has no working tool target to test against.

## License

See [LICENSE](LICENSE). Credential requirements are listed in
[CREDENTIALS.md](CREDENTIALS.md).
