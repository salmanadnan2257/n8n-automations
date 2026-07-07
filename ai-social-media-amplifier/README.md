# AI Social Media Amplifier

## What it is

A scheduled n8n workflow that crawls the Hacker News front page every 6 hours, finds posts linking to GitHub repositories, skips any it has already handled, visits each repo page, has an LLM write a Twitter post and a LinkedIn post about it, pings the owner on Telegram, waits 5 minutes, then posts to X and LinkedIn and logs status in Airtable.

## Why it exists

Manually scanning Hacker News for interesting open-source projects and writing social copy about each one is repetitive. This workflow automates the discovery-to-publish pipeline: find candidate projects, generate on-brand posts, give the owner a heads-up and a short window to notice something is about to go out, then publish and record what was posted so the same project doesn't get re-posted later.

## Features

- Runs on a schedule (every 6 hours), no manual trigger needed.
- Crawls the Hacker News front page and extracts only submissions that link to a GitHub repo, along with title, score, author, age, and comment count.
- Deduplicates against an Airtable table of already-posted items before doing any further work.
- Visits each candidate repo's GitHub page and converts it to markdown for the LLM's context.
- Generates a Twitter post and a LinkedIn post in one LLM call, in a specific tone (avoids emojis and buzzwords, keeps Twitter under 280 characters, makes LinkedIn more detailed).
- Validates and parses the model's JSON output before proceeding.
- Logs every generated post to Airtable and pings the workflow owner on Telegram with the drafted copy before it goes out.
- Waits 5 minutes after the Telegram ping (a manual-override window) before actually posting to X and LinkedIn.
- Updates Airtable status flags (`TDone`, `LDone`) once each platform's post succeeds.

## Architecture

Trigger and crawl:

1. **Schedule Trigger** (`n8n-nodes-base.scheduleTrigger`, every 6 hours) starts the run.
2. **Crawl HN Home** (`n8n-nodes-base.httpRequest`) fetches `https://news.ycombinator.com/` with `fullResponse` and `neverError` enabled so a bad response doesn't kill the run.
3. **Extract Meta** (`n8n-nodes-base.code`, Python/Pyodide) installs `beautifulsoup4` and `simplejson` at runtime, parses the HTML, and pulls out every submission whose link contains `github.com`, producing a record per post with `Post` (HN item ID), `title`, `url`, `site`, `score`, `author`, `age`, `comments`, and `hn_url`.

Dedup:

4. **Search Item** (`n8n-nodes-base.airtable`, search) queries the "My Tweets" table in the "Twitter Agent" Airtable base for a row matching each `Post` ID already extracted.
5. **Merge** (`n8n-nodes-base.merge`) combines the Airtable search results with the freshly extracted items.
6. **Filter Unposted Items** (`n8n-nodes-base.code`) builds a set of `Post` IDs that already have an Airtable `id` (meaning they were found in the table) and keeps only the newly extracted items whose `Post` is not in that set, i.e. only genuinely new posts continue.

Generate content:

7. **Visit GH Page** (`n8n-nodes-base.httpRequest`) fetches the actual GitHub repo page for each surviving item.
8. **Convert HTML To Markdown** (`n8n-nodes-base.markdown`) turns the fetched HTML into markdown text for the prompt.
9. **Generate Content** (`@n8n/n8n-nodes-langchain.openAi`, model `gpt-4o-mini`, `jsonOutput: true`) is given a system prompt defining tone and constraints, and a user prompt with the title, markdown details, and repo URL. It's asked to return JSON with `twitter` and `linkedin` fields.
10. **Validate Generate Content** (`n8n-nodes-base.code`, run once per item, `onError: continueRegularOutput`) checks whether `message.content.twitter`/`.linkedin` are already present as parsed fields; if not, it attempts `JSON.parse` on `message.content` as a fallback, and returns an empty object with a console log if that also fails to produce both fields.
11. **Filter Errored** (`n8n-nodes-base.filter`) passes through only items where `$json.error` is empty, screening out items that failed the previous validation step.

Record and notify:

12. **Create Item** (`n8n-nodes-base.airtable`, create) writes a new row to "My Tweets" with the URL, HN post ID, title, generated tweet, and generated LinkedIn text.
13. **Ping Me** (`n8n-nodes-base.telegram`) sends the drafted tweet and LinkedIn post to the owner's Telegram chat as a preview.
14. **Wait for 5 mins before posting** (`n8n-nodes-base.wait`, 5-minute unit) pauses before publishing, giving a manual window to notice and intervene (there is no cancel/skip mechanism wired in, just a delay).

Publish and record status:

