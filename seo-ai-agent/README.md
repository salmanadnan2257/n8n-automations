# SEO AI Agent

## What it is

An n8n workflow that takes a landing page URL from a web form and runs two parallel AI
audits against it (a content-focused SEO audit and a technical SEO audit), then emails
the combined findings as a formatted report.

## Why it exists

This was built as a lead-generation and audit tool: a visitor submits their landing
page, and a few moments later they get an emailed on-page SEO audit covering both
copy/content issues and technical issues, without a human auditor doing the initial
pass.

A note on provenance: the source file for this workflow was distributed under a
personal brand name in its original title and a form placeholder URL. Per the
condition this entry was approved under, every occurrence of that branding has been
removed from the copied workflow file, its node names, and this documentation. The
node graph, prompts, and logic below are otherwise unchanged from the original export.

## Features

- Single-field web form intake (landing page URL).
- Two independent LLM audit agents run in parallel from the same input: one framed as
  a content/SEO auditor, one framed as a technical SEO auditor, each using the same
  audit-guideline prompt (critical issues, quick wins, opportunities for improvement).
- Both agents run on Google Gemini (`gemini-2.5-pro-exp`).
- Results are merged, aggregated into a single item, and converted from markdown into
  HTML.
- Final report is emailed via Gmail with a subject line naming the audited URL.

## Architecture

Trigger: `Landing Page Url` (n8n Form Trigger, single required field for the landing
page URL).

1. The form trigger fans out to two parallel LangChain Agent nodes:
   - `Technical Audit` (`@n8n/n8n-nodes-langchain.agent`), backed by
     `Google Gemini Chat Model` (`gemini-2.5-pro-exp`).
   - `Content Audit` (`@n8n/n8n-nodes-langchain.agent`), backed by a second Gemini
     chat model node, `Google Gemini Chat Model1`.
   Both agents run the identical audit prompt (technical SEO elements: meta tags,
   headings, structured data, internal linking, page speed, mobile-friendliness,
   indexability; output as Critical Issues / Quick Wins / Opportunities for
   Improvement).
2. `Merge` (n8n Merge node) combines both agents' outputs into one stream, with
   `alwaysOutputData` set so the merge doesn't stall if one branch is slow or empty.
3. `Aggregate` collects the `output` field from both agent results into an array.
4. `Markdown` node converts the two audit outputs into a single markdown document
   ("# On-Page Technical Audit" / "# On-Page SEO Content Audit") and renders it to
   HTML.
5. `Gmail` node sends the rendered HTML as an email, subject line including the
   audited URL.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- Google Gemini (PaLM API) credential, used by both audit agent nodes.
- Gmail credential (OAuth2), used to send the final report.

Before running, set a real "To" address in the Gmail node's `sendTo` field (it ships
with the placeholder `YOUR_EMAIL_HERE`) and connect your own Gemini and Gmail
credentials in n8n's credential manager.

## Usage

Import and activate the workflow, then open the generated form URL and submit a
landing page URL. Within a few seconds an emailed report with two stacked audit
sections (technical, content) arrives at the configured address.

## Challenges

- **The audit agents never actually fetch the page.** Both `Technical Audit` and
  `Content Audit` reference `{{ $json.data }}` in their prompts as "the content of my
  landing page," but the only upstream node is the form trigger, whose output field is
  the URL itself, not a `data` field containing page content. As exported, there is no
  HTTP/scraping node between the form and the two audit agents that would populate
  `$json.data`. This looks like either an incomplete export or a gap in the original
  template: as-is, the agents would be auditing an undefined value rather than real
  page content. Fetching and passing the actual HTML (or rendered text) is required
  before this produces a meaningful audit.
- **Both audits share one prompt.** `Technical Audit` and `Content Audit` use exactly
  the same system prompt text, so in practice they're two identical agents run in
  parallel rather than two genuinely different audit lenses; only the node's name
  differs. Making the prompts actually distinct (one focused on markup/technical
  signals, one on copy/content quality) would be needed to get the two-angle audit the
  workflow's structure implies.
- **No page-fetch failure handling.** Because there's no fetch step, there's also
  nowhere in the graph that would need to handle a page that returns a 404, blocks
  bots, or times out; adding the missing fetch step would also need to add this error
  handling.
- **Single fixed model for both agents.** Both audits are hardcoded to
  `gemini-2.5-pro-exp-03-25`, an experimental/preview model ID at the time this was
  built; a preview model can be deprecated or renamed without notice, which would
  silently break both agents at once.

## What I learned

Reading this workflow's node graph closely surfaced a real gap between what the
prompts assume as input and what the trigger actually provides, the kind of thing
that's easy to miss when a workflow "looks complete" in the n8n canvas but the data
dependency between nodes was never wired through. It's a useful reminder to trace
`$json.<field>` references back to their actual source node, not just assume the
previous node produces what a prompt expects.

## What I'd do differently

I'd add an HTTP Request (or a headless-browser scraping node) between the form
trigger and the two audit agents to actually fetch the landing page's HTML into a
`data` field, write two genuinely distinct prompts for the technical vs. content
audits instead of duplicating one prompt across both agents, and add basic error
handling for pages that fail to load.
