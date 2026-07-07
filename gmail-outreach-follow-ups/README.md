# Gmail Outreach Follow-Ups

## What it is

An n8n workflow that sends two rounds of follow-up email to cold-outreach prospects
who were contacted through Gmail, tracked entirely through a Google Sheet. It replies
in-thread to the prospect's original Gmail message rather than sending a new email,
and it gates each follow-up behind a 36-hour wait so prospects aren't messaged back
to back.

This is a separate system from `cold-email-outreach-sequence-system/` elsewhere in
this portfolio. That one runs follow-ups through Instantly.ai; this one is Gmail-only,
built for prospects the sheet marks as outreached directly through a personal Gmail
account rather than through a bulk sending tool.

## Why it exists

Manually tracking who needs a follow-up, and when, across a spreadsheet of cold
outreach contacts doesn't scale past a handful of people. This workflow reads the
tracking sheet, works out which prospects have gone quiet long enough to warrant a
nudge, sends the pre-written follow-up text as a reply in their existing email
thread, and marks the sheet so the same prospect doesn't get the same follow-up
twice.

## Features

- Two follow-up stages (F1 and F2), each with its own message text pulled from a
  sheet column and its own "done" flag so a stage never fires twice for the same
  prospect.
- A 36-hour (2160-minute) cooldown between the initial outreach and F1, and between
  F1 and F2, computed from a `Sequence Last Date` timestamp column.
- Filters to only Gmail-outreached prospects (`Name - Outreached - I` contains
  "Gmail", equals "gmail", or equals "Salman") before doing anything else.
- Replies inside the original Gmail thread (searches the Sent folder for a message
  to the prospect from the last 7 days, then uses Gmail's reply operation on that
  message id) instead of sending a fresh, threadless email.
- A real-time path seeds the tracking timestamp the moment a new Gmail prospect row
  appears, so the cooldown clock starts immediately instead of waiting for the next
  scheduled run.

## Architecture

The workflow is built from two structurally identical pipelines that both point at
the same spreadsheet and the same "December" tab (see Challenges). What follows
describes one of them; the other duplicates every node and connection below under a
different name (`Schedule Trigger1`, `If5`-`If9`, `Get many messages2`/`3`, `Reply to
a message2`/`3`, and so on).

Within a single pipeline, there are two independent trigger paths that do different
jobs:

**Real-time path (sets the baseline timestamp for new prospects):**

1. **Google Sheets Trigger** (`googleSheetsTrigger`, polls every minute for
   `rowUpdate` events on the sheet): fires when a row in the tracking sheet changes.
2. **If1**: keeps the row only if `Name - Outreached - I` contains "Gmail" or equals
   "gmail" (same filter as the schedule path, minus the "Salman" check).
3. **If2**: keeps the row only if `Sequence Last Date` is empty, meaning this is the
   first time the sheet has seen this prospect.
4. **Append or update row in sheet**: writes `Sequence Last Date` to the current
   timestamp for that row (matched by `Name`). This is the only thing the real-time
   path does; it establishes the cooldown baseline so the schedule path won't try to
   send a follow-up before 36 hours have passed.

**Schedule path (does the actual follow-up sending):**

