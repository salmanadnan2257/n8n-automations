# Cold Email Outreach Sequence System

## What it is

A set of 9 chained n8n workflows that turn a raw lead (name, company, LinkedIn URL)
into a full six-touch cold email sequence, ready to hand to Instantly.ai for sending.
One workflow researches the lead and company, five workflows write the first email
and five follow-ups, one writes the subject line, one cleans and pushes the finished
copy into an Instantly.ai campaign, and one orchestrator (`NEW - Generate All Emails`)
loops over a list of leads and calls the others in the right order.

## Why it exists

This was built for real cold outreach at Digitalise Agency: writing a first email plus
five follow-ups by hand for every lead does not scale past a handful of prospects a
week. The system exists to take a spreadsheet of leads, enrich each one with a quick
web/LinkedIn research pass, generate a full personalized sequence with an LLM, and load
it straight into the sending platform, so a human only has to review and approve
copy instead of drafting it.

## Features

- Automatic lead and company research (general web search, news search, LinkedIn
  profile scrape, LinkedIn company scrape) before any copy is written.
- Six pieces of copy generated per lead: subject line, first email, and five
  follow-ups, each pulling in the research data so the copy references real facts
  about the person or company.
- Five parallel LLM generation attempts per email with a fallback gate, so one bad
  or empty generation does not kill the whole run.
- Output cleaning step that strips markdown artifacts and converts line breaks to
  HTML before the copy reaches Instantly.ai.
- Segment-based routing: leads are routed to one of five different Instantly.ai
  campaigns depending on a `type` field, each with its own campaign ID.
- A single orchestrator workflow that loops over a batch of leads and drives all
  the sub-workflows per lead without manual triggering of each one.

## Architecture

The system is 9 separate n8n workflow files plus a 10th standalone research
workflow. Node types used throughout: `n8n-nodes-base.executeWorkflow` and
`n8n-nodes-base.executeWorkflowTrigger` (the workflow-to-workflow call and its
entry point), `@n8n/n8n-nodes-langchain.agent` paired with
`@n8n/n8n-nodes-langchain.lmChatGoogleGemini` (the LLM calls), `n8n-nodes-base.code`
(output cleaning and JSON escaping), `n8n-nodes-base.switch` and `n8n-nodes-base.if`
(routing and fallback gates), `n8n-nodes-base.httpRequest` (the Tavily research
calls and the Instantly.ai API calls), `n8n-nodes-base.googleSheets` (the lead
database), `n8n-nodes-base.merge`, `n8n-nodes-base.splitInBatches`, and
`n8n-nodes-base.manualTrigger` (the two workflows a human starts by hand).

**Orchestrator: `NEW - Generate All Emails`.** Started manually. It loops over a
batch of leads (`Initialize Loop Vars` → `Increment Loop Var` → a filter/`If - Done`
loop) and, for each lead, calls eight sub-workflows through `executeWorkflow` nodes:
First Email, First Follow Up, Second Follow Up, Third Follow Up, Fourth Follow Up,
Fifth Follow Up, Generate Subject Line, and Add Leads to Instantly. Their outputs
merge back together (`Merge` → `Edit Fields`) before the loop advances to the next
lead. The file also still contains nine earlier, disconnected copies of these same
`executeWorkflow` nodes left over from an earlier version of the workflow; they have
no incoming or outgoing connections and are not part of the live call path.

**Research: `Online_Research.json`.** Standalone, started manually, not called by
`executeWorkflow` from any other file in this set. Given a lead's name, company
name, title, LinkedIn URL, and company LinkedIn URL, it fires four lookups against
Tavily's API: `api.tavily.com/search` for a general web search and a news search,
and `api.tavily.com/extract` for a LinkedIn profile scrape and a LinkedIn company
scrape. Each branch has its own if/loop/no-op path, gets cleaned, and is merged into
a single record with four fields: `general_search`, `news_search`,
`person_linkedin_scrape`, `company_linkedin_scrape`. Those exact field names are
read back later inside the LLM prompts of every email-writing workflow, which means
this research pass is expected to run first and its output written back into the
same lead record (almost certainly the Google Sheet) before Generate All Emails
runs. That handoff is inferred from the shared field names, not from a direct node
link between the two workflows, since none exists in the JSON.

