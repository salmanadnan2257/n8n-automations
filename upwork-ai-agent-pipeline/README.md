# Upwork AI Agent Pipeline

## What it is

An n8n chat agent that takes an Upwork job description as input and produces three
application assets from it: a written proposal (application copy), a Google Doc
proposal built from a template, and a Mermaid.js flowchart of the proposed automation
system. The agent is the orchestrator; the three asset generators are separate n8n
workflows that it calls as tools.

## Why it exists

Writing a strong Upwork proposal by hand, every time, for freelance automation work is
slow: you have to restate who you are, tailor the pitch to the specific job, and
often produce a visual (a flowchart) and a formatted document to stand out. This
workflow automates that repeat work: paste a job description into the chat, and the
agent calls out to the three sub-workflows and returns application copy, a shareable
Google Doc, and a diagram, in one pass.

## Features

- Single chat interface (n8n's chat trigger) as the only human-facing entry point.
- Three independent, reusable sub-workflows exposed to the agent as callable tools,
  each doing one job: application copy, Google Doc proposal, Mermaid diagram.
- Conversation memory (last 10 turns) so the agent can handle follow-up requests in
  the same chat without re-sending the job description.
- A Google Docs template-merge step that copies a master proposal template per job and
  fills in AI-generated content, rather than generating a document from scratch.

## Architecture

### Top-level orchestrator (`top-level-orchestrator.json`)

- **When chat message received** (`@n8n/n8n-nodes-langchain.chatTrigger`): entry point,
  receives the user's message (expected to be an Upwork job description).
- **AI Agent** (`@n8n/n8n-nodes-langchain.agent`): the controller. Its system prompt
  instructs it that on receiving a job description it *must* call all three tools
  below, then replace the literal placeholder string `$$$` (present inside the
  application copy) with the real Google Doc link before replying to the user.
- **OpenAI Chat Model** (`@n8n/n8n-nodes-langchain.lmChatOpenAi`): the language model
  behind the agent.
- **Window Buffer Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`, window of
  10): gives the agent short-term conversation memory.
- **Generate Application Copy**, **Generate Google Doc Proposal**, **Generate
  Mermaid.js** (`@n8n/n8n-nodes-langchain.toolWorkflow`, one per sub-workflow): each
  node points at one of the three sub-workflows below via `workflowId` (an n8n
  workflow ID plus a cached display name) and exposes it to the agent as a named,
  described tool (`generate_upwork_application_copy`,
  `generate_google_doc_proposal`, `generate_mermaid_diagram`). The agent decides at
  runtime, from its system prompt, to call all three and in what order; nothing in
  the node graph enforces call order or that all three actually ran.
- Two of the three tool nodes set a `responsePropertyName` (`urlOfProposal` for the
  Google Doc tool, `mermaidCode` for the Mermaid tool) telling n8n which field of the
  sub-workflow's output to hand back to the agent as the tool result. The application
  copy tool node does not set this, even though its sub-workflow's final node outputs
  a differently-named field (`response`, not `applicationCopy`). This inconsistency is
  visible directly in the JSON and is called out again under Challenges.

### Sub-workflow 1: Generate Application Copy (`sub-workflow-1-generate-application-copy.json`)

Triggered by `n8n-nodes-base.executeWorkflowTrigger` (i.e. only callable as a
sub-workflow, not standalone). **Set Variable** (`n8n-nodes-base.set`) injects a
hardcoded freelancer bio string (`aboutMe`) into the item. **OpenAI**
(`@n8n/n8n-nodes-langchain.openAi`, `gpt-4o-mini`, JSON output mode) receives the job
description plus the bio and a proposal template in its prompt, and returns
`{"proposal": "..."}`, deliberately leaving the `$$$` placeholder untouched for the
orchestrator to fill in later. **Edit Fields** (`n8n-nodes-base.set`) extracts
`message.content.proposal` into a field named `response`.

### Sub-workflow 2: Generate Google Doc Proposal (`sub-workflow-2-generate-google-doc-proposal.json`)

Also an `executeWorkflowTrigger`. **Set Variable** injects the same hardcoded
`aboutMe` bio (duplicated from sub-workflow 1, not shared). **OpenAI**
(`gpt-4o-mini`, JSON output) turns the job description into structured proposal
fields (title, brief explanation, step-by-step bullets, a left-to-right flow
summary, and about-me bullets). **Google Drive** (`n8n-nodes-base.googleDrive`,
`copy` operation) duplicates a fixed template document (referenced by its own
Google Doc file ID) and names the copy after the generated title. **Google Drive1**
(same node type, `share` operation) sets the new copy's sharing permission to
"anyone with the link, reader." **Google Docs** (`n8n-nodes-base.googleDocs`,
`update` operation) runs a series of `replaceAll` text substitutions against
literal placeholder tokens in the template (`{{titleOfSystem}}`,
`{{briefExplanationOfSystem}}`, etc.), replacing each with the matching
AI-generated field. **Edit Fields** builds the final shareable URL from the new
document's ID into `urlOfProposal`, the field name the orchestrator's tool node
expects back.

### Sub-workflow 3: Generate Mermaid Code (`sub-workflow-3-generate-mermaid-code.json`)

The simplest of the three: `executeWorkflowTrigger` -> **OpenAI** (`gpt-4o-mini`,
plain text, not JSON mode) generates raw Mermaid flowchart syntax from the job
description, instructed to output nothing but the diagram code -> **Edit Fields**
wraps the raw text into a `mermaidCode` field.

## Setup

1. In n8n, go to **Workflows > Import from File** and import the three sub-workflow
   files first: `sub-workflow-1-generate-application-copy.json`,
   `sub-workflow-2-generate-google-doc-proposal.json`,
   `sub-workflow-3-generate-mermaid-code.json`.
2. Import `top-level-orchestrator.json` last.
3. The orchestrator's three `toolWorkflow` nodes (Generate Application Copy, Generate
   Google Doc Proposal, Generate Mermaid.js) still point at the original workflow IDs
   from the source n8n instance. Open each one and re-select the matching sub-workflow
   you just imported from the `workflowId` picker, or the tool calls will fail.
4. Attach credentials (see below) to the OpenAI, Google Drive, and Google Docs nodes.
5. In sub-workflow 2's **Google Drive** node, replace the template `fileId` with a
   Google Doc you control that contains the literal placeholder tokens
   `{{titleOfSystem}}`, `{{briefExplanationOfSystem}}`, `{{specificPartOfTheirRequest}}`,
   `{{stepByStepBulletPoints}}`, `{{leftToRightFlowWithArrows}}`, and
   `{{aboutMeBulletPoints}}` somewhere in its body; the original template document is
   not included in this repository since it lives in Google Drive, not as a JSON file.
6. Accounts/credentials needed: **OpenAI API**, **Google Drive API**, **Google Docs
   API**.

## Usage

Open the orchestrator's chat panel in n8n (or its published chat webhook) and paste in
an Upwork job description. The agent should call all three tools and return a reply
containing the application copy (with the Google Doc link substituted in place of
`$$$`), a Mermaid diagram block, and the proposal document link.

## Challenges

- **Tool output field mismatch.** The Application Copy tool node has no
  `responsePropertyName` set, while its sub-workflow's last node outputs a field
  called `response` (not `applicationCopy`). The other two tools explicitly name the
  field they expect back. This is an inconsistency visible directly in the JSON, and
  it means the agent may receive the whole JSON object rather than a clean string for
  that one tool, forcing the LLM to parse it out of context rather than the node graph
  guaranteeing a clean value.
- **The `$$$` link substitution is done by the LLM, not a node.** Nothing enforces
  that the agent actually performs this text replacement correctly (or at all); it is
  entirely dependent on the system prompt being followed. A dedicated Set or Code node
  doing a literal string replace after all three tool calls finish would be more
  reliable than asking the model to do it in prose.
- **No enforced call order or completion check.** The three sub-workflows are exposed
  as independent tools; the system prompt says the agent "must" call all three, but
  nothing in the node graph verifies that it did. If the model skips a tool call (for
  example under token pressure or a malformed response), the chat reply can come back
  missing an asset with no error surfaced.
- **Duplicated personalization data.** The `aboutMe` bio string is hardcoded
  identically into two separate Set nodes (sub-workflows 1 and 2). Any update to the
  bio has to be made in both files by hand; there is no shared source.
- **Template-token fragility.** Sub-workflow 2's Google Docs merge depends on literal
  tokens like `{{titleOfSystem}}` existing verbatim in the copied template. Google
  Docs' `replaceAll` does not error when a token is missing, it silently matches zero
  times, so a renamed or mistyped placeholder in the template document produces a
  merged doc with unfilled tokens and no failure anywhere in the run.
- **No error handling on any external call.** None of the OpenAI, Google Drive, or
  Google Docs nodes across the three sub-workflows have retry or `onError` settings
  configured. A single transient API failure fails that sub-workflow's execution
  entirely, which fails the agent's tool call for that turn.

## What I learned

- n8n's `toolWorkflow` node type is what lets an AI Agent call an entire separate
  workflow as a single tool: it just needs a `workflowId`, a name, and a natural
  language description the LLM reads to decide when to invoke it. This is a genuinely
  clean pattern for splitting an agent's abilities into independently testable
  sub-workflows.
- `responsePropertyName` on a `toolWorkflow` node is what controls whether the agent
  sees a clean scalar value or the sub-workflow's full JSON output; leaving it unset
  (as happened here for one of the three tools) is easy to miss and produces
  inconsistent tool results across an otherwise-symmetric set of three tools.
- Google Docs' `replaceAll` action operates on literal text matches inside the
  document body, so the entire merge step lives or dies on the template document
  containing exactly the placeholder strings the workflow expects, with no schema or
  validation tying the two together.

## What I'd do differently

- Replace the LLM-driven `$$$` substitution with a Code or Set node that runs after
  all three tools return, so the final link swap is deterministic instead of resting
  on prompt compliance.
- Add a `responsePropertyName` to the Application Copy tool node (and rename its
  sub-workflow's output field to something more descriptive than `response`) so all
  three tools behave consistently.
- Pull the duplicated `aboutMe` bio out into one place, for example a small shared
  "get profile" sub-workflow the other two call, instead of maintaining the same
  string in two files.
- Add `onError` handling (at minimum `continueErrorOutput` with a visible failure
  message back to the chat) on the OpenAI and Google nodes so a single failed API call
  degrades gracefully instead of silently failing the whole turn.
