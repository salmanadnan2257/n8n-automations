# Telegram Translator Bot

## What it is

An n8n workflow that listens for voice messages sent to a Telegram bot, downloads the
recording, sends it to OpenAI's Whisper audio-translate endpoint, and posts the
resulting English text back to Telegram.

Despite the "translator bot" name, this is not a general text-to-text translator. It
only handles voice messages, and the underlying OpenAI operation (`audio.translate`)
always translates into English, regardless of the source language. There is no
language-detection step and no way to pick a different target language.

## Why it exists

Inferred from the node graph: a quick way to drop a voice note into Telegram in
another language and get an English transcript back, without opening a separate
transcription or translation tool. The workflow's own metadata gives no further
explanation, so this is a plausible read rather than a documented goal.

## Features

- Triggers on incoming Telegram messages.
- Downloads the voice file attached to a message using its Telegram file ID.
- Sends the audio to OpenAI Whisper's translate operation, which transcribes and
  translates it to English in one call.
- Posts the English text back to a Telegram chat.

## Architecture

Four nodes, wired in a straight line:

1. **Telegram Trigger** (`n8n-nodes-base.telegramTrigger`): listens for `message`
   updates from the Telegram Bot API. In the saved workflow this node is disabled and
   the workflow itself is marked inactive, so as exported it does not run.
2. **Get a file** (`n8n-nodes-base.telegram`, resource `file`): takes
   `message.voice.file_id` from the incoming update and downloads that voice
   recording from Telegram.
3. **Translate a recording** (`@n8n/n8n-nodes-langchain.openAi`, resource `audio`,
   operation `translate`): sends the downloaded audio to OpenAI's Whisper
   audio-translate endpoint, which returns an English transcription of the speech.
4. **Send a text message** (`n8n-nodes-base.telegram`): posts the translated text
   back to Telegram, to a fixed chat ID hardcoded in the node rather than derived
   from the incoming message's sender.

There is no language-detection node, no branching for non-voice message types (text,
stickers, images), and no formatting step beyond passing the OpenAI response straight
into the Telegram message body.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create and attach credentials for:
   - **Telegram API**: a bot token from BotFather, used by the trigger and both
     Telegram nodes.
   - **OpenAI API**: an API key with access to the audio endpoints, used by the
     translate node.
3. Re-enable the Telegram Trigger node (it is disabled in the exported file) and
   activate the workflow.
4. Replace the hardcoded `chatId` placeholder on the "Send a text message" node with
   a real chat ID, or rework it to use the sender's chat ID from the trigger data so
   replies go back to whoever sent the voice message.

See `CREDENTIALS.md` for the full list of what each node needs.

## Usage

Send a voice message to the connected Telegram bot. The bot downloads it, runs it
through Whisper's translate endpoint, and replies with the English text in the chat
configured on the "Send a text message" node.

## Challenges

- **Replying to the right chat.** The "Send a text message" node has a chat ID typed
  in directly rather than pulled from the trigger payload. As built, the bot always
  replies to one fixed chat no matter who sent the voice message. That's a real
  design limitation, not something this workflow works around.
- **Non-voice messages.** The trigger listens for any `message` update, but only the
  "Get a file" node's `voice.file_id` expression is wired downstream. A text message,
  photo, or sticker would fail at that node since there is no `voice` object on the
  payload. There is no IF node or switch to branch on message type, so the workflow
  only really works for voice notes.
- **Target language is fixed.** Whisper's `audio.translate` operation always outputs
  English; there is no way to specify a different target language. If the goal were
  translating into other languages, this endpoint choice would not support it and a
  chat-completion style translation prompt would be needed instead.
- **Audio length and format limits.** OpenAI's audio endpoints cap file size and
  duration. Nothing in the graph checks the file before sending it, so a long voice
  message would simply fail at the "Translate a recording" node with no fallback or
  error handling.
- **Workflow shipped inactive.** Both the workflow itself (`active: false`) and the
  Telegram Trigger node (`disabled: true`) are turned off in the exported file, so it
  would not run as-is without first flipping both switches back on.

## What I learned

- n8n's OpenAI Langchain node exposes Whisper's audio endpoints as a `resource:
  "audio"` with `operation: "translate"` or `operation: "transcribe"`, and it's easy
  to reach for `translate` without noticing it hardcodes the output language to
  English.
- Wiring a Telegram file ID straight from `$json.message.voice.file_id` works fine for
  the happy path but has no guard for messages that aren't voice notes.
- A workflow can be fully wired and look complete while still shipping with its
  trigger disabled and the whole workflow marked inactive, which is easy to miss
  without opening the JSON directly.

## What I'd do differently

- Read the chat ID for the reply from the incoming trigger data instead of hardcoding
  it, so the bot replies to whoever actually sent the message.
- Add an IF node right after the trigger to branch on message type, so text, photos,
  and stickers get a sensible response (or are ignored) instead of failing silently
  at the file-download step.
- Add error handling around the OpenAI call for oversized or unsupported audio files,
  with a Telegram message back to the user explaining the failure instead of a silent
  workflow error.
- If translating into languages other than English was ever the actual intent, swap
  the Whisper translate operation for a transcribe step followed by a chat-completion
  prompt that can target any language.
