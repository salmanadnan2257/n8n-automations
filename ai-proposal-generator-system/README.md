# AI Proposal Generator System

## What it is

An n8n workflow that turns a sales-call intake form into a finished, sendable business
proposal. A form submission (company name, problem, solution, scope, cost, timeline)
goes into GPT-4o, which writes the proposal copy as structured JSON, and that copy gets
dropped into a document and emailed to the prospect automatically.

The exported file actually contains two parallel builds of this idea, wired side by
side and labeled with sticky notes:

- A "free" path: copies a Google Slides template, fills in the AI-written copy with
  Slides' text-replace feature, and emails the client a link to the deck.
- A "paid" path: sends the AI-written copy to PandaDoc, which creates a document from a
  PandaDoc template (including a pricing table), and emails the client a note about it.

## Why it exists

Inferred from the node graph: a way to stop manually writing a custom proposal after
every sales call. The form doubles as a call log (first name, last name, company,
website, problem, solution, scope, cost, timeline) and the same data feeds both proposal
paths, so whoever ran the call fills in one form and gets a proposal document without
opening a doc editor. Nothing in the workflow's own metadata states this goal directly;
it is a plausible read of what the nodes do, not a documented one.

## Features

- Single form intake with fields for the client's problem, proposed solution, scope,
  cost, and desired timeline.
- GPT-4o turns that intake into full proposal copy: title, problem summary, three
  solution sections, three scope items, and a four-part milestone timeline (Slides
  path), or an equivalent problem/solution/scope/timeline structure for PandaDoc.
- Google Slides path: copies a template presentation per submission and fills in
  every text placeholder with the generated copy.
- PandaDoc path: creates a document from a PandaDoc template with the generated copy
  mapped into named tokens, plus a pricing table built from the submitted cost.
- Both paths finish by emailing the client a link to their document.

## Architecture

Two independent flows share the same form fields but are not the same trigger. Node by
node:

**Google Slides flow** (sticky note: "Google Slides AI Proposal Generator"):

1. **On form submission** (`n8n-nodes-base.formTrigger`): "Sales Call Logging Form"
   with First Name, Last Name, Company Name, Email, Website, Problem, Solution, Scope,
   Cost, and How Soon fields.
2. **OpenAI** (`@n8n/n8n-nodes-langchain.openAi`, GPT-4o, JSON output mode): a
   system prompt plus one hardcoded few-shot example (a fictional company,
   "1SecondCopy") teaches the model the output schema, then a real user message built
   from `$('On form submission')` fields asks it to generate the actual proposal
   fields (title, problem summary, three solution headings/descriptions, three scope
   items, four milestone dates/descriptions).
3. **Google Drive** (`n8n-nodes-base.googleDrive`, operation `copy`): copies a fixed
   template file (Slides presentation) and names the copy after the generated
   `proposalTitle`.
4. **Replace Text** (`n8n-nodes-base.googleSlides`, operation `replaceText`): swaps
   every `{{placeholder}}` token in the copied deck for the matching AI-generated
   field. One replacement is not dynamic: `{{cost}}` is always replaced with the
   literal string `$1,850`, regardless of what the form's Cost field actually holds.
5. **Gmail**: sends a fixed-text email ("Hey Nick, ... You'll find it here: [deck
   link] ... Thanks, Nick") to the submitted Email address, with a hardcoded subject
   line ("Re: Proposal for LeftClick") that does not reference the actual client or
   company name.

**Important gap found in this branch:** in the exported workflow's `connections`
object, the "On form submission" trigger node has zero outgoing connections. It is not
wired to the OpenAI node at all. As exported, this entire flow (OpenAI, Google Drive,
Replace Text, Gmail) has no trigger feeding it and would never run. This is stated
plainly rather than guessed around; reconnecting the trigger's output to the OpenAI
node is a one-drag fix in the n8n editor, but the file as saved does not have it.

**PandaDoc flow** (sticky note: "PandaDoc AI Proposal Generator"), fully wired
trigger-to-finish:

1. **On form submission1**: an identical copy of the same form, feeding this flow
   instead.
2. **OpenAI1**: the same few-shot pattern as above, generating a differently shaped
   JSON schema tailored to the PandaDoc template's fields (`problemTitle`,
   `solutionTitle`, `solutionText`, five scope items, four timeline entries).
3. **HTTP Request**: a raw POST to `api.pandadoc.com/public/v1/documents/`, building a
   document from a PandaDoc template UUID, mapping the AI output and form fields into
   named tokens (`Client.Email`, `Client.Company`, `Client.ProblemText`, and so on),
   plus a pricing table populated by parsing the form's Cost field
   (`.replace("$","").replace(",","").toNumber()`) into a number. The sender identity
   (`Sender.Email`, `Sender.Company`, `Sender.FirstName`, `Sender.LastName`) is
   hardcoded into the request body rather than read from a variable or credential.
