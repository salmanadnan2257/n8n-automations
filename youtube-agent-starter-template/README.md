# YouTube Agent Starter Template

## What it is

An n8n starter workflow for a YouTube competitor-research agent: it tracks a list of
YouTube channels in a Google Sheet, has an AI agent pull each channel's stats and new
videos since the last check, updates the sheet with growth numbers, and has a second,
mostly-unbuilt agent stubbed in to eventually research each new video and suggest
content ideas.

This is explicitly course material, not an original build: it was extracted from
the zip archive for the paid course "Build A YouTube Agentic Workflow with n8n," and
its file name on disk is `n8n YouTube Agent - Starter Template.json`. The workflow is
a starter/skeleton as shipped by the course, not a finished product; the second half
of it (the "Video Agent") is intentionally left as placeholder text for the course's
students to fill in themselves, and that placeholder state is preserved here rather
than completed, so the documentation below describes what the file actually contains.

## Why it exists

It's included in this Portfolio as an honest example of a course-provided scaffold: a
working first half (channel tracking) and a deliberately unfinished second half (video
research), which is a useful, realistic artifact to read and explain, distinct from
the fully-built workflows elsewhere in this collection.

## Features

- Google Sheets-backed channel list ("YouTube Channel Tracker") with a `Last Visited`
  date per channel, so each run only looks at videos published since the last check.
- A LangChain agent (`Channel Agent`) with two YouTube Data API tools (get a channel,
  list a channel's videos) that autonomously decides which tool calls it needs to
  answer "what's new on this channel since date X."
- Structured output parsing: the agent's result is forced into a fixed JSON schema
  (channel stats plus a videos array) via a Structured Output Parser node, so
  downstream nodes get a predictable shape rather than free text.
- Updates the sheet with subscriber/view/video counts and computed growth deltas
  (this run's numbers minus last run's) for each tracked channel.
- Deduplicates the new-videos list before handing it to the second agent.
- Can run manually or on a weekly schedule (Saturday), both wired to the same entry
  point.

## Architecture

Two trigger nodes feed the same first node: `When clicking 'Execute workflow'`
(Manual Trigger) and `Schedule Trigger` (weekly, Saturdays).

1. `Get row(s) in sheet` (Google Sheets) reads every tracked channel's row from the
   "Channels" tab of the "YouTube Channel Tracker" sheet, including each channel's
   `Last Visited` date and prior stats.
2. `Channel Agent` (`@n8n/n8n-nodes-langchain.agent`) receives one channel's ID and
   last-visited date per item. It has two tools available:
   - `Get a channel in YouTube` (`n8n-nodes-base.youTubeTool`, operation `get`) fetches
     channel snippet/statistics/status.
   - `Get many videos in YouTube` (`n8n-nodes-base.youTubeTool`, resource `video`,
     `returnAll`) lists videos published after the channel's last-visited date.
   The agent is backed by `OpenAI Chat Model1` (`gpt-4.1-mini`, forced to
   `json_object` response format) and constrained by a `Structured Output Parser`
   node whose JSON schema fixes the output shape (channel stats, plus a videos array
   of id/title/publishedAt).
3. The agent's output fans out two ways:
   - `Split Out Videos` breaks the `output.videos` array into one item per video, then
     `Remove Duplicates1` drops repeats before handing off to the (unbuilt) `Video
     Agent`.
   - `Update row in sheet` (Google Sheets) writes the new subscriber/view/video counts
     back to the channel's row, computing each growth delta against the row's
     previous values, and stamps today's date as the new `Last Visited`.
4. `Video Agent` (`@n8n/n8n-nodes-langchain.agent`) is present as a node but its prompt
   and system message are literal placeholder text
   (`[Pass video Id and short instructions here]`, `[Role] / [Mission and Context] /
   [Steps/Guidance] / [Output]`), and it has no connected tools or output path in the
   `connections` graph (`"Video Agent": { "main": [[]] }`). It is a course-provided
   stub meant for the student to complete: per the course's own sticky notes, it
   should eventually get video details, get video comments, and save findings back to
   Sheets, then send a compiled list of new video ideas by email. None of that is
   built in this file.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- Google Sheets OAuth2 account, connected to a "YouTube Channel Tracker" spreadsheet
  with a "Channels" tab (columns include Channel ID, Subscribers, Total Views, Videos,
  Last Visited).
- YouTube Data API credential (OAuth2), with the YouTube Data API enabled in Google
  Cloud Console, for both YouTube tool nodes.
- OpenAI API credential, for the Channel Agent's language model.

Before running, point the two Google Sheets nodes at your own spreadsheet (the
original references a specific document ID and tab), and populate the Channels tab
with at least one real YouTube channel ID.

## Usage

As shipped, only the channel-tracking half is functional: running it will pull new
videos and updated stats for every tracked channel and log growth numbers to the
sheet. The video-research half (`Video Agent`) needs its prompt, tools (get video
details, get video comments, save to sheet), and output wiring built out before it
does anything; right now triggering that branch would run an agent with an empty
instruction set and nowhere to send its output.

## Challenges

- **The second agent is not built.** `Video Agent`'s prompt and system message are
  literal template placeholders, and it has no tools or output connections. This is
  the course's intended "exercise for the student" structure, but it means this
  workflow cannot, as imported, do the video-level research and idea generation its
  own sticky notes describe. Building that out (video-detail tool, comment-fetching
  tool, sheet-logging tool, and an email step) is real, non-trivial work left
  incomplete by design.
- **Growth math breaks on a channel's first run.** `Update row in sheet` computes
  `Growth (Subscribers)` etc. as this run's count minus the sheet's existing value.
  For a channel added to the tracker for the first time, that existing value is blank,
  so the first growth calculation is against an empty cell rather than a real
  baseline.
- **`returnAll` on the videos tool has no cap.** `Get many videos in YouTube` fetches
  every video published after the last-visited date with no page limit; a channel
  that hasn't been checked in months, or a very high-frequency uploader, could return
  a large result set into the agent's context in one call.
- **Duplicate detection is generic.** `Remove Duplicates1` uses n8n's default
  dedupe (comparing full item equality) rather than deduping specifically on video ID,
  so if the agent ever returns the same video with slightly different fields across
  two channels' runs, it would not be caught.
- **Structured-output schema and system-message schema are slightly different.** The
  agent's system message describes the target JSON shape one way (missing a comma
  between `channle_statistic` and `videos` in the literal prompt text) while the
  Structured Output Parser's schema is separately defined; if a future model is less
  forgiving about the malformed example in the prompt, the two could drift out of
  sync in a way that's hard to spot without reading both closely, which is how this
  was found.

## What I learned

Course-provided starter templates are often deliberately half-built as a teaching
device, and treating the unbuilt half as a bug to hide rather than a fact to disclose
is the wrong instinct for a portfolio; documenting exactly where the scaffold stops
and the exercise begins is more useful and more honest than dressing it up as
complete. I also confirmed, by tracing `$fromAI()` tool parameters and the output
parser schema side by side, that the "channel agent" half is genuinely functional
end to end, not just plausible-looking.

## What I'd do differently

If I were finishing the course exercise rather than just documenting the starter, I'd
build the `Video Agent`'s tools (video details, video comments) and output path (sheet
logging, email digest) next, fix the first-run growth-delta math to treat a blank
baseline as zero rather than subtracting against nothing, and cap `Get many videos in
YouTube`'s result size so a long-dormant tracked channel can't flood the agent's
context in one run.
