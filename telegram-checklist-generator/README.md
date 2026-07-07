# Telegram Checklist Generator

## What it is

A Telegram bot workflow: send it a free-text message describing your day or a jumble of tasks, and it replies with the same tasks broken out as a checklist, first as one message, then as individual paced follow-up messages, one per item.

## Why it exists

People dump their day's tasks as a run-on sentence ("I have to do X, then Y, then Z"). Turning that into a checklist by hand is a small chore that repeats daily. This workflow does the extraction with an LLM and then delivers the result twice: once as a single block for a quick read, and once as a drip of individual messages so each task shows up as its own Telegram notification.

## Features

- Telegram-triggered: any message sent to the bot kicks off the flow.
- LLM-based task extraction that turns a paragraph into a clean JSON array of task strings.
- Sends the full checklist as one message immediately.
- Also splits the array into individual items and sends each as a separate Telegram message, spaced out by a Wait node inside a loop, instead of dumping everything at once.

## Architecture

1. **Telegram Trigger** (`n8n-nodes-base.telegramTrigger`, listening for `message` updates) starts the flow. Note: this node is saved with `disabled: true` in the exported JSON, so the workflow needs re-enabling on import.
2. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`) receives `{{ $json.message.text }}` as input, backed by a **Google Gemini Chat Model** node (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`). Its system prompt instructs it to output only a single-line JSON array of task strings, no prose, no markdown fences.
3. **Edit Fields** (`n8n-nodes-base.set`) takes the agent's `output` and assigns it to a field typed as `array`, coercing the LLM's string output into an actual array value for downstream nodes.
4. From there the flow forks:
   - **Send a text message** (`n8n-nodes-base.telegram`) joins the array items with newlines (via an inline function in the expression) and sends the whole checklist as one message.
   - **Split Out** (`n8n-nodes-base.splitOut`) splits the `output` array into one n8n item per task.
5. **Loop Over Items** (`n8n-nodes-base.splitInBatches`) iterates the split items one at a time.
6. **Wait** (`n8n-nodes-base.wait`) pauses between iterations (default wait settings, no explicit duration set in this export).
7. **Send a text message1** (`n8n-nodes-base.telegram`) sends the current item's text as its own Telegram message, then loops back into "Loop Over Items" to process the next one, continuing until the batch is exhausted.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Re-enable the "Telegram Trigger" node; it is imported disabled.
3. Create/attach credentials for:
   - **Telegram Bot API** on the "Telegram Trigger", "Send a text message", and "Send a text message1" nodes.
   - **Google Gemini API** on the "Google Gemini Chat Model" node.
4. Replace the `YOUR_TELEGRAM_CHAT_ID` placeholders in the two Telegram send nodes with the actual chat ID you want the bot to reply to (or, better, wire them to `{{ $json.message.chat.id }}` from the trigger so the bot replies to whoever messaged it, since as exported it always sends to one hardcoded chat).
5. Activate the workflow.

## Usage

Message the Telegram bot with a description of your tasks for the day. It replies once with the full checklist, then again with each task as its own message, one every wait interval.

## Challenges

- **Hardcoded chat ID, not the sender's.** Both Telegram send nodes use a literal chat ID rather than `{{ $json.message.chat.id }}` from the trigger. As built, the workflow only ever replies to one specific chat regardless of who messages the bot, which only works as a personal single-user bot, not a bot other people can use.
- **No JSON parse safety net.** The agent is prompted to output a raw JSON array, but "Edit Fields" assigns `{{ $json.output }}` directly to an `array`-typed field with no explicit JSON.parse or try/catch. If the model returns anything other than a strictly valid array literal (extra text, a trailing comma), this coercion can fail or silently produce something the Split Out node can't split cleanly.
- **Wait node has no configured duration.** The "Wait" node in the loop uses default settings; the pacing between individual task messages depends on whatever n8n's default wait behaves as, not a deliberately chosen interval, so the "paced" delivery is really just "however the trigger config resolves" the exporter used.
- **Split Out assumes `output` is always an array.** If the LLM ever returns a single string instead of an array (a one-task input, for example), "Split Out" and the subsequent loop may behave unexpectedly since the field type was force-set to `array` upstream but the actual runtime shape wasn't validated.
- **Disabled trigger on import.** The workflow ships with its only trigger disabled, so a straight import-and-activate will silently do nothing until someone notices and flips the node back on.

## What I learned

Coercing an LLM's freeform text output into a strongly typed n8n field (via "Edit Fields" set to `array`) is a lightweight way to get structured data out of a chat model without a dedicated JSON-parsing code node, but it only works cleanly when the model's output format is enforced tightly by the prompt, there's no fallback if it isn't. Running the paced delivery through `splitInBatches` + `wait` in a loop is a straightforward pattern for "send N messages, one at a time, with a pause" without needing a separate scheduling mechanism.

## What I'd do differently

I would replace the hardcoded chat ID with `{{ $json.message.chat.id }}` so any user who messages the bot gets checklist replies, add an explicit JSON parse step with error handling before the Edit Fields node so a malformed LLM response fails loudly instead of producing a broken array, and set an explicit duration on the Wait node so the message pacing is a deliberate choice rather than a default.
