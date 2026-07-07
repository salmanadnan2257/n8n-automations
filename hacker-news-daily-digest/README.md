# Hacker News Daily Digest

## What it is

An n8n workflow that pulls the top Hacker News stories, fetches the linked article
for each one, summarizes it with an LLM, and emails the whole batch out as a single
daily digest. Runs manually from the n8n editor (no schedule trigger wired in).

## Why it exists

Reading Hacker News properly (opening every link, reading the article, forming an
opinion) takes longer than most people have. This automates the first pass: it
picks the top stories, fetches the actual article content behind each one, and
hands back a plain-text summary of each so you can decide what's worth reading in
full, without opening ten tabs.

## Features

- Fetches Hacker News stories through n8n's built-in Hacker News node.
- Caps the batch to 5 stories with a Limit node, so a run stays fast and cheap.
- Loops over each story, downloads the linked page, converts the HTML to Markdown,
  and passes that Markdown to an LLM for summarization.
- Summaries are aggregated into one email body and sent through SMTP.
- Per-item HTTP fetch failures don't stop the run; that node is configured to
  continue on error.

## Architecture

Node-by-node, in execution order:

1. **When clicking 'Execute workflow'** (`manualTrigger`): starts the workflow. There
   is no cron/schedule trigger in this export, so "daily" is aspirational until
   someone wires a Schedule Trigger node in front of it (see Challenges).
2. **NEWS API** (`httpRequest`): present in the graph but disabled and has no URL
   or parameters configured. n8n skips disabled nodes and passes items through
   unchanged, so this node currently does nothing; it looks like leftover
   scaffolding from an earlier version that hit an external news API directly.
3. **Get many items** (`n8n-nodes-base.hackerNews`, resource `all`): fetches
   Hacker News items through n8n's built-in node (backed by the Algolia HN
   search API). No additional filters are set.
4. **Limit**: keeps only the first 5 items from that list.
5. **Loop Over Items** (`splitInBatches`, batch size 10): since only 5 items ever
   reach it, this runs as a single batch, but it's still functioning as an
   explicit loop: its "loop" output feeds the per-item fetch/summarize chain,
   and downstream nodes route back into it (see step 9) until all items in the
   batch are processed, at which point its "done" output fires into Aggregate.
6. **HTTP Request**: for each item, fetches the article at
   `$('Limit').item.json._highlightResult.url.value`, an Algolia search result
   field, confirming the Hacker News node returns Algolia-shaped objects, not the
   raw Firebase HN API shape. Configured with `continueErrorOutput`, so a dead
   link or non-HTML response doesn't kill the run, just that item.
