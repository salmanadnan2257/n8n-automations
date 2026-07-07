# Daily Email Digest, AI Powered

## What it is

An n8n workflow that runs every day at midnight, pulls the last 24 hours of Gmail
messages, summarizes them with an LLM, and sends back a single HTML digest email with
a master summary, an extensive per-batch summary, and the full original emails
(including attachments) laid out with clickable citation links back to the source
message. Live in the source n8n instance under the name "Daily Email Digest - AI
Powered", currently active.

## Why it exists

Reading through a full day of email individually is slow, and important items get
buried. This workflow does the reading first: it groups the day's emails, has an LLM
extract every action item, deadline, decision, and open question with a citation back
to the specific email, then folds all of that into one master briefing so the person
receiving it can get the gist in under a minute and still drill into any cited email
for the full text.

## Features

- Runs on a daily schedule (also has a manual trigger for testing on demand).
- Batches emails in groups of 4 before summarizing, so the LLM prompt for each call
  stays a manageable size instead of stuffing an entire day's mail into one prompt.
- Two-model setup: Google Vertex AI (Gemini 2.5 Pro) as primary, Google Gemini AI
  Studio (Gemini 2.5 Flash) wired in as a fallback if the primary call fails.
- Every extracted fact is cited back to its source email with a `[#N]` marker that
  becomes a clickable anchor link in the final HTML.
- Conditionally attaches original email attachments (up to 50) to the outgoing
  digest, only when at least one exists.
- Digest email includes: a master summary, an extensive combined summary, and every
  original email's full text and attachments, all in one scrollable HTML page.

## Architecture

Node graph, in execution order:

1. **Every Day at Midnight** (`scheduleTrigger`): fires once a day. **When clicking
   'Execute workflow'** (`manualTrigger`) is a parallel entry point for manual testing,
   both feed into the same next node.
2. **Get Emails** (`gmail`, operation `getAll`): pulls every message received in the
   last 24 hours (`$now.minus({days: 1})`), downloading attachments as binary data.
3. **Cluster into Batches of 4** (`code`): a JS Code node that groups the incoming
   email items into batches of 4, building a plain-text block per batch (sender,
   recipient, date, subject, attachment names, body) for the LLM to read.
4. **Summarize Batch (AI)** (`chainLlm`, one call per batch): extracts action items,
   deadlines, key information, and open questions from each batch, citing every point
   back to its email number. Backed by **Google Vertex Chat Model**
   (`lmChatGoogleVertex`, Gemini 2.5 Pro) as the primary model, with **Google Gemini
   Chat Model** (`lmChatGoogleGemini`, Gemini 2.5 Flash) wired in as `needsFallback`.
5. **Compile All** (`code`): reruns over the original `Get Emails` output (via
   `$("Get Emails").all()`) and the batch summaries, and assembles one JSON object
   with the full email list, all attachment metadata, and one combined summaries text
   block.
6. **Master Summary (AI)** (`chainLlm`): a second LLM pass that synthesizes every
   batch summary into one master briefing with fixed section headers (critical action
   items, key information, open questions, attachments, email-by-email digest),
   deduplicating repeated items while keeping every citation. Same Vertex-primary,
   Gemini-fallback model pair.
7. **Format HTML Email** (`code`): a large JS node that turns the master summary and
   the combined batch text into styled HTML: converts the `##` section markers into
   colored headings, turns `[#N]` citations into clickable anchor links to each email,
   renders each original email's full body and attachment badges, and builds an
   attachment index table. Produces the final `html`, `subject`, and attachment
   binaries.
8. **Has Attachments?** (`if`): branches on whether `attachmentCount > 0`.
9. **Send Digest (With Attachments)** / **Send Digest (No Attachments)** (`gmail`,
   send): sends the finished digest, attaching up to 50 files by binary key when the
   `if` branch says there are attachments.
10. **Merge** (`merge`): recombines the two send branches into a single execution
    output.

There is also a **Sticky Note** node in the canvas with no functional role (n8n's
inline documentation/comment feature).

