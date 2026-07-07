# Social Media Trend Monitor

An n8n workflow that is meant to scan multiple social platforms and search sources
daily, score what is trending, and report the findings to a Slack channel and a
Google Sheets content calendar.

## Why it exists / origin disclosure

This workflow's name and structure ("Monitor Content Trends Across Social Media with
AI, Slack, and Google Sheets") match a pattern that circulates widely as a public n8n
community template: a daily schedule trigger, a large hardcoded content-strategy
config, a batch loop, several AI scraper nodes for different platforms, a merge, an
analysis code node, and Slack plus Sheets outputs. This is very likely an
adapted or imported copy of that kind of template rather than an original in-house
design. I cannot verify from the JSON alone which specific template or author it
originated from, so I am not naming one. It is included here as a worked example of
reading, understanding, and honestly documenting an existing automation, not as a
from-scratch design of mine.

Reading through the exported JSON turned up a real, concrete problem with the copy
itself: several of the connections needed to make the pipeline actually run are
missing. That is detailed in Challenges below, since it changes what this workflow
can honestly be said to do.

## Features (as designed)

- Runs on a recurring schedule to catch fresh trends without manual triggering.
- Builds a large query set across 8 platforms (LinkedIn, Twitter, Instagram, YouTube,
  TikTok, Facebook, Pinterest, Reddit) and 10 industries, plus a separate Google Trends
  keyword query set and a competitor/viral-content query set.
- Processes that query set in batches, one query per iteration.
- Uses AI-driven scraper nodes to pull data from social platforms, Google Trends,
  BuzzSumo-style viral content sources, and Reddit discussions.
- Scores trend momentum, flags content gaps against existing content, and produces
  prioritized recommended actions (high/medium/low, each with a timeline).
- Appends a row to a Google Sheets content calendar and posts a summary to Slack.

## Architecture

Node types actually present in `workflow.json`:

- `n8n-nodes-base.scheduleTrigger` - "Daily Trend Monitor Trigger": fires on an
  interval.
- `n8n-nodes-base.code` - "Trend Configuration Processor": builds the industries,
  platforms, content-calendar rules, and engagement thresholds, then generates the
  full list of trend/keyword/competitor search queries with per-platform search URLs.
- `n8n-nodes-base.splitInBatches` - "Split Trend Queries": iterates the query list one
  batch at a time.
- `n8n-nodes-base.code` - "Query Processor": pulls the current batch index and
  resolves which query in the combined list that index corresponds to.
- `n8n-nodes-scrapegraphai.scrapegraphAi` x4 - "AI Social Trend Scraper", "AI Google
  Trends Scraper", "AI Viral Content Analyzer", "AI Reddit Insights Scraper": a
  community node package (ScrapeGraphAI) meant to run AI-assisted scraping/extraction
  against the target platform for the current query.
- `n8n-nodes-base.merge` - "Merge Trend Data": combines the four scrapers' outputs
  with the original config data.
- `n8n-nodes-base.code` - "Trend Analysis Processor": computes trend momentum,
  content gaps, viral patterns, community insights, a trend health score, and
  prioritized recommended actions from the merged data.
- `n8n-nodes-base.googleSheets` - "Content Calendar Updater": appends a row to a
  Google Sheets tab named `Content_Calendar_2025`.
- `n8n-nodes-base.slack` - "Team Notification Sender": posts a formatted trend
  report to a Slack channel.
- `n8n-nodes-base.stickyNote` x5: documentation-only notes describing each stage,
  no functional role.

Intended data flow, per the sticky notes and node layout: schedule trigger to
config processor to batch splitter to query processor to four parallel AI scrapers
to merge to trend analysis to Google Sheets and Slack in parallel.

**What the JSON actually wires up is narrower than that.** The `connections` object
in the file has no entries at all for "Query Processor" or for any of the four
`scrapegraphAi` nodes. Concretely: nothing connects "Query Processor" to the
scrapers, nothing connects the scrapers to "Merge Trend Data", and "Merge Trend
Data" itself has no inbound connections in the file, only an outbound one to "Trend
Analysis Processor". The trigger, config processor, and batch splitter are wired
correctly, then the graph goes dead until "Merge Trend Data", which has nothing
feeding it. As exported, the workflow would not deliver any real scraped data to the
analysis or reporting stages; it would need those connections added by hand before
it does anything useful. This is stated plainly rather than glossed over, per the
origin disclosure above.

## Setup

1. In n8n: Workflows menu, Import from File, select `workflow.json`.
2. Install the ScrapeGraphAI community node package if it is not already installed
   on the n8n instance (Settings, Community Nodes, install `n8n-nodes-scrapegraphai`,
   or the npm equivalent for a self-hosted instance). Without it the four scraper
   nodes will show as unrecognized.
3. Assign credentials to each node that needs one (see `CREDENTIALS.md`):
   - ScrapeGraphAI API, on each of the four AI scraper nodes.
   - Slack API, on the notification node.
   - Google Sheets OAuth2, on the content calendar node.