4. **Gmail1**: the same fixed-text email pattern as the Slides flow's Gmail node, sent
   to `On form submission1`'s Email field.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create and attach credentials for:
   - **Google Slides OAuth2** (Replace Text node).
   - **Google Drive OAuth2** (Google Drive node, to copy the template file).
   - **OpenAI API** (both OpenAI nodes).
   - **Gmail OAuth2** (both Gmail nodes).
   - **PandaDoc API key**: the HTTP Request node authenticates with a plain
     `Authorization: API-Key ...` header rather than an n8n credential, so the key has
     to be pasted into that header field directly (or reworked into n8n's HTTP Header
     Auth credential type).
3. Point the Google Drive "copy" node at your own Slides template file ID, and the
   PandaDoc HTTP Request node at your own `template_uuid`. The ones in the export are
   specific to the original builder's account.
4. Fix the "On form submission" -> "OpenAI" connection in the Slides flow (see
   Architecture above); it is missing in the exported file.
5. Replace the hardcoded sender identity and email copy (subject line, greeting,
   sign-off) with real values or expressions before using this for an actual client.

See `CREDENTIALS.md` for the full list of what each node needs.

## Usage

Fill out the "Sales Call Logging Form" after a sales call. Once the Slides flow's
trigger connection is restored, that submission also produces a copied Slides deck with
AI-written proposal copy and emails the client a link to it. A separate identical form
(the PandaDoc flow's own trigger) produces a PandaDoc document with the same kind of
AI-written copy, a pricing table, and its own client email.

## Challenges

- **A disconnected trigger.** As covered above, the Google Slides flow's form trigger
  has no outgoing connection in the saved file. This is the kind of thing that is easy
  to miss in the n8n editor if the canvas is not scrolled to check every node's wires,
  and it means the "free" path silently does nothing until reconnected.
- **A hardcoded cost value.** The Slides flow always writes `$1,850` into the deck's
  cost field, no matter what the form's Cost field contains. Anyone using this flow
  as-is would send every client the same price regardless of what was actually quoted
  on the call.
- **Client-agnostic email copy.** Both Gmail nodes use a fixed subject line and message
  body written for one specific client interaction ("Re: Proposal for LeftClick", "Hey
  Nick"). Nothing in either email is built from the form's Company Name or First Name
  fields, so every proposal email reads the same regardless of who it is actually going
  to.
- **No output validation on the LLM's JSON.** Both OpenAI nodes are told to return
  every field and to never leave one empty, but nothing downstream checks that the
  actual response matches that schema. A malformed or partial JSON response would
  either break the Replace Text / HTTP Request nodes outright or silently insert blank
  text into the client-facing document.
- **Fragile cost parsing on the PandaDoc side.** The pricing table value is derived by
  stripping `$` and `,` characters from the form's Cost field and converting it to a
  number. A cost entered without a dollar sign, with a different currency symbol, or as
  a range ("2000-2500") would either produce a wrong price or fail the expression
  outright; there is no format validation on the form field itself.
- **Reused, mislabeled credentials.** The OpenAI and Google Slides credential objects
  in the export are named "YouTube" and "YouTube " (with a trailing space), clearly
  recycled from an unrelated project rather than provisioned for this one. Anyone
  importing this workflow needs to create fresh, correctly named credentials rather
  than assume the labels describe what they connect to.

## What I learned

- n8n's few-shot prompting pattern: a system message plus a fabricated example
  user/assistant exchange inside the same OpenAI node's message list, followed by the
  real templated user message, is a workable way to pin down a large structured JSON
  output schema without a separate schema-validation node.
- Google Slides' `replaceText` operation is a simple, effective way to template a
  presentation from a single source deck, as long as every placeholder actually gets a
  matching replacement wired in (the hardcoded `$1,850` case shows what happens when
  one does not).
- Google Drive's `copy` operation lets a workflow duplicate a template file per
  execution, so the original template is never touched by the automation.
- It is possible for a workflow to look fully built in the canvas view while one
  branch's trigger is quietly disconnected; the only way to catch that reliably is
  reading the exported JSON's `connections` object directly.

## What I'd do differently

- Reconnect "On form submission" to "OpenAI" so the Slides flow actually runs, and
  test both flows end to end before considering this "generator system" complete.
- Replace the hardcoded `$1,850` cost value and the fixed "LeftClick"/"Nick" email
  copy with expressions pulled from the form submission, so the output is actually
  client-specific.
- Add a validation step (an IF node checking for required keys, or a Code node
  validating the parsed JSON) between each OpenAI node and what consumes its output,
  so a malformed model response fails loudly instead of producing a broken document.
- Move the PandaDoc API key into n8n's credential store instead of a manually typed
  header value, and rename every credential to describe what it actually connects to.
- Add basic input validation on the Cost field (a number field type, or a regex check)
  so the PandaDoc pricing table parse cannot silently produce a wrong number.