**Email and subject line workflows: `NEW___First_Email.json`,
`NEW___First_Follow_Up.json` through `NEW___Fifth_Follow_Up.json`, and
`NEW___Generate_Subject_Line.json`.** Each one is entered through an
`executeWorkflowTrigger` node ("When Executed by Another Workflow"). Internally each
runs five parallel LLM generation attempts (`generate_*_v1` through `_v5`), each
pairing an `agent` node with its own `lmChatGoogleGemini` chat model node (models
seen: `gemini-2.0-flash-001`, `gemini-2.0-flash-lite-001`,
`gemini-2.5-flash-lite-preview-06-17`, `gemini-2.5-flash-preview-05-20`), then a
switch/if gate picks a usable result from the five attempts. A `code` node
(`clean_first_email`, `clean_first_follow_up`, and so on) then strips markdown bold
and italic markers, converts newlines to `<br>` tags, and escapes double quotes, so
the result is safe to drop straight into an HTML email body.

**Delivery: `NEW___Add_Leads_to_Instantly.json`.** Entered through an
`executeWorkflowTrigger`. A `code` node (`clean_data`) JSON-escapes the six pieces
of generated copy (subject line, first email, five follow-ups), then a `switch`
node reads the lead's `type` field and routes it to one of five nearly identical
`httpRequest` nodes, each posting to `https://api.instantly.ai/api/v2/leads` with
its own campaign ID and the lead's data plus all the generated copy in
`custom_variables`. Each of the five nodes has `retryOnFail` and
`onError: continueErrorOutput` set, so a failed API call for one lead does not stop
the run for the rest of the batch; there is no explicit rate-limit delay or batching
node.

Overall data flow: lead enters the sheet → `Online_Research.json` run manually to
enrich it with web/news/LinkedIn data → `NEW - Generate All Emails` run manually,
looping per lead → calls the five follow-up workflows, the first email workflow,
and the subject line workflow in parallel per lead, each doing its own five-attempt
LLM generation and cleanup → merged results passed to `Add Leads to Instantly` →
lead and copy pushed into the matching Instantly.ai campaign.

## Setup

Import each of the 9 files into n8n separately: Workflows menu > Import from File,
one file at a time, for all of `NEW___Add_Leads_to_Instantly.json`,
`NEW___Fifth_Follow_Up.json`, `NEW___First_Email.json`,
`NEW___First_Follow_Up.json`, `NEW___Fourth_Follow_Up.json`,
`NEW___Generate_All_Emails.json`, `NEW___Generate_Subject_Line.json`,
`NEW___Second_Follow_Up.json`, and `NEW___Third_Follow_Up.json`. Import
`Online_Research.json` as well if you want the research step.

After import, the `executeWorkflow` nodes inside `NEW - Generate All Emails` point
to workflow IDs from the original n8n instance; re-point each one at the matching
freshly imported workflow (n8n usually offers to remap these automatically if the
`cachedResultName` matches).

You will need your own credentials set up in n8n for:

- A Google Gemini / Google PaLM API credential, used by every `lmChatGoogleGemini`
  node across the six copywriting workflows.
- A Tavily API credential (or equivalent auth on the `httpRequest` nodes), used by
  `Online_Research.json` for search and LinkedIn extraction.
- An Instantly.ai API key, set as the `Authorization` header value on the five
  `httpRequest` nodes in `NEW___Add_Leads_to_Instantly.json` (currently placeholder
  text `YOUR_INSTANTLY_API_KEY_HERE` in this copy).
- A Google Sheets credential if you keep your lead list in Sheets, matching the
  `googleSheets` nodes referenced by the follow-up workflows.

None of this was re-run end to end after scrubbing; only the JSON structure and node
wiring were verified, not a live execution against real Gemini, Tavily, and
Instantly.ai accounts.

## Usage

1. Add leads to your lead sheet with at minimum name, company name, title, LinkedIn
   URL, and company LinkedIn URL.
2. Run `Online_Research.json` manually to enrich each lead with search, news, and
   LinkedIn data, and write the results back to the same lead record.
3. Run `NEW - Generate All Emails` manually. It loops over the batch, generates a
   subject line, first email, and five follow-ups per lead, cleans the output, and
   pushes the finished sequence into the correct Instantly.ai campaign based on the
   lead's `type` field.