4. Replace the placeholder Google Sheets document ID (`1your-content-calendar-sheet-id`
   in the "Content Calendar Updater" node) with a real spreadsheet ID, and make sure
   that spreadsheet has a `Content_Calendar_2025` tab with matching columns.
5. Set the Slack channel name in "Team Notification Sender" to a real channel the
   credential's bot/user can post to.
6. Fix the missing connections described in Architecture above (Query Processor to
   each scraper node, each scraper node to Merge Trend Data) before activating, or the
   scheduled run will do nothing past the batch splitter.
7. Review the schedule trigger. It is currently set to "every 24 hours" with no
   anchor time, not literally 8 AM as its note claims (see Challenges).

## Usage

Once imported, wired, and credentialed, activating the workflow runs it on the
configured interval. Each run is meant to generate the query set, work through it in
batches, gather AI-scraped trend data per query, analyze it, log a calendar entry to
Google Sheets, and post a trend summary to Slack. It can also be run manually from
the n8n editor for a one-off check.

## Challenges

- **Trend-data source integration.** The four AI scraper nodes ship with empty
  `parameters` in the JSON: no prompt, no target URL, no extraction schema. They are
  placeholders for where scraping logic belongs, not working scrapers. The workflow's
  design assumes ScrapeGraphAI can turn a search URL and a natural-language ask into
  structured trend data, but none of that configuration is actually present here, so
  this is not addressed by the graph as exported. It would need to be built out node
  by node.
- **Missing pipeline wiring.** As covered in Architecture, the `connections` object
  is missing the links from "Query Processor" into the four scrapers and from the
  scrapers into "Merge Trend Data". This is the single biggest issue with the file:
  it is not a design limitation so much as an incomplete export, and it means the
  workflow cannot produce real output until those connections are added by hand.
- **Filtering noise vs. real signal.** This one is genuinely addressed in the graph:
  the "Trend Analysis Processor" code node has real logic for it (`calculateUrgencyScore`,
  `calculateTrendMomentum`, an engagement-score check before flagging a "content gap").
  The catch is that this logic never receives live data because of the wiring gap
  above, so it is well-designed but currently unreachable in practice.
- **Schema mismatch between analysis output and Google Sheets input.** The "Content
  Calendar Updater" node's column mapping reads fields like `$json.content_calendar`,
  `$json.content_ideas`, and `$json.engagement_optimization`. None of those keys exist
  anywhere in the object "Trend Analysis Processor" actually returns (it returns
  `trending_topics`, `viral_patterns`, `community_insights`, `content_opportunities`,
  `content_gaps`, `recommended_actions`, `trend_health_score`, and similar). Every one
  of those Sheets columns would fall back to its literal default string ("Medium",
  "Blog Post", and so on) rather than real analysis data. The Slack message node, by
  contrast, correctly references the fields the analysis node actually produces
  (`trend_health_score`, `total_opportunities`, `trending_topics`,
  `recommended_actions`), so Slack would report real numbers while Sheets would not.
- **Scheduling reliability.** The trigger's sticky note claims it "triggers daily at 8
  AM," but the actual `scheduleTrigger` parameters only set an hours interval of 24,
  with no fixed hour. In practice the run time would drift to whatever time the
  workflow happened to be activated or last executed, not settle on 8 AM.
- **Stale hardcoded date.** The "Trend Configuration Processor" code node sets
  `today = new Date('2025-07-25')` and a literal `date: '2025-07-25'` field instead of
  reading the actual run date. A workflow meant to run daily would keep stamping every
  analysis with that same fixed date regardless of when it actually ran, unless someone
  edits the code node directly.

## What I learned

- Reading an n8n export's `connections` object closely, not just the node list, is
  the only way to know whether a workflow actually does what its sticky notes and
  node names claim. A workflow can look complete in the canvas (nodes positioned in a
  clear left-to-right pipeline) while having real gaps in what is wired together.
- Cross-checking a Code node's actual `return` shape against what downstream nodes
  reference (`$json.fieldName`) is a quick way to catch silent data-mapping bugs. Two
  nodes reading from the same upstream code node can be in completely different states
  of correctness, as with the Slack node versus the Google Sheets node here.
- Community nodes (like `n8n-nodes-scrapegraphai`) are a dependency the workflow file
  alone does not make obvious. Anyone importing this needs to know to install the
  package first, or the four scraper nodes just show up broken.

## What I'd do differently

- If building this kind of monitor from scratch, I would wire and test one platform
  end to end (trigger, one scraper, one merge input, analysis, Slack) before fanning
  out to four scrapers and a large multi-industry query matrix, so gaps like the
  missing connections here would surface immediately instead of only on close reading.
- I would derive the analysis date from the actual run time (`new Date()` inside the
  scheduled execution) instead of hardcoding a date string, so a daily-run workflow
  behaves like one.
- I would keep the Google Sheets column mapping and the analysis code node's return
  shape in the same file or otherwise machine-checked, so a field rename in one
  cannot silently break the other the way it has here.
- I would set an explicit trigger hour on the schedule node instead of a bare interval,
  since "every 24 hours from whenever this was last activated" is not the same
  guarantee as "runs at 8 AM."
