# Trend SEO Post Generator

## What it is

An n8n workflow that writes a WordPress blog post about the week's most trending AI
news topic. On a weekly schedule it pulls trending Google search queries in the AI
space, picks the best topic for SEO purposes with an LLM, researches it, writes the
post, adds internal links, and publishes the result as a WordPress draft.

The workflow's filename on disk was
`SEO___Blog_Post___Trends___Template_SKOOL.json`. The "SKOOL" suffix indicates this
started as a template shared in a Skool community (a paid-community platform), not as
an original design. It was adapted and run in production from there.

## Why it exists

Keeping a blog's SEO content aligned with what's currently trending in a niche (here,
AI) is a recurring, time-consuming task if done by hand every week: check what's
trending, pick something relevant, research it, write it, link it, publish it. This
workflow automates that weekly cycle end to end, bar a manual review of the draft.

## Features

- Pulls Google Trends "rising" related queries for a fixed topic via SerpAPI, keeps
  the top two trending queries.
- Also pulls Google Trends "top" queries and filters them down to a comma-separated
  list of high-search-volume keywords (search volume > 30) with a small Code node, to
  optionally weave into the post.
- Uses an LLM (`deepseek-r1`) to choose the single best of the two trending queries for
  SEO relevance to the target site, rather than always taking the single most-trending
  one.
- Perplexity-backed research on the chosen topic, with citation markers rewritten into
  inline source links.
- Writes the post in a reporter-style, curiosity-driven tone distinct from the more
  formal tone used in the cluster-post variant of this system.
- Internal linking pass against a shared "Completed Keywords" log of previously
  published posts.
- Generates slug, title, and meta description as separate LLM calls.
- Converts the post into styled WordPress HTML and publishes as a draft with a
  SerpAPI-sourced cover image.
- Logs the finished post's title, topic, summary, and URL back to the shared
  completed-posts sheet.

## Architecture

Trigger: `Schedule Trigger` (cron `0 8 * * 4`, weekly on Thursday).

1. `Trends` (HTTP Request to `serpapi.com`, `google_trends` engine,
   `data_type=RELATED_QUERIES`) fetches trending queries for a placeholder search term
   (`[YOUR QUERY]` in the raw template, meant to be replaced with your niche).
2. `2 Most Trending` (Set, raw JSON mode) extracts the top two "rising" queries and
   their growth scores into a small structured object.
3. `High search volume keywords` (Code node) filters the "top" queries list down to
   ones with `extracted_value > 30` and joins them into a comma-separated string, for
   optional use in the post body.
4. `Choosing Topic` (OpenAI node, `deepseek-r1` via OpenRouter) picks whichever of the
   two trending queries is the better SEO fit, considering both relevance and growth.
5. `Research` (HTTP Request to `api.perplexity.ai/chat/completions`, `sonar-pro`)
   researches the chosen topic.
6. `Fix Links` (Set node) rewrites Perplexity's citation markers into inline source
   text, same pattern as the cluster-post variant.
7. `Copywriter` (OpenAI node, `claude-3.5-sonnet`) writes a 1500-2000 word post in a
   reporter tone, weaving in the optional high-volume keywords where natural.
8. `Previous Posts` (Google Sheets, shared "Completed Keywords" sheet) plus
   `Aggregate` collapse prior posts into one item for the linking step.
9. `Add internal links` (OpenAI node, `o1-mini`) inserts at least five internal links
   from the previous-posts list into the new draft.
10. `HTML version` (OpenAI node, `o1-preview`) reformats into styled WordPress HTML.
11. `Slug`, `Title`, `Meta description` (three separate `gpt-4o` calls) derive the SEO
    fields from the linked post.
12. `Image Covers` (HTTP Request to SerpAPI, `google_images`) finds a cover image
    keyed on the chosen topic; `Edit Fields` picks one URL.
13. `Wordpress` node publishes the post as a draft.
14. `Google Sheets` appends the finished post's title, topic, summary, and URL to the
    shared completed-posts log.

This workflow shares the "Completed Keywords" log sheet and the same internal-linking
and HTML-formatting prompt patterns with the cluster-post variant
(`cluster-seo-post-generator`), suggesting both were built from the same base template
and adapted for two different post-sourcing strategies (a fixed keyword calendar
versus live trend-chasing).

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- SerpAPI key (HTTP query auth), used for both the Google Trends lookup and the
  Google Images cover-image search.
- An OpenAI-compatible credential (the original split calls across an OpenRouter key
  and a direct OpenAI key; one provider covering all referenced model IDs works if
  consolidated) for topic selection, research-link cleanup, writing, internal
  linking, HTML formatting, slug, title, and meta description.
- Perplexity API key (HTTP header auth) for the research step.
- Google Sheets OAuth2 account with access to the shared completed-posts log sheet.
- WordPress REST API credential for the target site.

Before running, replace the `[YOUR QUERY]` placeholder in the `Trends` node with your
actual niche/seed query, and replace the completed-posts sheet ID, WordPress
category/tag IDs, and the placeholder `YourURL.com` in the log-append step with your
own values.

## Usage

Enable the schedule trigger for a weekly cadence, or run manually to test. Each run
produces one WordPress draft on whichever of the two current trending queries the
topic-selection LLM judges more relevant; review before publishing live.

## Challenges

- **Trending-topic selection is a single LLM judgment call with only two options.**
  The workflow only compares the top two "rising" queries, so if neither is genuinely
  relevant to the target niche, the workflow still forces a choice between them rather
  than skipping the week. There's no fallback path for "nothing trending is relevant."
- **Same citation-marker fragility as the cluster-post variant.** The `Fix Links` node
  chains ten `.replaceAll()` calls for citation markers `[1]` through `[10]`; an
  eleventh source silently loses its inline link.
- **Hardcoded placeholder query.** The `Trends` node ships with a literal
  `[YOUR QUERY]` string that must be manually edited before the workflow does anything
  useful; there's no parameter or sheet-driven input for the seed topic, unlike the
  cluster-post variant's sheet-driven keyword source.
- **No dedupe against very recent trend cycles.** Because trend queries can repeat
  week to week (a topic can stay "rising" for consecutive weeks), nothing in this
  workflow checks the completed-posts log before choosing a topic, so it's possible to
  write near-duplicate posts on the same trend two weeks running.
- **No factual verification.** As with the cluster-post variant, the research and
  writing steps are not checked against source accuracy before publishing; the draft
  status on the WordPress post is the only safety net.

## What I learned

Trend-driven content generation needs a rejection path, not just a selection path: an
LLM asked to "pick the best of these two options" will always pick one, even when
neither is actually good, so real trend-chasing workflows need an explicit "skip this
week" branch that a forced-choice prompt doesn't provide. I also confirmed the
citation-rewriting approach shared with the cluster-post workflow has the same
scaling ceiling here.

## What I'd do differently

I'd add a relevance threshold so the workflow can skip publishing when neither
trending query is a good fit, replace the `[YOUR QUERY]` hardcoded seed term with a
sheet-driven or parameter-driven input like the cluster-post variant already has, and
add a check against the completed-posts log to avoid repeating a topic. I'd also fix
the citation-marker replacement the same way I would in the cluster-post variant.
