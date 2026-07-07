# AI Motivational Quotes Bot

## What it is

An n8n workflow that generates a short motivational quote with an LLM, turns that
quote into an image, and sends the image to a Telegram chat on a schedule.

## Why it exists

The node graph and naming (personal Telegram credentials, a single hardcoded chat
ID) point to a personal automation: an AI-generated motivational quote delivered as
an image to one Telegram chat, without a human writing or picking the quote each
time. The schedule trigger in the saved workflow is set to fire every 10 seconds,
which does not match a "quote of the day" use case. That looks like a leftover
testing setting rather than the intended production cadence, and there is no way
to confirm what interval was meant to ship, so this is stated plainly rather than
guessed.

## Features

- Generates a short quote with an LLM agent on every run, no manual writing needed.
- Keeps a conversation memory buffer across runs so the agent has some notion of
  prior output, not just a stateless one-shot prompt.
- Converts the generated quote text directly into an image using an AI image
  generation model, rather than sending plain text.
- Delivers the finished image as a Telegram photo message.

## Architecture

The workflow has five nodes, wired as one linear pipeline with two side-inputs
feeding the agent:

1. **Schedule Trigger** (`n8n-nodes-base.scheduleTrigger`): fires the workflow on
   an interval (configured as every 10 seconds in the saved JSON).
2. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`): the core node. It is given the
   fixed instruction "Give a quote" and a system message telling it to generate
   one very short quote and return only the quote text, nothing else.
3. **Google Gemini Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`,
   model `gemini-2.0-flash-lite`): feeds the AI Agent as its language model via the
   `ai_languageModel` connection. It is not in the main data flow, it is a sub-input
   the agent calls into.
4. **Simple Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`): feeds the AI
   Agent as its memory via the `ai_memory` connection, using a fixed custom session
   key. Every run shares the same session, so the agent's short window of prior
   turns persists across executions rather than resetting each time.
5. **OpenAI** (`@n8n/n8n-nodes-langchain.openAi`, resource `image`, model
   `gpt-image-1`): takes the AI Agent's text output (`{{ $json.output }}`) as the
   image prompt and generates a PNG.
6. **Telegram** (`n8n-nodes-base.telegram`, operation `sendPhoto`): sends the
   generated image binary to a fixed Telegram chat ID as a photo message.

Main data flow: Schedule Trigger -> AI Agent -> OpenAI (image) -> Telegram.
Gemini and Simple Memory attach to the AI Agent as language-model and memory
sub-inputs rather than sitting in that main chain.

## Setup

1. In n8n, go to Workflows menu > Import from File, and select `workflow.json`
   from this folder.
2. Create and attach the following credentials in n8n (see CREDENTIALS.md):
   - A Google Gemini (Google PaLM API) credential for the **Google Gemini Chat
     Model** node.
   - An OpenAI API credential for the **OpenAI** node (used for image generation,
     model `gpt-image-1`).
   - A Telegram API credential (bot token) for the **Telegram** node.
3. Open the **Telegram** node and set `chatId` to the actual chat or channel you
   want to send to. The imported file ships with a placeholder value.
4. Open the **Schedule Trigger** node and set a real interval (for example daily
   at a fixed time, with the correct timezone in the n8n instance settings). The
   imported file ships with a 10-second interval, which is not usable as-is.
5. Activate the workflow once credentials and schedule are set.

## Usage

Once active, the workflow runs unattended on the configured schedule: it asks the
LLM for a quote, renders that quote as an image, and posts the image to the
configured Telegram chat. No manual input is needed per run.

## Challenges

- **Duplicate quotes over time**: the only mechanism against repeats is the Simple
  Memory node's buffer window, shared across all runs through a fixed session key.
  A window buffer only holds a limited number of recent turns, so it can discourage
  immediate repeats but cannot prevent the same quote resurfacing after enough runs
  have passed. There is no separate store of previously sent quotes to check
  against, so long-term duplicate avoidance is not solved by this graph.
- **LLM output consistency and formatting**: the system message asks the model to
  "return only the quote" with no output parser, structured output node, or
  post-processing step in the graph. Formatting consistency depends entirely on the
  model following that one instruction; nothing in the workflow validates or
  cleans the text before it becomes an image prompt.
- **Schedule trigger reliability and timezone handling**: the saved trigger uses a
  plain seconds interval (10 seconds) with no cron expression and no explicit
  timezone handling. That is fine for testing but would need to be replaced with a
  cron-style schedule and a confirmed timezone for any real "daily quote" use, which
  the workflow as saved does not do.
- **Delivery channel API limits and failure handling**: the pipeline calls two
  paid, rate-limited APIs (image generation, then Telegram) with no error-handling
  branch, retry node, or fallback path. If image generation fails or Telegram
  rejects the send, the run simply fails with nothing delivered, for example there
  is no fallback to sending the quote as plain text if the image step fails.

## What I learned

- In n8n's LangChain nodes, the language model and memory are not part of the main
  data flow; they attach to the AI Agent node through dedicated `ai_languageModel`
  and `ai_memory` connections, so the agent's own `main` output is just its
  finished text, not the raw model or memory objects.
- An LLM's text output can be chained straight into an image generation node with
  an expression like `{{ $json.output }}`, letting an agent's writing become an
  image prompt without an intermediate formatting node.
- Telegram's `sendPhoto` operation in n8n expects binary data from the previous
  node (`binaryData: true`), so the image node upstream has to actually output
  binary content, not just a URL or base64 string in JSON.

## What I'd do differently

- Replace the 10-second interval with a proper cron expression and a stated
  timezone, since a motivational quote workflow only makes sense on a daily or
  similarly spaced cadence.
- Add a real duplicate-avoidance step, for example storing sent quotes in an n8n
  data table or external store and checking new output against that history before
  sending, instead of relying on a short memory buffer.
- Add error handling around the image generation and Telegram send steps, with a
  fallback to sending the plain quote text if image generation fails, so a single
  API hiccup does not silently drop the day's quote.
- Make the Telegram chat ID configurable (workflow setting or credential-linked
  value) rather than hardcoded in the node parameters, so the same workflow can be
  reused for a different chat without editing node internals.
