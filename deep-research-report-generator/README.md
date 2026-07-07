# Deep Research Report Generator

## What it is

An n8n workflow that takes a single search topic (submitted through a web form), breaks
it into five subtopics, researches each one on the web, writes a formatted HTML chapter
for each, stitches the chapters into one report with a title page, introduction, table
of contents, and sources list, renders the whole thing to a PDF, and emails it to the
person who submitted the form.

## Why it exists

Doing this by hand means five separate research sessions, a lot of copy-pasting into a
document, manually tracking which source number goes with which claim, and formatting
a report by hand. This workflow automates the whole chain: topic breakdown, web search,
per-section writing with inline numbered citations, table-of-contents generation, PDF
rendering, and delivery.

## Features

- Single form submission (topic + email) triggers the entire pipeline.
- One LLM call decomposes the topic into five distinct subtopics.
- A second LLM call generates the report title, a two-paragraph introduction, and five
  chapter headings, all in styled HTML, which also serves as the style guide the later
  chapter-writing calls are told to match.
- Five parallel research branches, one per subtopic: web search, per-result HTML
  section writing with inline `[n]` citation links, and running citation numbers that
  stay unique across all five chapters (chapter 1 starts at source 1, chapter 2 at
  source 6, and so on).
- A Google Sheet is used as shared intermediate storage: each branch writes its content,
  sources, and section titles to its own set of columns in a row matched by the search
  topic, so later steps can re-read the fully assembled row.
- Auto-generated Table of Contents and Sources sections, each following the same style
  guide as the rest of the report.
- Final HTML is combined and sent to a PDF rendering API, and the resulting PDF is
  emailed as an attachment to the address given in the form.

## Architecture

Trigger and planning:

1. **On form submission** (`n8n-nodes-base.formTrigger`) collects `Search Topic` and
   `Email`.
2. **Plan Topics** (`@n8n/n8n-nodes-langchain.agent`, backed by **OpenRouter Chat
   Model** calling `anthropic/claude-3.5-sonnet` through OpenRouter) breaks the topic
   into five subtopics, parsed into a fixed `topic_1..topic_5` object by the **5
   Topics** structured output parser (`@n8n/n8n-nodes-langchain.outputParserStructured`).
3. **Intro** (another `agent` node, its own OpenRouter chat model) takes the topic plus
   the five subtopics and produces a report title, a styled HTML introduction, and five
   `<h2>` chapter headings, parsed by the **Title, Intro, Chapters** structured output
   parser. This is written to the Google Sheet by **Send Intro** (append).
4. In parallel, **Split Out** pulls the five subtopic strings out of Plan Topics'
   output, and **Set Topics** / **Split Out1** produce five items labeled
   `topic_1..topic_5`. **Merge1** (combine by position) pairs each subtopic string with
   its label, and **Merge** (combine all) joins that with the Send Intro output as a
   synchronization point.
5. **Switch** routes the five paired items into five separate branches, one per
   condition (`topics == topic_1` through `topic_5`). This is a fixed fan-out, not a
   `splitInBatches` loop: there are five hardcoded branches rather than one loop body
   that repeats five times.

Per-chapter branch (this exact chain is duplicated five times, once per subtopic,
suffixed 1-4 in the node names):

6. **Tavily** (`httpRequest`, `POST https://api.tavily.com/search`, HTTP header auth)
   runs an "advanced" depth web search for the subtopic, capped at 5 results with 3
   content chunks per source.
7. **Split Out2..6** split the Tavily `results` array into one item per search result.
8. **Code / Code1..4** number the result URLs. Each branch's starting number is
   hardcoded: chapter 1 starts at 1, chapter 2 at 6, chapter 3 at 11, chapter 4 at 16,
   chapter 5 at 21, so citation numbers stay unique across the final report.
9. **Writer / Writer1..4** (agent nodes, one OpenRouter chat model each) write a styled
   HTML section for each individual search result, given the result's title, content,
   numbered source, and the Intro node's HTML output as a style guide to match. Inline
   citations use `<a href="URL" target="_blank">[n]</a>`.