7. **Markdown**: converts the fetched page's HTML body into Markdown text.
8. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`): takes the Markdown, and with a
   system prompt telling it to summarize the article and format it for a daily
   digest email (plain text, no Markdown formatting characters), produces a
   summary. It's backed by:
9. **Google Gemini Chat Model** (`lmChatGoogleGemini`, model
   `gemini-2.0-flash-lite`): the actual LLM behind the AI Agent node.
10. **Edit Fields** (`set`): stores the AI Agent's output under an `output` field,
    then the connection loops back into **Loop Over Items** to pull the next
    batch item (or finish, if this was the last one).
11. **Aggregate** (`aggregateAllItemData`): once Loop Over Items' "done" output
    fires, this collects every processed item's data into one array.
12. **Edit Fields1** (`set`): builds a `final` string, "News Daily Digest:"
    followed by each item's `output` summary joined with blank lines.
13. **Send email** (`emailSend`): sends `final` as the email body over SMTP.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials this workflow needs, configured in n8n's credential store after import:

- An SMTP credential for the **Send email** node (any SMTP provider works: Gmail
  SMTP, SendGrid, Mailgun, etc).
- A Google Gemini / Google AI credential (API key) for the **Google Gemini Chat
  Model** node.

No credential is needed for the Hacker News node itself; the Algolia HN search API
it calls is public and unauthenticated. If you re-enable the disabled **NEWS API**
node, whatever API it's meant to call would need its own credential, but as
exported it has no URL configured, so there's nothing to wire up.

### A note on file size

The original export of this workflow was about 960 KB, unusually large for a
13-node n8n workflow. Inspecting it showed why: n8n had cached roughly 710 KB of
`pinData`, pinned execution output from past test runs, attached to four nodes
("Get many items", "HTTP Request", "Markdown", "AI Agent"). That data is cached
output for previewing in the n8n editor; it isn't part of the workflow's logic and
isn't read when the workflow actually runs. The copy in this repo has that pinned
data stripped (confirmed the workflow still parses and its node/connection
structure is unchanged) so the shipped file is under 9 KB. The only cost of this
is that if you open the workflow in n8n, node panels won't show cached sample
output from a past run; running it again produces fresh output as normal.

## Usage

Open the workflow in n8n and click "Execute workflow" (or trigger it via the n8n
API/CLI). It fetches, summarizes, and emails a digest of 5 Hacker News stories
each time it's run. To make it genuinely "daily," add a Schedule Trigger node in
front of it, since the current trigger is manual-only.

## Challenges

- **No real "daily" trigger.** Despite the name, the workflow only has a manual
  trigger. Anyone deploying this needs to add a Schedule Trigger themselves; it
  isn't wired up in the export.
- **Algolia's HN node vs. the raw HN API.** The URL extraction expression reaches
  into `_highlightResult.url.value`, an Algolia search-result field. That's a
  fragile path: it depends on n8n's Hacker News node continuing to return
  Algolia's schema rather than the plain Firebase HN API shape, and it silently
  breaks if a story has no URL at all (Ask HN / text posts), since
  `_highlightResult.url` won't exist for those.
- **Fetching arbitrary article URLs is unreliable.** Linked sites can be
  paywalled, JS-rendered, geo-blocked, or just down. The workflow only guards
  against this with `continueErrorOutput` on the HTTP Request node, which stops a
  bad fetch from killing the whole run, but doesn't handle partial failures
  gracefully; a failed item just produces no Markdown and the AI Agent has
  nothing to summarize for it.
- **LLM summarization has no formatting or length enforcement.** The system
  prompt asks for plain text with no Markdown symbols, but there's no
  post-processing step that verifies the model actually complied. If the model
  drifts and adds a bullet list or asterisks, that goes straight into the email
  unchecked.
- **The disabled "NEWS API" node is dead weight.** It sits in the middle of the
  trigger chain, contributes nothing, and would confuse anyone reading the graph
  for the first time without checking that it's disabled.
- **Batch size vs. Limit is inconsistent.** `Loop Over Items` is configured for
  batches of 10, but `Limit` upstream caps the list at 5. The batching logic
  works fine at that size, but it's a mismatch that would only reveal its intent
  (or a bug) if someone later raised the Limit above 10.

## What I learned

Inspecting the exported JSON directly, rather than trusting file size or node
count, was the only way to catch that this workflow was 74% pinned test data.
n8n's export format doesn't distinguish "this is workflow logic" from "this is
cached debug output" at a glance; you have to check the `pinData` key. It's also
a useful reminder that `splitInBatches` isn't just for pagination: here it's used
as a loop construct, with a downstream node routing back into it to process one
item per iteration, which is a pattern worth recognizing when reading someone
else's n8n graphs.

## What I'd do differently

I'd replace the manual trigger with a Schedule Trigger so the workflow actually
matches its name, remove the dead "NEWS API" node instead of leaving it disabled
in place, and add a fallback path for items where the HTTP fetch fails (at
minimum, note in the digest which stories couldn't be fetched instead of just
dropping them silently). I'd also validate the Hacker News node's response shape
before extracting `_highlightResult.url.value`, since that expression will throw
or produce a bad URL for text-only posts.
