# Ultimate Personal Assistant System

## What it is

A five-workflow n8n system built around one Telegram bot. A user sends a text or voice
message to the bot. A top-level orchestrator workflow reads the message, decides what
kind of task it is, and calls one of four specialist sub-workflows to actually do the
work: calendar, contacts, email, or blog content creation. Each sub-workflow is a
self-contained LangChain agent with its own system prompt and its own set of tools
(Google Calendar, Airtable, Gmail, or a web search tool), wired up so n8n can invoke it
as a callable "tool" from the orchestrator.

## Why it exists

This is a personal assistant that lives entirely inside Telegram: no app to install,
no separate dashboard. Instead of one giant agent with every tool bolted on (which
tends to confuse LLMs about which tool to pick and blows up the system prompt), the
work is split into an orchestrator that only routes, and specialist agents that only
know their own domain. Each specialist can be developed, tested, and reused
independently of the others, and can be swapped or upgraded without touching the
routing logic.

## Features

- Telegram bot entry point, accepts both typed text and voice messages.
- Voice messages are downloaded from Telegram and transcribed with OpenAI's audio
  transcription endpoint before being handed to the orchestrator as text.
- Orchestrator agent (GPT-4o) that routes every request to exactly one of: calendar
  agent, contact agent, email agent, content creator agent, a Tavily web search tool,
  or a calculator tool.
- Per-chat conversation memory (window buffer keyed on the Telegram chat ID) so the
  orchestrator has short-term context across messages in the same chat.
- Calendar sub-agent: create, read, update, and delete Google Calendar events,
  including events with attendees.
- Contact sub-agent: look up and upsert contacts in an Airtable base (name, email,
  phone number).
- Email sub-agent: send email, create drafts, reply to a message, list/search emails,
  list labels, apply labels, and mark messages unread, all via Gmail.
- Content creator sub-agent: research a topic with Tavily web search, then write an
  HTML-formatted blog post with an Anthropic Claude model, preserving citation links.
- Built-in cross-agent rule: before sending or drafting an email, or creating a
  calendar event with an attendee, the orchestrator is instructed to call the contact
  agent first to resolve a name into an email address.

## Architecture

**Orchestrator: `orchestrator-ultimate-personal-assistant.json`**

- `Telegram Trigger` (`n8n-nodes-base.telegramTrigger`) fires on incoming messages.
- `Switch` (`n8n-nodes-base.switch`) branches on whether `message.voice.file_id`
  exists (voice) or `message.text` exists (typed text).
- Voice branch: `Download File` (`n8n-nodes-base.telegram`, file resource) pulls the
  voice file from Telegram, then `Transcribe` (`@n8n/n8n-nodes-langchain.openAi`,
  audio resource, transcribe operation) turns it into text.
- Text branch: `Set 'Text'` (`n8n-nodes-base.set`) copies `message.text` into a `text`
  field so both branches feed the agent the same shape of data.
- `Ultimate Assistant` (`@n8n/n8n-nodes-langchain.agent`, GPT-4o via
  `OpenAI Chat Model`) is the routing brain. Its system prompt explicitly tells it
  never to write email or summary content itself, only to call the right tool.
- Four sub-workflows are attached as callable tools via
  `@n8n/n8n-nodes-langchain.toolWorkflow` nodes (`Email Agent`, `Calendar Agent`,
  `Contact Agent`, `Content Creator Agent`), each pointing at one of the sub-workflow
  files below by workflow ID. This is n8n's "Call n8n Workflow Tool" pattern: the
  orchestrator's LLM decides when to invoke a named tool, and n8n runs the referenced
  sub-workflow synchronously, passing a `query` string and returning its output as the
  tool result.
- Two direct HTTP/utility tools are also attached: `Tavily`
  (`@n8n/n8n-nodes-langchain.toolHttpRequest`, POSTs to the Tavily search API) and
  `Calculator` (`@n8n/n8n-nodes-langchain.toolCalculator`).
- `Window Buffer Memory` (`@n8n/n8n-nodes-langchain.memoryBufferWindow`) is keyed on
  the Telegram chat ID so each chat gets its own short-term memory.
- The agent's final `output` is sent back to the user with `Response`
  (`n8n-nodes-base.telegram`).

