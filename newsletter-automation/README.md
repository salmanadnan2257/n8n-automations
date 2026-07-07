# Newsletter Automation

## What it is

An n8n workflow that turns a short form submission (topic, tone, target audience) into
a researched, formatted newsletter and sends it by email. A form trigger feeds three
chained AI agents: one plans a table of contents, one researches and drafts each
section using live web search, and one edits everything into a single HTML newsletter
with a generated title, which then goes out through Gmail.

## Why it exists

Writing a newsletter by hand means picking a topic, researching current information,
drafting several sections, and editing them into one coherent piece, every time you
want to publish. This workflow automates that pipeline end to end: a form fills in the
brief, three specialized AI roles do the planning, research, and writing, and the
result lands in an inbox ready to review or send. It is a template built for reuse
across different topics, tones, and audiences without touching the workflow itself.

## Features

- Web form intake for topic, tone (dropdown: Professional or Funny), and target
  audience, no manual JSON editing needed to run it.
- A planning agent ("Newsletter Expert") that researches the topic live and proposes
  a 4 to 6 item table of contents tailored to the audience.
- Per-section parallel drafting: each table-of-contents item is split out and handed
  to a research agent that writes original content with inline hyperlinked citations.
- A dedicated editor pass that merges every section into one HTML document, enforces
  a single alphabetized sources list, and caps output at 1000 words.
- Automatic subject-line generation based on the finished newsletter content.
- Delivery via Gmail with a fixed sender name ("Daily Newsletter").
- A reusable sub-workflow ("tavily") that wraps the Tavily search API so both AI
  agents can call it as a tool.

## Architecture

The workflow is a single n8n graph plus one called sub-workflow.

1. **On form submission** (`n8n-nodes-base.formTrigger`): captures Topic, Tone, and
   Target Audience from a hosted form and starts the run.
2. **Newsletter Expert** (`@n8n/n8n-nodes-langchain.agent`), backed by **OpenAI Chat
   Model** (`lmChatOpenAi`, gpt-4o-mini per the model list) and the **tavily** tool:
   takes the form fields and produces a table of contents as its `output` field. It
   is explicitly instructed to search for trending subtopics before writing the list.
3. **Project Planner** (`@n8n/n8n-nodes-langchain.openAi`, a direct chat-completion
   call, not an agent): takes that table of contents and reshapes it into structured
   JSON, an array under `newsletterSections`, each with a title and description.
4. **Split Out** (`n8n-nodes-base.splitOut`): explodes `newsletterSections` into one
   item per section so the rest of the graph runs once per section.
5. **Research Team** (`@n8n/n8n-nodes-langchain.agent`), backed by **Anthropic Chat
   Model** (`lmChatAnthropic`) and the same **tavily** tool: writes the actual prose
   for one section, citing sources as inline HTML hyperlinks, with no framing text.
6. In parallel, **Split Out**'s output also flows straight into **Merge**
   (`n8n-nodes-base.merge`, `combineByPosition`), which lines up each section's title
   (from Split Out) with its drafted content (from Research Team) item by item.
7. **Aggregate** (`n8n-nodes-base.aggregate`): collapses all the per-section items
   back into two flat lists, `title` and `output`, merged into a single item.
8. **Editor** (`@n8n/n8n-nodes-langchain.agent`), also backed by the Anthropic chat
   model: takes the full lists of titles and drafted content and writes one HTML
   newsletter, section by section, with a single deduplicated, alphabetized sources
   list at the end. It is instructed to cap output at 1000 words because a longer
   body was observed to break the automation downstream.
9. **Create TItle** (`@n8n/n8n-nodes-langchain.openAi`, gpt-4o-mini): reads the
   finished newsletter body and generates a plain-text, title-cased subject line.
10. **Send Newsletter** (`n8n-nodes-base.gmail`): sends the Editor's HTML body as the
    message with the generated title as the subject, via a Gmail OAuth2 credential.

**tavily sub-workflow** (called as a tool by both the Newsletter Expert and Research
Team agents): a **Workflow Input Trigger** (`executeWorkflowTrigger`) receives a
`query` string, an **HTTP Request** node (`n8n-nodes-base.httpRequest`) POSTs it to
`https://api.tavily.com/search` with a topic filter of "news" and a 3-result cap, and
a **Set** node (`n8n-nodes-base.set`) formats the top 3 results into a plain-text
block of source URLs and content that gets returned to whichever agent called it.