1. **Schedule Trigger** (`scheduleTrigger`, no explicit interval configured, so it
   runs on n8n's default cadence): fires periodically.
2. **Get row(s) in sheet** (`googleSheets`): pulls every row from the tracking sheet.
3. **If**: keeps rows where `Name - Outreached - I` contains "Gmail", equals "gmail",
   or equals "Salman".
4. **If3** (F1 gate): true only when `F1 Gmail` is not empty, at least 2160 minutes
   (36 hours) have passed since `Sequence Last Date`, and `F1 - Outreach` does not
   already contain "Done". True branch sends F1; false branch falls through to If4.
5. **Get many messages** (`gmail`, `getAll`): searches Gmail for
   `in:sent newer_than:7d to:<Profile URL column value>` to find the original message
   sent to that prospect. The search term is pulled from the sheet's "Profile URL"
   column; whether that column actually holds an email address rather than a URL
   wasn't something this read of the workflow could confirm (see Challenges).
6. **Reply to a message** (`gmail`, `reply`): replies to the message id found above
   with the text from the sheet's `F1 Gmail` column.
7. **Append or update row in sheet1**: marks `F1 - Outreach` as "Done" and updates
   `Sequence Last Date` to now, matched by `Name`.
8. **If4** (F2 gate, reached from If3's false branch): true only when `F2 Gmail` is
   not empty, 2160+ minutes have passed since `Sequence Last Date`, `F1 - Outreach`
   already contains "Done", and `F2 - Outreach` does not.
9. **Get many messages1** / **Reply to a message1**: same thread-search-and-reply
   pattern as steps 5 to 6, using the `F2 Gmail` column text.
10. **Append or update row in sheet2**: marks `F2 - Outreach` as "Done" and updates
    `Sequence Last Date`.

The graph also has eight sticky notes documenting this design (titles like "TRIGGER
METHODS", "FILTERING LOGIC", "F1 SEQUENCE"). Their content matches what the nodes
actually do, with one exception: the "Configuration Notes" sticky says If3/If4 logic
"currently needs completion," but both conditions are fully specified in the export
read for this README, not stubbed out.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Note on the file itself: the original export pointed at a real, live spreadsheet
("Digitalise Prospecting- Skool / 2025"). The `documentId` and `cachedResultUrl`
values in every Google Sheets node in this copy have been replaced with
`YOUR_SPREADSHEET_ID_HERE` and a placeholder URL; the human-readable
`cachedResultName` labels ("Digitalise Prospecting- Skool / 2025", "December") were
left in place since they're descriptive, not secret. The sticky notes also name a
Google account username ("salmanadnan0206") as the label of the OAuth credential
the original used; that's a credential connection name, not a live secret, so it
was left as-is, but you'll create and attach your own credentials on import anyway
(see below).

After import, in each of the Google Sheets and Gmail nodes:

1. Point the `documentId` (currently `YOUR_SPREADSHEET_ID_HERE`) at your own tracking
   spreadsheet, and confirm the `sheetName` tab matches (the original targets a tab
   called "December").
2. Set up the sheet with at minimum these columns: `Name`, `Name - Outreached - I`,
   `Profile URL`, `F1 Gmail`, `F2 Gmail`, `F1 - Outreach`, `F2 - Outreach`,
   `Sequence Last Date`.
3. Attach a Google Sheets OAuth2 credential to every Sheets node, and a Gmail OAuth2
   credential to every Gmail node (see `CREDENTIALS.md`).
4. Decide whether you want both pipelines active, or whether to disable one (see
   Challenges); running both against the same sheet as exported risks duplicate
   sends.

## Usage

Activate the workflow in n8n. The Google Sheets Trigger nodes poll every minute for
row updates and seed the cooldown timestamp on new Gmail prospects; the Schedule
Trigger nodes run on their configured interval and send F1 or F2 follow-ups to any
prospect whose cooldown has elapsed. No manual trigger exists; this is designed to
run unattended once activated.

## Challenges

- **The workflow is two complete, unconnected copies of itself.** Every node in the
  first pipeline (`Schedule Trigger`, `If` through `If4`, `Get many messages`
  through `Reply to a message1`, `Append or update row in sheet` through `sheet2`)
  has an exact counterpart in the second (`Schedule Trigger1`, `If5` through `If9`,
  `Get many messages2`/`3`, `Reply to a message2`/`3`, `sheet3` through `sheet5`).
  Reading every node's parameters confirmed both copies point at the identical
  spreadsheet id and the identical "December" tab, with identical filter logic and
  an identical (default) schedule interval. There's no second sheet, no second tab,
  and no different trigger type that would explain having two; it reads as the same
  logic built or pasted twice into one workflow. If both pipelines were active
  together, they'd double-poll the same sheet and could send the same follow-up to
  the same prospect twice in the same run window, since neither pipeline's "already
  done" check accounts for the other pipeline having just sent it.
- **The Gmail search keys off a column called "Profile URL."** `Get many messages`
  and its duplicates build their search as `to:<Profile URL column value>`. Gmail's
  `to:` search operator expects an email address, not a URL. Either the column holds
  an email address despite its name (leftover naming from an earlier prospecting
  stage that tracked LinkedIn profile links), or this search never matches anything
  useful. The exported workflow doesn't include sheet data, so this couldn't be
  confirmed either way; it's flagged here rather than guessed at.
- **The cooldown timer depends on an exact date-format match.** The 36-hour gate in
  If3/If4/If8/If9 parses `Sequence Last Date` with
  `DateTime.fromFormat(value, "yyyy-MM-dd - hh:mm:ss a")`. Every write path formats
  the timestamp the same way, so this holds as long as no one edits that column by
  hand in a different format; a manual edit that doesn't match exactly would make
  `DateTime.fromFormat` return an invalid date and the time-difference check would
  silently fail to gate correctly.
- **A sticky note is out of date with the actual graph.** The "Configuration Notes"
  sticky says the If3/If4 follow-up routing logic "currently needs completion," but
  both conditions are fully built out with real thresholds. Documentation like this
  drifting from the graph it describes is worth watching for when reading someone
  else's exported workflow instead of trusting the notes at face value.
- **No error handling on the Gmail search.** If `Get many messages` finds no
  matching sent message (the prospect's original email is older than 7 days, was
  sent from a different account, or the `to:` search simply doesn't match), the
  downstream `Reply to a message` node has no message id to reply to and the run
  fails for that item rather than skipping it gracefully.
- **Real-time and scheduled paths only meet through the sheet.** The two trigger
  types never share a node; they coordinate purely by reading and writing the same
  spreadsheet rows. That's a reasonable design for this problem, but it means the
  only thing preventing a race condition between "real-time seeds the timestamp"
  and "schedule sends the follow-up" is that a brand-new row's `Sequence Last Date`
  starts empty and the F1/F2 gates require it to be both non-empty and 36+ hours
  old, not a lock of any kind.

## What I learned

Reading every node's parameters rather than trusting the node names or the sticky
notes was the only way to establish that the two "halves" of this workflow are
genuinely duplicate logic against the same sheet, not a second pipeline for a
different data source. Node names like `If5` and `sheet3` give no hint on their own
that they're a byte-for-byte copy of `If` and `sheet1`'s logic; only the actual
`documentId`, `sheetName`, and condition expressions confirmed it. It's also a
useful pattern to recognize elsewhere: a real-time trigger path that only exists to
seed a baseline value (here, the initial `Sequence Last Date`), paired with a
separate scheduled path that does the actual repeated work, is a clean way to avoid
double-processing on the very first sheet write.

## What I'd do differently

I'd delete one of the two duplicate pipelines rather than leave both in the export,
since running both against the same sheet is a real risk of double-sending a
follow-up, not just dead weight like an unused node. I'd also rename the "Profile
URL" column (or the node that reads it) to make it obvious whether it holds an email
address or an actual profile link, since a `to:` Gmail search silently doing nothing
useful is exactly the kind of failure that only shows up when a prospect stops
getting follow-ups and nobody notices why. Finally, I'd add a fallback branch on
`Get many messages` for the case where no original sent message is found, so a
missing thread produces a flagged row in the sheet instead of a failed execution.