15. **X** (`n8n-nodes-base.twitter`, `onError: continueRegularOutput`) posts the generated tweet text.
16. **LinkedIn** (`n8n-nodes-base.linkedIn`) posts the generated LinkedIn text under a configured person URN.
17. **Update X Status** / **Update L Status** (`n8n-nodes-base.airtable`, update) set `TDone`/`LDone` boolean flags on the Airtable row created in step 12, keyed by the row's Airtable `id`.
18. **No Operation, do nothing** (`n8n-nodes-base.noOp`) is the terminal node both status updates flow into.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create/attach credentials for:
   - **Airtable** (Personal Access Token) on the "Search Item", "Create Item", "Update X Status", and "Update L Status" nodes, pointed at a base with a table matching the "My Tweets" schema (`Post`, `Title`, `Url`, `Tweet`, `LinkedIn`, `Date`, `TDone`, `LDone` fields). The base ID `app7fh2kmMzPKS4RZ` and table ID `tblf0cODJFdvDj7vU` in this export point at the original owner's Airtable base and will need to be repointed at your own base and table.
   - **OpenAI API** on the "Generate Content" node.
   - **Telegram Bot API** on the "Ping Me" node, and replace the `YOUR_TELEGRAM_CHAT_ID` placeholder with your own chat ID.
   - **X (Twitter) API** on the "X" node.
   - **LinkedIn API** on the "LinkedIn" node, and replace the `YOUR_LINKEDIN_PERSON_URN` placeholder with your own LinkedIn person URN.
3. The "Extract Meta" code node runs Python via n8n's Pyodide-based code node and installs `beautifulsoup4` and `simplejson` at execution time; this requires the n8n instance's code node to support Python execution.
4. Activate the workflow so the schedule trigger runs every 6 hours.

## Usage

Once active, the workflow runs unattended every 6 hours. Any newly generated post triggers a Telegram preview message; after 5 minutes it posts automatically to X and LinkedIn unless something outside this workflow intervenes (there's no pause/cancel step built in, the wait is a fixed delay only).

## Challenges

- **The "review window" has no actual review mechanism.** The Telegram ping and 5-minute wait look like an approval gate, but there is no node that listens for a reply or cancellation. If the drafted copy is wrong, the only way to stop it is to manually deactivate or stop the running execution in n8n before the wait elapses.
- **Dedup depends on Airtable search matching exactly.** "Filter Unposted Items" only works correctly if "Search Item" reliably returns a match for every already-posted `Post` ID; the Airtable filter formula `={Post}= {{ $json.Post }}` uses `=` without normalizing types, so a subtle type or whitespace mismatch between the code node's `Post` value and Airtable's stored value could cause a repost.
- **JSON parsing of the LLM's output has a shaky fallback.** "Validate Generate Content" checks for `.twitter`/`.linkedin` on `message.content` first, and only falls back to `JSON.parse(message.content)` if those aren't already present as object fields. Since "Generate Content" already sets `jsonOutput: true`, it's not fully clear from this export which shape `message.content` actually arrives in at runtime, string or parsed object, which is exactly the kind of ambiguity this fallback exists to paper over.
- **Two independent httpRequest crawls with no shared rate limiting.** "Crawl HN Home" and "Visit GH Page" are plain HTTP requests with no delay or backoff configured; running this on a schedule against GitHub repo pages at scale risks getting rate-limited or blocked, and there's nothing in the graph that would catch or retry that gracefully beyond the generic `neverError` flag on the HN crawl (which "Visit GH Page" doesn't share).
- **Both posting nodes have `continueRegularOutput`/no error branch and no partial-failure recovery.** If "X" fails (bad credential, API downtime) but "LinkedIn" succeeds, "Update X Status" simply won't be reached correctly for that item since the two publish nodes fan out from the same Wait node independently; there's no unified failure handling that would still record what did and didn't post.
- **Hardcoded Telegram chat ID.** Like the checklist generator, "Ping Me" sends to a fixed chat ID rather than deriving it from any dynamic source, so this only works as a single-operator personal automation, not a multi-user tool.

## What I learned

This is the most complete pipeline of the four workflows reviewed: crawl, dedupe, generate, notify, delay, publish, record status, each stage with a clear single-responsibility node. The dedup pattern (search Airtable by ID, merge with fresh data, filter out anything that already has an Airtable `id`) is a clean way to avoid reprocessing without needing a separate database. The "ping the owner and wait before publishing" pattern is a reasonable manual safety net in concept, but only actually functions as a safety net if a human is watching the clock and manually stops the execution, since there is no listen-for-approval node in this export.

## What I'd do differently

I would replace the fixed 5-minute wait with an actual approval step, for example a Telegram node that waits for a reply (n8n supports "wait for webhook/response" patterns) so a thumbs-down actually halts the post instead of just a ticking clock. I would also unify the X and LinkedIn status updates behind a single node that records partial success/failure per platform, instead of two independent branches that can silently diverge if one platform's post fails and the other's doesn't.