10. **Aggregate / Aggregate1..9** collect the five (or fewer) Writer outputs into one
    array, and separately collect the numbered source URLs into another array.
    **Merge3..7** (combine by position) zip those two arrays back into a single item.
11. **HTML / HTML1..4** (`n8n-nodes-base.html`, `extractHtmlContent`) pull the `<title>`
    tag back out of each Writer section's HTML, and **Combine / Combine1..4** collect
    those titles into a `sections` array, reusing already-generated content instead of
    asking the model again for a section list.
12. **Google Sheets1..5** (`update`) write that branch's `Topic N Sources`, `Topic N
    Content`, and `Topic N Sections` columns into the shared row, matched on the
    `Search Topic` column.

Final assembly:

13. **Merge2** (`numberInputs: 5`) waits for all five Google Sheets writes to finish,
    then **Limit** and **Get Sources** re-read the full row from the sheet.
14. **Sources** (agent) builds a single HTML "Sources" section, an ordered list of
    numbered, clickable links, from all five `Topic N Sources` columns. **Send Sources**
    writes it back to the sheet's `Sources` column.
15. **Get All Content** re-reads the row again, and **Table of Contents** (agent) builds
    an HTML table of contents from the five chapter titles and their per-chapter
    `sections` arrays, following the same style guide. **Send ToC** writes it to the
    `ToC` column.
16. **Get All Content1** re-reads the row one more time, and **Combine Content** (code
    node) concatenates Title, Introduction, ToC, and each Chapter heading plus its
    Topic N Content, plus Sources, into one HTML string field, `CombinedContent`.
17. **Generate PDF** (`httpRequest`, `POST
    https://rest-us.apitemplate.io/v2/create-pdf-from-html`, APITemplate.io
    credential) renders that HTML to an A4 PDF with page-number header/footer.
18. **Download PDF** (`httpRequest`, `GET` on the returned `download_url`) fetches the
    rendered PDF as binary.
19. **Send Report** (`n8n-nodes-base.gmail`) emails the PDF as an attachment to the
    address collected in the form.

Every hop through the Google Sheet is a deliberate synchronization mechanism: five
branches finish at different times, and the sheet acts as external shared state that
later nodes explicitly re-read rather than n8n trying to hold five in-flight branches
in memory and merge them directly.

## Setup

1. Open n8n, go to **Workflows > Import from File**, and select `workflow.json`.
2. Create your own copy of a Google Sheet with columns matching what the workflow
   reads and writes: `Search Topic`, `Title`, `Introduction`, `Chapter 1..5`, `Topic
   1..5 Sources`, `Topic 1..5 Content`, `Topic 1..5 Sections`, `Sources`, `ToC`. Every
   Google Sheets node in the workflow points at one specific spreadsheet and sheet;
   update each node's `documentId` and `sheetName` to point at your copy.
3. Set up these accounts/credentials in n8n's credential store and attach them to the
   matching nodes:
   - **OpenRouter API** (attach to all seven `OpenRouter Chat Model*` nodes).
   - **Tavily API** as an HTTP Header Auth credential (`Authorization: Bearer <token>`),
     attached to the five `Tavily*` HTTP Request nodes.
   - **Google Sheets OAuth2**, attached to every Google Sheets node.
   - **APITemplate.io API**, attached to the `Generate PDF` node.
   - **Gmail OAuth2**, attached to `Send Report`.
4. Activate the workflow so the form trigger is reachable, or run it manually from the
   n8n editor for testing.

## Usage

Open the form URL generated by the **On form submission** trigger, enter a research
topic and an email address, submit, and wait. The workflow runs unattended from there:
topic planning, five parallel research-and-write branches, table of contents and
sources assembly, PDF rendering, and email delivery. Total run time depends on the
LLM and search API response times across roughly a dozen chained calls; this was not
timed end to end here since it needs live OpenRouter, Tavily, and APITemplate.io
credentials and a real Google Sheet to execute, none of which are safe to embed in this
Portfolio.

## Challenges

- **No pagination or retry handling on the search calls.** Each `Tavily` node is a
  bare HTTP request with no retry-on-fail or error branch configured. If Tavily
  rate-limits or times out on any one of the five parallel branches, that branch's
  Google Sheets write never happens, and `Merge2` (`numberInputs: 5`) stalls forever
  waiting for a fifth input that never arrives, with no visible failure.