**Sub-workflows** are each triggered by `n8n-nodes-base.executeWorkflowTrigger` ("When
Executed by Another Workflow", passthrough input), meaning they only run when called
by the orchestrator (or manually for testing), never on their own trigger. Each ends
in a two-way branch on the inner agent node's error output: a `Success` set node
copies `output` into a `response` field, a `Try Again` set node returns a fixed
fallback string if the agent's own execution errored out.

- `sub-agent-calendar.json` (🤖Calendar Agent): a
  `@n8n/n8n-nodes-langchain.agent` (GPT-4o) with five
  `n8n-nodes-base.googleCalendarTool` tools: Create Event, Create Event with
  Attendee, Get Events, Update Event, Delete Event. The system prompt tells the model
  it must call Get Events first to obtain an event ID before it can update or delete
  anything, and to default to a one-hour duration when none is given.
- `sub-agent-contacts.json` (🤖Contact Agent): a
  `@n8n/n8n-nodes-langchain.agent` (GPT-4o) with two `n8n-nodes-base.airtableTool`
  nodes against one Airtable base/table: Get Contacts (search) and Add or Update
  Contact (upsert, matched on the `name` column, storing name/email/phoneNumber).
- `sub-agent-email.json` (🤖Email Agent): a `@n8n/n8n-nodes-langchain.agent` (GPT-4o)
  with seven `n8n-nodes-base.gmailTool` nodes: Send Email, Create Draft, Email Reply,
  Get Emails, Get Labels, Label Emails, Mark Unread. The system prompt requires HTML
  formatting and a fixed "Nate" sign-off, and requires the model to call Get Emails
  (and Get Labels, where relevant) first to obtain a message ID before replying,
  labelling, or marking a message unread.
- `sub-agent-content-creator.json` (🤖Content Creator Agent): a
  `@n8n/n8n-nodes-langchain.agent` running on Anthropic Claude (via
  `@n8n/n8n-nodes-langchain.lmChatAnthropic`, not GPT-4o like the others) with one
  `@n8n/n8n-nodes-langchain.toolHttpRequest` tool that POSTs to the Tavily search API.
  The system prompt requires HTML output with real headings and preserved citation
  links from the Tavily results.

Every sub-agent node has `onError: continueErrorOutput` set, which is what makes the
Success/Try Again branching possible: an LLM or tool failure inside the sub-agent
routes to the second output instead of crashing the whole sub-workflow execution.

## Setup

1. In n8n, go to Workflows > Import from File and import all five files in this
   folder. Import the four sub-agents first so their workflow IDs exist, then the
   orchestrator.
2. After importing, each `toolWorkflow` node in the orchestrator (`Email Agent`,
   `Calendar Agent`, `Contact Agent`, `Content Creator Agent`) references a
   sub-workflow by ID. n8n's import will generally remap these automatically if all
   five files are imported into the same instance; if a node shows a broken workflow
   reference, reopen it and reselect the matching imported sub-workflow from the list.
3. Create and attach credentials for each of the following (see CREDENTIALS.md for
   the full list with purposes):
   - Telegram Bot API (bot token, used by the trigger, the voice file download, and
     the response node)
   - OpenAI API (used for GPT-4o chat in the orchestrator, calendar, contact, and
     email agents, and for audio transcription of voice messages)
   - Anthropic API (used by the content creator agent's chat model)
   - Google Calendar OAuth (used by the calendar agent's five calendar tools)
   - Gmail OAuth (used by the email agent's seven Gmail tools)
   - Airtable Personal Access Token (used by the contact agent's two Airtable tools)
   - Tavily API key (used by the orchestrator's and content creator agent's web
     search tool; this key is embedded directly in the HTTP request body as
     `YOUR_API_KEY_HERE`, since Tavily is called via a raw HTTP Request tool node, not
     a dedicated n8n Tavily node)
4. Replace `YOUR_API_KEY_HERE` in the two Tavily HTTP Request tool nodes
   (`orchestrator-ultimate-personal-assistant.json`'s `Tavily` node and
   `sub-agent-content-creator.json`'s `Tavily` node) with a real Tavily API key, or
   better, move it into an n8n credential/expression instead of a literal in the JSON
   body.
5. Replace `YOUR_CALENDAR_EMAIL@gmail.com` in all five Google Calendar tool nodes in
   `sub-agent-calendar.json` with the calendar you want the agent to manage.
6. Set up an Airtable base with a "Contacts" table containing at least `name`,
   `email`, and `phoneNumber` fields (text). Point the contact agent's two Airtable
   nodes at that base and table.
7. Activate all five workflows.

## Usage

Message the Telegram bot in plain language, by text or voice note. Examples:

- "What's on my calendar tomorrow?" routes to the calendar agent's Get Events tool.
- "Schedule a call with Jane Doe at 3pm Thursday for 30 minutes" routes to the
  contact agent first (to resolve Jane Doe's email), then the calendar agent's Create
  Event with Attendee tool.
- "Send an email to Jane Doe asking if she's free Friday" routes to the contact agent
  for the email address, then the email agent's Send Email tool.
- "Write a blog post about the future of solar panels" routes to the content creator
  agent, which searches Tavily for sources and returns an HTML draft.
- A voice note asking any of the above is transcribed first, then handled the same
  way as a typed message.

The orchestrator replies in the same Telegram chat with the sub-agent's output or, on
a failure inside a sub-agent, a fixed apology string from that sub-agent's Try Again
branch.

## Challenges

- **Sub-workflow calls are a black box to the orchestrator.** The `toolWorkflow` nodes
  pass no schema (`workflowInputs.schema` is empty in every case), so the orchestrator
  can only send a single freeform `query` string per call and receive the sub-agent's
  final `output` back. If a sub-agent needs more structured input (say, a strict event
  ID plus a strict new time), it has to parse that back out of natural language, which
  is exactly the kind of thing that silently degrades as prompts drift over time. There
  is no schema validation catching a malformed handoff.
- **Get-then-act ordering is enforced only by prompt text, not by the graph.** Rules
  like "you must use Get Events first to get the event ID before deleting" or "you
  must use Get Emails first to get the message ID before replying" live entirely in
  the system message strings, not in node wiring or conditional logic. Nothing in the
  workflow itself prevents the LLM from skipping straight to Delete Event with a
  guessed or hallucinated ID.
- **Contact resolution is a manual convention, not a hard dependency.** The
  orchestrator's system prompt tells it to call the contact agent before emailing or
  inviting someone, and shows a worked example, but this is advisory. If the model
  decides it "already knows" an email address from conversation memory or invents one,
  nothing stops it from calling the email agent directly with a wrong address.
- **Every sub-agent's failure path collapses to one generic string.** `Try Again` /
  "Unable to perform task. Please try again." nodes catch anything from an invalid
  Google Calendar OAuth token to a malformed Airtable filter to a Gmail rate limit, and
  return the identical message. There is no node-level distinction surfaced to the
  user (or a log) about which tool or credential actually failed.
- **Voice transcription has no error handling.** `Download File` into `Transcribe` has
  a single main connection straight to the `Ultimate Assistant` agent, no branch for a
  failed download (revoked file, expired Telegram file URL) or an empty/silent
  transcription result. A bad voice note likely surfaces as a confusing agent response
  rather than a clear error to the user.
- **The content creator agent runs on a different model provider than every other
  agent** (Anthropic Claude versus GPT-4o everywhere else), with no explanation in the
  workflow itself for why. That's a real inconsistency to flag in any handoff: it
  means two separate provider credentials and quota limits are load-bearing for one
  system, and a Claude-specific formatting quirk (or an Anthropic outage) affects only
  blog generation, not the rest of the assistant.

## What I learned

- n8n's "Call n8n Workflow Tool" (`toolWorkflow`) pattern is a clean way to give an
  agent a small number of well-named callable capabilities instead of one flat list of
  tools, and it maps naturally onto a LangChain-style tool-calling agent: the workflow
  ID plus name/description is exactly what an LLM tool schema needs.
  `executeWorkflowTrigger` with `inputSource: passthrough` is what makes a sub-workflow
  callable this way instead of only runnable from its own trigger.
  `onError: continueErrorOutput` on an agent node is what turns "the sub-workflow just
  fails" into "the sub-workflow returns a controlled error message," which is the
  difference between a broken chat and a slightly unhelpful chat.
- `$fromAI(...)` parameters on tool nodes (event start/end, attendee email, message ID,
  label ID, and so on) are how n8n lets the LLM fill in a tool node's fields at run
  time rather than the workflow author hardcoding them, which is what makes one
  Google Calendar tool node handle arbitrary user-specified events instead of one fixed
  event.
- Routing quality in a system like this rests entirely on the orchestrator's system
  prompt (tool names, descriptions, and the worked example), since there is no other
  mechanism (no keyword rules, no classifier node) deciding which tool gets called.

## What I'd do differently

- Give each `toolWorkflow` node an explicit input schema (at minimum: intent, and any
  IDs already known) instead of a single freeform `query` string, so sub-agents get
  structured data instead of having to re-parse natural language passed to them by
  another LLM.
- Move the "get the ID before you act" rules out of prompt text and into the graph:
  for example, an IF node after Get Events/Get Emails that only allows Delete/Update
  Event or Email Reply to run if a matching ID was actually found, rather than trusting
  the model not to guess one.
- Differentiate the failure responses per sub-agent (or at least log which tool/node
  failed) instead of collapsing every error into one identical apology string, so a
  credential expiry is distinguishable from a bad user request.
- Add an explicit branch (or at least a fallback message) for a failed voice download
  or empty transcription, instead of letting a bad `Transcribe` result flow straight
  into the orchestrator as if it were valid text.
- Either bring the content creator agent onto the same model provider as the rest of
  the system, or document plainly in-workflow why it deliberately uses a different one
  (a good style/quality reason, a specific Anthropic feature it depends on), so the
  inconsistency reads as a decision instead of an oversight.
- Not verified here: no Telegram bot, OpenAI, Anthropic, Google Calendar, Gmail,
  Airtable, or Tavily credentials were exercised. This system was reviewed by reading
  the exported node graphs only; the routing behavior described above (which agent
  handles which phrasing) reflects what the system prompts instruct, not an observed
  live run.
