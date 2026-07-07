# Content Business Chat Agent

A note on naming: in the live n8n instance this workflow is saved under the name
"N8N Chat Agent for YouTube." That name is misleading. It does not touch YouTube
data, transcripts, or video content in any way; it is a website chatbot for a
content-writing business. This folder uses the honest, descriptive name instead.

## What it is

A webhook-based conversational AI agent, built as a website chat widget, for
1SecondCopy, a content-writing company. It answers questions about the business
(turnaround times, pricing, past clients, editorial process) and, if a visitor wants
a quote, walks them through booking a calendar meeting: collects their name, email,
and preferred time, checks the calendar for availability, and creates the event.

## Why it exists

A content-writing business gets the same handful of questions from website visitors
over and over (how fast, how much, who have you worked with) and loses leads when a
human isn't available to answer immediately or to book a call. This workflow gives
the site a chatbot that can answer those questions with a fixed knowledge base baked
into its system prompt and hand qualified visitors straight into a booked calendar
slot, without a person in the loop for the initial conversation.

## Features

- Persistent chat trigger endpoint that a website widget can connect to.
- A single LLM agent with a fixed persona ("Nick"), business facts, tone rules
  (short, casual, a bit witty), and an explicit anti-derailment instruction that
  steers off-topic conversations back to the business.
- Short-term conversation memory (last 10 exchanges) so the bot keeps context within
  one chat session.
- Two calendar tools the agent can call on its own judgment: one to check existing
  availability, one to create a new event with the visitor as an attendee.
- Timezone-aware scheduling instructions (the persona is fixed to Edmonton, MT).

## Architecture

Four nodes, all in one graph, no branching logic and no code nodes:

1. **When chat message received** (`@n8n/n8n-nodes-langchain.chatTrigger`, mode
   `webhook`, `public: true`): the entry point a website chat widget posts messages
   to. Every incoming visitor message starts a run here.
2. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`): the core of the workflow. Its
   system prompt hard-codes the business persona, facts (pricing, turnaround, past
   clients, editorial process), the current date and timezone, and a scripted
   sequence for booking a meeting (name, email, preferred time, confirm). It decides
   on every turn whether to just answer, or to call one of its attached tools.
3. **OpenAI Chat Model** (`@n8n/n8n-nodes-langchain.lmChatOpenAi`): the language
   model backing the AI Agent node, connected via the `ai_languageModel` link. No
   explicit model ID is set in the node parameters, so it uses whatever OpenAI
   credential default is configured at import time.
4. **Window Buffer Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`,
   `contextWindowLength: 10`): attached via `ai_memory`, gives the agent
   conversational continuity across the last 10 messages in a session.
5. **Google Calendar** (`n8n-nodes-base.googleCalendarTool`, operation `getAll`):
   attached via `ai_tool`. The agent calls this to look up existing events between
   an AI-inferred start and end date (`$fromAI("afterDate")`, `$fromAI("beforeDate")`)
   before offering the visitor a time slot.
6. **Google Calendar1** (`n8n-nodes-base.googleCalendarTool`, create-event
   operation): also attached via `ai_tool`. The agent calls this once a visitor
   confirms a time, passing an AI-inferred start, end, meeting summary, and the
   visitor's email as an attendee alongside the business's own calendar email.

All tool arguments (dates, attendee email, meeting title) are extracted by the model
itself at call time via `$fromAI(...)` expressions; there is no separate node that
validates or normalizes what the model decides to pass into the calendar API calls.

## Setup

1. In n8n: Workflows menu > Import from File, select `workflow.json` from this
   folder.