## Setup

1. In n8n: Workflows menu > Import from File > select `workflow.json` from this
   folder.
2. Configure a **Gmail OAuth2** credential and assign it to both the "Get Emails" node
   and the two "Send Digest" nodes.
3. Configure a **Google Vertex AI** credential and assign it to the "Google Vertex
   Chat Model" node.
4. Configure a **Google Gemini (AI Studio) API key** credential and assign it to the
   "Google Gemini Chat Model" node.
5. Replace the `YOUR_EMAIL_ADDRESS_HERE` placeholder in both "Send Digest" nodes'
   `sendTo` field with the real recipient address(es).
6. Activate the workflow, or trigger it manually via "When clicking 'Execute
   workflow'" to test.

See `CREDENTIALS.md` for the full list of required accounts.

## Usage

Once active, the workflow runs unattended every day at midnight and delivers one
digest email per run. For ad hoc testing, use the manual trigger node directly inside
n8n, which runs the exact same pipeline on demand.

## Challenges

- **Keeping the LLM from missing or inventing information.** Summarizing a full
  inbox risks either dropping real details or hallucinating ones that were not there.
  The prompt design addresses this directly: it demands citation of every extracted
  point with `[#N]`, explicitly forbids inventing or inferring anything not stated,
  and requires the model to internally verify completeness before returning output.
  Whether the model actually complies every run is not verified here; this only
  confirms the prompt is designed to constrain it.
- **Prompt size blowing up with a busy inbox.** Feeding an entire day of email into
  one LLM call risks hitting context limits or degrading quality. The workflow
  addresses this by batching into groups of 4 before summarizing, then running a
  second synthesis pass over the batch summaries rather than the raw emails.
- **Model reliability.** A single LLM provider call can fail or rate-limit. The
  workflow addresses this with `needsFallback: true` wired to a second model (Gemini
  Flash via AI Studio) on both chain-LLM nodes, so a Vertex failure does not stop the
  whole run.
- **Rebuilding structured HTML from freeform LLM text.** The final formatting step
  depends on the LLM consistently emitting the exact `##` section headers and `[#N]`
  markers the prompt asks for. The "Format HTML Email" code node's regexes only
  recognize specific header text patterns; if the model drifts from the requested
  format, sections silently fail to get styled and fall through as plain paragraph
  text. There is no explicit validation step catching this, it is a soft failure.
- **Attaching the right files back to the right email.** With multiple emails each
  carrying different attachments, the workflow rebuilds an attachment index keyed by
  email number and gates the digest's own attachment fields with conditional
  expressions (`attachmentCount >= N`) up to 50, rather than a dynamic loop, which
  means a 51st attachment would silently not be attached. This is a real ceiling
  in the current design.

## What I learned

- Running two-pass summarization (per-batch, then a master synthesis over the batch
  summaries) is a practical way to keep an LLM call within a reasonable prompt size
  without truncating the source material outright.
- Wiring a fallback language model onto a chain-LLM node (`needsFallback`) is a low
  effort way to add resilience to a single point of failure, at the cost of needing
  two credentials configured instead of one.
- Citation-based extraction (`[#N]` per fact) turns an LLM summary from a black box
  into something a reader can verify by clicking through, which matters a lot more
  for an email digest than for casual chat output.

## What I'd do differently

- Replace the fixed `attachmentCount >= N` ladder (hardcoded up to 50) in the send
  nodes with a proper loop or a code-generated list, so the attachment ceiling is not
  a silent, undocumented limit.
- Add an explicit check after the LLM summary steps that the expected `##` section
  headers are actually present, and fall back to raw text (or flag the run) instead
  of silently degrading formatting when the model doesn't follow the requested
  structure.
- The workflow currently has commented-out dead code sitting inside the "Format HTML
  Email" node (an earlier version of the same rendering logic, left in as a block
  comment). That should be deleted rather than kept as a comment, it makes the node
  harder to read for no benefit.