## Setup

1. In n8n: Workflows menu > Import from File, select `workflow.json` from this
   folder. Repeat for a second workflow if you want the Tavily tool as its own
   importable workflow (it is included as nodes inside this same file here, wired as
   a sub-workflow call by ID, so you will need to recreate or repoint that tool
   workflow reference after import since workflow IDs do not carry over between
   n8n instances).
2. Credentials needed, added in n8n's Credentials section and then attached to the
   relevant nodes:
   - OpenAI API (used by the Newsletter Expert's chat model, the Project Planner,
     and the Create Title node)
   - Anthropic API (used by the Research Team and Editor agents' chat model)
   - Gmail OAuth2 (used by Send Newsletter)
   - A Tavily API key, set directly in the Tavily HTTP Request node's JSON body
     (`YOUR_TAVILY_API_KEY_HERE` in this copy) rather than n8n's credential store,
     since Tavily is called with a raw HTTP request, not a dedicated node.
3. Rebuild or reconnect the `tavily` tool node's `workflowId` reference to point at
   wherever you host the Tavily sub-workflow in your own instance.
4. Publish the form trigger and set the workflow to Active.

## Usage

Open the published form URL, fill in Topic, Tone, and Target Audience, and submit.
The workflow runs the full pipeline and sends the finished newsletter to the Gmail
account attached to the Send Newsletter node. There is no draft or approval step
before sending; the output goes straight to the configured inbox.

## Challenges

- **Keeping per-section research aligned after a split.** Splitting sections into
  parallel items and later recombining them risks mismatched titles and content if
  order isn't preserved. The workflow addresses this with `combineByPosition` in the
  Merge node, which assumes Split Out and Research Team preserve item order; there is
  no node that verifies a title and its content still correspond after the merge.
- **Enforcing a hard word limit on an LLM.** The Editor's system prompt asks for a
  1000-word cap "or else the automation breaks," which is a real constraint (likely
  a downstream email size or agent context limit) but it's enforced entirely through
  prompt instruction, with no code node actually truncating or validating length
  before the email is sent.
- **Citation quality depends entirely on the search tool.** Both research-facing
  agents are told to cite sources as inline hyperlinks, but the tavily tool returns
  only 3 results per query with basic search depth, so thin or repetitive source
  coverage on obscure topics is a real risk the graph doesn't specifically account for.
- **Two different agents write in two different voices.** The Research Team agent
  (Anthropic) drafts sections, and the Editor (also Anthropic, but a different
  system prompt) rewrites them for flow. Because they're separate agent calls, voice
  consistency across sections relies on the Editor's rewrite pass rather than a
  shared style guide passed to both.
- **No dry-run or review step.** Because Create Title flows directly into Send
  Newsletter, there's no human-in-the-loop point to catch a bad draft before it's
  emailed. Testing this workflow safely means either disabling the Gmail node or
  redirecting it to a test inbox first.
- **Sub-workflow references don't survive an environment migration.** The `tavily`
  tool node references a `workflowId` by n8n's internal ID, which is specific to the
  instance it was built on. Importing this file elsewhere requires manually
  repointing that reference, since n8n doesn't remap sub-workflow IDs on import.

## What I learned

Multi-agent content pipelines are easier to reason about when each agent has one
narrow job (plan, research, edit) rather than one agent doing everything, but the
tradeoff is that ordering guarantees (like `combineByPosition` in Merge) become load
bearing: if any upstream node ever reorders items, the whole pipeline silently
attaches the wrong content to the wrong title with no error thrown. Splitting a
generation task into parallel per-section agent calls is also a real way to keep each
individual LLM call focused and within a reasonable context size, rather than asking
one agent to write an entire multi-section article in one pass.

## What I'd do differently

I'd add a code node right after Merge that explicitly checks each item's title
survived pairing with its matching content (for example by asserting array lengths
match before Aggregate runs), instead of trusting position-based combination
silently. I'd also add a human approval step, even a simple Slack or email
notification with an approve/reject action, before Send Newsletter fires, since right
now there is no gate between the Editor's output and a real inbox. Finally I'd move
the Tavily API key out of the raw JSON body and into an n8n credential (n8n supports
generic HTTP header/query auth credentials), so the key isn't sitting in plaintext
inside the node's parameters.