2. Credentials needed, added in n8n's Credentials section and attached to the
   relevant nodes:
   - OpenAI API (used by the AI Agent's chat model)
   - Google Calendar OAuth2 (used by both calendar tool nodes, pointed at the
     business's own booking calendar)
3. Replace the calendar identifier in both Google Calendar nodes
   (`YOUR_CALENDAR_EMAIL_HERE` in this copy) with the real calendar you want
   availability checks and bookings to run against.
4. Update the system prompt's business facts (pricing, turnaround time, client
   list, persona name, timezone) to match whichever business is actually running
   this, since they are currently hard-coded for 1SecondCopy specifically.
5. Activate the workflow and connect the chat trigger's webhook URL to a website
   chat widget, or test it directly through n8n's built-in chat panel.

## Usage

A visitor opens the chat widget and asks a question or asks to book a call. The
agent answers directly from its system-prompt knowledge, or, if booking is
requested, gathers name, email, and preferred time, checks the calendar tool for
conflicts, and creates the event once confirmed. No dashboard or admin step exists
outside the calendar itself; a completed booking simply shows up as a calendar event
with the visitor as an attendee.

## Challenges

- **A misleading workflow name is a real risk in itself.** The workflow is titled
  "N8N Chat Agent for YouTube" in the source instance, and its OpenAI credential is
  even labeled "YouTube_Feb 4", but nothing in the node graph touches YouTube in any
  way. Anyone handed this file without context, including a future maintainer or an
  interviewer, would reasonably misjudge what it does from its name alone.
- **All business knowledge lives in one prompt with no source of truth.** Pricing,
  turnaround time, and the client list are hard-coded into the AI Agent's system
  message as plain text. If any of those facts change, the workflow itself has to be
  edited; there's no connected knowledge base, sheet, or CMS node feeding this
  agent, so accuracy depends entirely on whoever last updated the prompt by hand.
- **Tool arguments come straight from model inference with no validation.** Every
  date, email, and meeting summary passed to the Google Calendar tools is extracted
  by the LLM via `$fromAI(...)` at call time. There's no code node that checks the
  visitor's email is well-formed or that a proposed meeting time is actually in the
  future before the create-event call fires.
- **No fallback for calendar API failure.** If the Google Calendar OAuth2 credential
  expires or the API call errors, the graph has no error-handling branch; the agent
  just gets the tool's failure back and has to decide how to respond conversationally,
  with no logged alert to a human that a booking attempt failed.
- **Anti-derailment relies entirely on prompt wording.** The system prompt tells the
  model to redirect off-topic or adversarial messages, but there's no separate
  moderation or guardrail node checking that it actually does; a prompt-only defense
  is inherently softer than one backed by a rule-based or classifier check.
- **Session identity and memory scope aren't visible in the graph.** The buffer
  memory holds 10 messages, but the chat trigger doesn't show explicit session-key
  logic in its parameters, so how sessions are distinguished between different site
  visitors depends on defaults in the chat trigger node that aren't visible from the
  workflow JSON alone; this is worth confirming directly in the running instance
  rather than assumed from the file.

## What I learned

Building a business chatbot as one agent node with hard-coded facts and two tool
calls is a genuinely fast way to ship something usable, the whole decision logic for
"answer directly" versus "book a meeting" versus "check availability first" lives
inside the model's own reasoning rather than in explicit workflow branches. The
tradeoff is that every constraint (don't discuss unrelated topics, confirm details
before booking, stay in one timezone) is enforced by prompt instruction alone, so
the workflow's correctness is only as good as the model's adherence to that prompt
on any given turn, and there's no separate node forcing it.

## What I'd do differently

I'd rename the workflow the moment it stopped being a YouTube-specific experiment,
since a stale name like this actively misleads anyone maintaining it later. I'd also
pull the business facts (pricing, turnaround, clients) out of the system prompt and
into a small external source, even a Google Sheet or Airtable node the agent reads
from at the start of each conversation, so updating a price doesn't mean editing and
redeploying the whole workflow. Finally I'd add a lightweight validation step before
the create-event tool call, confirming the collected email looks valid and the
proposed time is in the future, rather than trusting the model's own judgment on
both.
