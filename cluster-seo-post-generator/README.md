# Cluster SEO Post Generator

## What it is

An n8n workflow that turns one row of a keyword-cluster spreadsheet into a published
WordPress blog post. It runs on a weekly schedule, pulls the next unfinished keyword
cluster from a Google Sheet, researches the topic, drafts a post with a chain of LLM
calls, adds internal links to older posts, finds a cover image, and publishes the
result as a WordPress draft.

The workflow's filename on disk was
`SEO___Blog_Post___Keyword_Clusters___Template_UPDATED_SKOOL.json`. The "SKOOL" suffix
indicates this started life as a template shared in a Skool community (a paid-community
platform popular with n8n course creators), not as an original design. It was adapted
and run in production from there, but the underlying structure, prompt chain, and
sheet-driven pattern are not original to this build.

## Why it exists

Manually researching a keyword, writing a 2000+ word SEO post, adding internal links,
and publishing to WordPress takes an hour or more per post. This workflow was run
against a real content calendar (a Google Sheet of pillar-post keyword clusters) to
produce a batch of posts without that manual work, one post per scheduled run.

## Features

- Pulls the next incomplete keyword cluster from a Google Sheet (filtered on a
  "Completed" column) so the same sheet can drive many runs over time.
- Two-stage planning: a cheap model sketches a preliminary content plan, then a
  stronger reasoning model expands it into a detailed section-by-section plan once
  research is folded in.
- Perplexity-backed research step with citation numbers rewritten into inline source
  links so the copywriting step can cite real sources.
- Internal linking pass that reads previously published posts from a second sheet and
  inserts at least five contextual links into the new post.
- Converts the finished post into styled WordPress-ready HTML (custom inline CSS for
  fonts, colors, headings) in one LLM call.
- Auto-generates slug, title, and meta description as separate focused LLM calls
  instead of one call doing everything.
- Pulls a cover image from Google Images via SerpAPI keyed on the post title.
- Publishes as a WordPress draft (not live) and logs the finished post back to the
  keyword sheet and marks the source row "Completed".

## Architecture

Trigger: `Schedule Trigger` (cron `2 1 * * 2`, weekly).

1. `Grab New Cluster` (Google Sheets) reads the next row where `Completed = No` from
   the keyword-cluster sheet.
2. `Preliminary Plan` (OpenAI node, model `o1-mini` via OpenRouter) sketches a rough
   content outline from the keywords and search intent.
3. `Research` (HTTP Request to `api.perplexity.ai/chat/completions`, model
   `sonar-pro`) researches the primary keyword and returns cited findings.
4. `Fix Links` (Set node) rewrites Perplexity's bracketed citation markers (`[1]`,
   `[2]`, ...) into inline "- source: <url>" text using the citations array.
5. `Create plan` (OpenAI node, `o1-preview`) expands the preliminary plan into a
   detailed, keyword-annotated section plan using the research.
6. `Write Blog` (OpenAI node, `claude-3.5-sonnet` via OpenRouter) writes the full post
   from the detailed plan and research.
7. `Previous Posts` (Google Sheets) reads all previously completed posts from a
   separate "Completed Keywords" sheet; `Aggregate` collapses them into one item.
8. `Add internal links` (OpenAI node, `o1-mini`) reads the new post plus the list of
   old posts and inserts at least five relevant internal links.
9. `HTML version` (OpenAI node, `o1-preview`) reformats the linked post into WordPress
   HTML with inline styling, per a strict prompt spec and worked example.
10. `Slug`, `Title`, `Meta description` (three separate OpenAI `gpt-4o` calls) each
    derive one SEO field from the linked post.
11. `Image Covers` (HTTP Request to SerpAPI, `google_images` engine) searches for a
    cover image using the generated title.
12. `Edit Fields` (Set) picks one image URL from the results.
13. `Wordpress` node creates the post as a draft with the generated title, slug, HTML
    body (image tag plus formatted content), category, and tag.