- **Google Sheets keyed on topic text, not a run ID.** Every read/write matches rows on
  the literal `Search Topic` string. Two submissions of the same topic (or the same
  topic resubmitted) will match and overwrite the same row, which can corrupt whichever
  report is still mid-flight. There is no per-run identifier anywhere in the workflow.
- **Fixed five-way fan-out instead of a real loop.** The five chapter branches are
  five hand-duplicated node chains gated by a `Switch` with five hardcoded conditions,
  not a `splitInBatches` loop over however many subtopics `Plan Topics` returns.
  Supporting more or fewer chapters means cloning or deleting an entire branch and
  manually adjusting the citation-numbering offsets in every `Code` node.
- **Citation numbering assumes exactly five results per topic.** The offsets in
  `Code`, `Code1`, `Code2`, `Code3`, `Code4` are hardcoded (`+1`, `+6`, `+11`, `+16`,
  `+21`), which only lines up if Tavily returns exactly five results for every
  subtopic. `max_results: 5` is a ceiling, not a guarantee; a topic returning fewer
  results leaves a numbering gap in later chapters rather than breaking anything
  outright, but the offsets are never computed from actual counts.
- **No validation on the structured LLM outputs.** `Plan Topics` and `Intro` both rely
  on the model returning JSON that matches an exact schema (`topic_1..topic_5`,
  `chapter_1..chapter_5`), with no retry or fallback node if the model omits a key or
  nests the response wrong. The `Switch` node's conditions also depend on `Set Topics`'
  hardcoded label array lining up with whatever keys `Plan Topics` actually produced.
- **Single point of failure at PDF rendering with no error branch.** `Generate PDF`
  assumes APITemplate.io always returns a `download_url`. There is a manual
  `.replace()` on quotes and newlines before sending the HTML, but no full JSON-escaping
  and no IF node checking for a failed response; a large or malformed combined HTML
  string can fail rendering with no fallback path, and the user never receives an
  email.

## What I learned

- A `Switch` node with a fixed number of literal-value conditions is a legitimate way
  to fan out into parallel branches with per-branch configuration (here, different
  citation-numbering offsets per chapter) when the branch count is known ahead of time,
  but it trades that per-branch flexibility for being much harder to scale or resize
  than a genuine `splitInBatches` loop.
- Using a Google Sheet as a scratch coordination layer across independent branches is
  a practical workaround for the fact that five branches with LLM calls in them will
  finish at different times; writing intermediate state to an external row and having
  later nodes explicitly re-read it sidesteps trying to hold five async branches in
  memory and merge them directly inside the workflow.
- `combineByPosition` merges are used repeatedly here to zip two arrays that came from
  the same source items (the written HTML sections and their numbered source URLs)
  back into one object per item. It only works because both aggregates are built from
  items that were in the same order to begin with; this is an easy assumption to break
  if any upstream node reorders or filters items.
- The `html` node's `extractHtmlContent` operation is used to pull a `<title>` tag back
  out of HTML the workflow itself just generated, which recovers a clean section
  heading list for the Table of Contents without a second round-trip prompt to the
  model asking it to restate its own title.

## What I'd do differently

- Replace the `Search Topic` text match with a UUID generated right after the form
  trigger, and match every Google Sheets read and write on that ID instead, so
  identical or repeated topics can't collide.
- Rebuild the five duplicated branches as one `splitInBatches` loop driven off the
  actual subtopics `Plan Topics` returns, so the chapter count isn't hardcoded to five
  node chains and citation offsets can be computed from the running count of sources
  seen so far instead of static `+1/+6/+11/+16/+21` literals.
- Add an IF node after each `Tavily` call and after `Generate PDF` to check for a
  failed or empty response, with a fallback path (skip that topic's sources, or email
  the user a partial-failure notice) instead of letting a stalled branch silently hang
  the `numberInputs: 5` merge forever.
- Add basic structured-output validation (or a retry loop) after `Plan Topics` and
  `Intro`, since the whole rest of the pipeline depends on those two calls returning
  exactly the keys the downstream nodes expect.