4. Check the Instantly.ai campaign to confirm leads landed with the expected copy
   before turning sending on.

## Challenges

- **Keeping 9 workflows in sync.** Every one of the six copywriting workflows
  duplicates the same five-attempt generation pattern and its own clean-up code
  node. A prompt tweak or a bug fix in the cleaning regex has to be copied into six
  separate files by hand; there is no shared sub-workflow for the common logic. The
  leftover set of nine disconnected, orphaned `executeWorkflow` nodes still sitting
  in `NEW - Generate All Emails` from an earlier version is a direct symptom of this
  problem: old wiring was never cleaned up when the workflow was restructured.
- **Error handling across chained sub-workflow calls.** The Instantly delivery step
  handles per-lead failures reasonably well (`retryOnFail` plus
  `continueErrorOutput` on all five posting nodes, so one bad API call does not
  halt the batch). The email-generation workflows are weaker: if all five LLM
  attempts in a workflow come back empty, the switch/if gate has to pick something,
  and there is no visible dead-letter path or alerting for a lead whose copy failed
  outright; it is only caught by manually inspecting the merged output.
- **LLM output cleaning and formatting reliability.** LLMs return markdown
  (bold/italic asterisks) and literal newlines that break an HTML email body. Each
  workflow has its own `code` node doing regex-based stripping of `**`, `*`, and
  `\n` to `<br>` and quote escaping. This works but is duplicated six times with no
  shared test, so a formatting edge case (nested markdown, a stray quote inside
  generated copy) has to be caught and fixed in every copy of the regex separately.
- **Running five LLM attempts per email.** Generating five parallel attempts per
  email (v1 through v5) across six workflows means up to 30 Gemini calls per lead
  before a single sequence is finalized. This is a real cost and rate-limit
  consideration; the workflow does not appear to have any explicit rate-limit
  backoff or queuing, it relies on running the attempts in parallel and picking
  whichever succeeds.
- **Deduplication of leads.** Nothing in these 10 files checks whether a lead has
  already been researched, emailed, or pushed to Instantly before running again.
  Running `Generate All Emails` twice over the same batch would generate a fresh
  sequence and push a duplicate lead entry to Instantly; dedup has to be handled
  upstream, in how the lead sheet itself is maintained.
- **Instantly.ai API quirks.** Leads are split across five separate campaigns using
  a `type` field and five near-identical HTTP Request nodes with hardcoded campaign
  IDs, rather than one node with a dynamic campaign parameter. Adding a sixth
  segment means adding a sixth near-identical node and a new switch branch, not
  changing a single value.

## What I learned

- `executeWorkflow` combined with `executeWorkflowTrigger` is a workable pattern
  for splitting a large automation into named, independently testable pieces, but
  n8n gives no built-in guardrail against leaving dead, disconnected nodes behind
  when you restructure the call graph, they just sit there silently.
- Running several LLM generation attempts in parallel and gating on the first
  usable one is a cheap way to raise reliability against occasional empty or
  malformed model output, at the direct cost of multiplying API calls per unit of
  final output.
- Cleaning LLM output for HTML delivery is a small amount of logic (strip markdown,
  convert newlines, escape quotes) but it is exactly the kind of logic that quietly
  drifts out of sync when copied across many workflow files instead of centralized.

## What I'd do differently

- Centralize the shared logic, the five-attempt generation pattern and the output
  cleaning regex, into one sub-workflow that every email-type workflow calls with
  its own prompt as a parameter, instead of duplicating both across six files.
- Remove the nine orphaned, disconnected `executeWorkflow` nodes from
  `NEW - Generate All Emails` rather than leaving them in the exported JSON; they
  add confusion for anyone reading the workflow later.
- Replace the five hardcoded, near-identical Instantly.ai HTTP Request nodes with
  one node whose campaign ID is looked up dynamically from the lead's `type` field,
  so adding a new segment does not mean copying a node.
- Add an explicit dedup check (has this lead already been pushed to Instantly)
  before the delivery step, instead of relying entirely on upstream sheet hygiene.
- Add a visible failure path for leads where all five LLM attempts come back empty,
  instead of only being able to catch that by manually inspecting the final merge.