14. `Check as completed on Sheets` and `Google Sheets` update the source row to
    `Completed = Yes` and append the finished post's title, keywords, summary, and URL
    to the "Completed Keywords" log sheet.

Two OpenAI credential entries are wired into different nodes in this same workflow
(`OpenRouter` for some calls, a separate `OpenAI - Kia` credential for others), which
reflects how it was actually run rather than a single clean provider choice.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- Google Sheets OAuth2 account, with access to a keyword-cluster sheet (columns:
  Keywords, Intent, Primary Keyword, Completed) and a separate completed-posts log
  sheet.
- An OpenAI-compatible credential for the chained LLM calls. The original used both an
  OpenRouter API key (for `o1-mini`/`claude-3.5-sonnet` calls routed through
  OpenRouter) and a direct OpenAI API key (for other `o1`/`gpt-4o` calls). One
  provider that supports all the referenced model IDs works if you consolidate them.
- Perplexity API key (HTTP header auth) for the research step.
- SerpAPI key (HTTP query auth) for the Google Images cover-image search.
- WordPress REST API credential (username/application password) for the target site.

Before running, replace the two Google Sheet IDs (keyword-cluster sheet and completed-
posts log sheet), the WordPress category/tag IDs, and the placeholder `YourURL` in the
completed-posts log append step with your own site's domain.

## Usage

Enable the schedule trigger, or run manually via n8n's "Execute Workflow" for a single
test post. Each run consumes exactly one row from the keyword sheet and produces one
WordPress draft; review the draft before publishing it live, since nothing in the
chain checks factual accuracy.

## Challenges

- **Citation format mismatch.** Perplexity returns numbered citation markers (`[1]`,
  `[2]`, ...) in the prose plus a separate `citations` array of URLs. The `Fix Links`
  node handles this with ten chained `.replaceAll()` calls, one per citation index.
  It's fragile (a paper with 11+ sources silently loses the correction on source 11)
  but was good enough for the volume this ran at.
- **Multi-provider LLM sprawl.** The workflow calls the same "OpenAI" node type but
  wires two different credentials (an OpenRouter key and a direct OpenAI key) across
  different steps, presumably because some models were only available through one
  provider at the time. It works, but it means the workflow can't be run start to
  finish with a single API key without editing several nodes.
- **No factual verification step.** The research node returns whatever Perplexity's
  sonar-pro model finds; nothing downstream checks the research or the final post
  against it beyond "did the writer include the citations." SEO content generated this
  way needs a human editorial pass before it goes live, which this workflow does not
  attempt to replace (it publishes as a draft, not live, for exactly this reason).
- **Internal linking depends on sheet growth.** The internal-linking step reads the
  *entire* history of completed posts on every run via `aggregateAllItemData`. That's
  fine at the volume it was built for, but it does not paginate or cap the input, so a
  sheet with hundreds of rows would eventually push a very large prompt into the
  "Add internal links" call.
- **Model choices are hardcoded per node.** Model IDs like `o1-preview` and
  `gpt-4o-2024-11-20` are typed directly into node parameters rather than centralized,
  so a model deprecation means editing each node individually rather than one setting.

## What I learned

Splitting a long-form generation task into narrow single-purpose LLM calls (plan,
research, detailed plan, draft, internal links, HTML, slug, title, meta description)
produces more controllable output than one mega-prompt, at the cost of more nodes and
more places for a schema mismatch to break the chain. Passing structured
citation/source data through a text-based LLM pipeline is genuinely awkward: text
replacement on numbered markers is the kind of thing that looks fine in testing and
breaks quietly at scale.

## What I'd do differently

I'd consolidate the two LLM credentials into one provider so the workflow is portable
with a single API key, add a real editorial/fact-check gate before WordPress
publishing rather than relying on "draft status" as the only safety net, and replace
the citation-marker string replacement with a proper JSON-based citation mapping so it
scales past ten sources. I'd also paginate the internal-linking history read instead
of aggregating the full sheet on every run.
