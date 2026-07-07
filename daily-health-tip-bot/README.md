# Daily Health Tip Bot

## What it is

A small n8n workflow that runs on a daily schedule, asks an LLM agent for one concrete
health tip, and sends it as a Telegram message.

## Why it exists

A minimal example of the "scheduled AI content, delivered via chat" pattern used in
several other workflows in this collection (compare `daily-health-tip-bot` against the
scheduled SEO post generators, which follow the same trigger-then-generate-then-
deliver shape at much larger scale). This one is intentionally small: single-purpose,
few nodes, easy to read end to end.

## Features

- Daily scheduled trigger at a fixed time.
- LLM agent instructed to return exactly one health tip and nothing else (no
  preamble, no formatting), via Google Gemini.
- Session-scoped conversation memory attached to the agent, so repeated runs share
  context under one fixed session key rather than each run starting cold (though with
  a fixed session key, that also means every run shares the same memory thread).
- Delivers the finished tip as a plain Telegram text message.

## Architecture

Trigger: `Schedule Trigger` (daily, fixed hour/minute).

1. `Edit Fields` (Set node) stamps the current timestamp onto the item. This node is
   disabled in the exported workflow (`"disabled": true`), so as imported it passes
   data straight through without doing anything; it looks like a debugging aid left
   in place rather than an active step.
2. `AI Agent` (`@n8n/n8n-nodes-langchain.agent`) runs a fixed prompt ("Return the
   health tip and health tip ONLY") against a system message defining the assistant's
   role (a helpful assistant whose job is to think of one concrete, astute, pertinent
   health tip).
3. `Google Gemini Chat Model` supplies the language model backing the agent.
4. `Simple Memory` (`memoryBufferWindow`) attaches a buffered conversation history to
   the agent, keyed on a single hardcoded session ID rather than a per-run or
   per-user key.
5. `Send a text message` (Telegram node) sends the agent's output text to a fixed
   Telegram chat.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- Google Gemini (PaLM API) credential, for the AI Agent's language model.
- Telegram Bot API credential, plus the numeric chat ID to send the daily tip to
  (replace the `YOUR_TELEGRAM_CHAT_ID` placeholder in the Telegram node).

## Usage

Enable the schedule trigger to get one health tip delivered to Telegram at the
configured time each day, or run manually to test. The disabled `Edit Fields` node
can be safely left disabled or removed; it currently does nothing.

## Challenges

- **Fixed, shared memory session key.** `Simple Memory` uses a single hardcoded
  session key rather than a per-day or per-run identifier, so the buffered
  conversation history accumulates across every scheduled run indefinitely rather
  than resetting; over months of daily runs, the memory buffer could grow large or
  cause the agent to reference irrelevant older tips.
- **A disabled dead node left in the graph.** `Edit Fields` is present, wired into the
  main path, and disabled, so it's effectively a no-op pass-through. It's harmless as
  is, but it's the kind of leftover that makes a small workflow slightly harder to
  read than it needs to be ("what does this do?" costs a moment even when the answer
  is "nothing, it's off").
- **No duplicate-tip protection.** Nothing in the workflow checks whether today's
  generated tip repeats a recent one; with a shared memory buffer feeding the same
  prompt daily, tip repetition is plausible over time and nothing here would catch it.
- **Single fixed destination chat.** Like the other Telegram-delivery utilities in this
  collection, the chat ID is hardcoded rather than parameterized.

## What I learned

A workflow this small still surfaces a real memory-design question: attaching
conversation memory to a recurring scheduled agent only makes sense if the session key
actually resets on a sensible boundary (per day, here); a single fixed key turns
"memory" into an ever-growing, never-cleared buffer, which is a different (and
probably unintended) behavior than a fresh context each day.

## What I'd do differently

I'd key the memory session to the run date so each day's generation starts from a
clean, bounded context (or drop memory entirely, since a single-shot "give me a tip"
prompt doesn't obviously benefit from conversation history), remove the disabled
`Edit Fields` node, and add a simple duplicate check against recently sent tips before
sending.
