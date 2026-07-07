# Real Estate Market Update Poster

## What it is

An n8n workflow that watches a Google Sheet for a new real-estate-related topic,
pulls a matching news article, has an LLM turn that article into a social media
post plus an image prompt and a video prompt, generates an image from that prompt,
animates the image into a short video, and writes the finished post text, image
URL, and video URL back into the same Google Sheet row.

## Why it exists

Writing a market-update social post by hand means reading an article, distilling
it into something people will actually stop and read, then separately briefing a
designer (or a prompt) for a matching image and a short video cut. This workflow
automates that whole chain from "here's a topic" to "here's a post, an image, and
a video clip," so the only manual step left is dropping a topic into a spreadsheet
row and marking it "In Progress."

## Features

- Google Sheets acts as the queue: adding a topic and marking it "In Progress"
  triggers the run.
- Pulls real news articles for the topic via the newsdata.io search API.
- Scrapes the full article text from the article's own URL rather than relying on
  the short search snippet.
- Three chained LLM calls (Google Gemini) turn the article into a social post, an
  image prompt, and a video-motion prompt, each with a tightly scoped system
  prompt so the model returns only the raw text needed for the next step.
- Generates a still image from the image prompt via Runware's image inference API.
- Animates that still image into a short video via Novita AI's image-to-video
  (Wan) API, with an async poll loop that waits for the render to finish.
- Writes the finished post text, image URL, video URL, and a "Done" status back
  into the source spreadsheet row.

## Architecture

Trigger and setup:

1. **latest_topic** (`n8n-nodes-base.googleSheetsTrigger`): polls a Google Sheet
   every minute, watching the "Topic" column for changes.
2. **Filter** (`n8n-nodes-base.filter`): only lets a row through if its
   "Progress" column equals `In Progress`. This is a manual gate: someone has to
   set that value on the row for the workflow to act on it.
3. **get_articles** (`n8n-nodes-base.httpRequest`): `GET
   https://newsdata.io/api/1/latest` with `q=<Topic>`, authenticated via a
   generic query-auth credential. Single request, no pagination.
4. **Edit Fields** (`n8n-nodes-base.set`): carries the Topic forward and grabs the
   `results` array from the news API response.
5. **Split Out** (`n8n-nodes-base.splitOut`): splits `results` into one item per
   article.
6. **scrape_articles** (`n8n-nodes-base.httpRequest`): fetches the full text of
   each article's own link as plain text (`responseFormat: text`), with
   `onError: continueErrorOutput` so a failed scrape doesn't stop the run.
7. **store_article_data** (`n8n-nodes-base.set`, `executeOnce: true`): assembles
   Topic, title, link, description, and content into one item for the LLM chain.

Content generation (three sequential single-purpose LLM agents, each backed by
its own `@n8n/n8n-nodes-langchain.lmChatGoogleGemini` node running
`gemini-2.0-flash-lite`):

8. **Generate Post** (`@n8n/n8n-nodes-langchain.agent`): system prompt casts the
   model as a "Content Alchemist" that reads the full article and writes one
   scroll-stopping social post (hook, value nugget, implication, call to read),
   explicitly banned from clickbait words and from outputting anything but the
   post text itself.
9. **Generate Image Prompt** (`@n8n/n8n-nodes-langchain.agent`): reads the
   generated post and writes a single structured image prompt (subject, style,
   composition, lighting, color palette), ending with a hard negative constraint
   against rendering any text in the image.
10. **Generate Video Prompt** (`@n8n/n8n-nodes-langchain.agent`): reads the post
    and the image prompt and writes a motion prompt on top of the same visual
    (subject animation, camera movement, environmental motion, pacing), again
    ending with a no-text constraint.
11. **Post + Visuals** (`n8n-nodes-base.set`): collects `post`, `image_prompt`,
    and `video_prompt` into one item.

Image and video generation (the part with the most moving pieces):

12. **Generate Image** (`n8n-nodes-base.httpRequest`, `POST
    https://api.runware.ai/v1`): sends an `imageInference` task (512x512, one
    result, JPEG, output type URL, model `runware:100@1`) with the image prompt
    as `positivePrompt`. Runware credential is a generic header-auth key. The
    JSON does not say what underlying model `runware:100@1` actually maps to on
    Runware's side; treat it as opaque.
13. **Image-to-Video - POST** (`n8n-nodes-base.httpRequest`, `POST
    https://api.novita.ai/v3/async/wan-i2v`): submits an async image-to-video job
    (1280x720) using the generated image's URL and the video prompt as input.
    "wan-i2v" points to Novita's hosted Wan image-to-video model. This call
    returns a `task_id` and does not return a finished video.
14. **Wait** (`n8n-nodes-base.wait`): pauses before checking the async job. The
    node has no explicit duration configured in the JSON, so it runs on
    n8n's default wait behavior; the workflow does not set its own backoff.
15. **Image-to-Video - GET** (`n8n-nodes-base.httpRequest`, `GET
    https://api.novita.ai/v3/async/task-result?task_id=...`): polls the job
    status.
16. **If** (`n8n-nodes-base.if`): checks whether the task status contains
    `TASK_STATUS_SUCCEED`. True goes to **Final**. False loops back to **Wait**,
    forming a poll loop. There is no separate branch for a failed or errored
    task status and no iteration cap, so a stuck or failed job on Novita's side
    loops indefinitely rather than surfacing an error.
17. **Final** (`n8n-nodes-base.set`): pulls `post` from Post + Visuals, `img_url`
    from the Runware response, and `video_url` from the completed Novita
    response (`videos[0].video_url`).

Write-back:

18. **Google Sheets** (`n8n-nodes-base.googleSheets`, update operation): matches
    the row by Topic and writes Article Heading, Description, Link, Content,
    post_content, img_url, video_url, and sets Progress to `Done`.

## Setup

1. In n8n: Workflows menu > Import from File, select `workflow.json`.
2. Create and attach credentials for each node that needs one (see
   `CREDENTIALS.md` for the full list):
   - Google Sheets OAuth2 (used by both the trigger and the write-back node)
   - newsdata.io API key (query auth)
   - Google Gemini API key (used by all three LLM chat model nodes)
   - Runware.ai API key (header auth)
   - Novita.ai API key (header auth, used by both the POST and GET nodes)
3. Point the Google Sheets trigger and the Google Sheets write-back node at your
   own spreadsheet. The sheet needs at minimum: Topic, Progress, Article Heading,
   Description, Link, Content, post_content, img_url, video_url columns.
4. Leave the workflow inactive until credentials and the sheet are confirmed
   working; the JSON ships with `"active": false`.

## Usage

1. Add a row to the tracking sheet with a Topic (e.g. "mortgage rates") and set
   Progress to `In Progress`.
2. The trigger picks up the change on its next minute-poll and the workflow runs
   the full chain: fetch article, scrape it, generate post/image
   prompt/video prompt, generate image, animate it into video, poll until the
   video render finishes, write everything back to the row with Progress set to
   `Done`.
3. Read the finished post text and grab the image/video URLs from the sheet for
   posting.

## Challenges

- **Unbounded poll loop on video generation.** The If node only checks for
  `TASK_STATUS_SUCCEED`; if Novita ever returns a failed or errored status, the
  false branch sends execution straight back to Wait with no cap on retries and
  no branch that surfaces a failure. A stuck async job would spin the workflow
  indefinitely instead of failing loudly.
- **No configured backoff on the poll wait.** The Wait node has no duration set
  in the JSON, so however long it actually pauses is whatever n8n defaults to,
  not a value tuned to how long an image-to-video render realistically takes.
  Too short a wait means extra, wasted GET calls against Novita's API while the
  job is still processing.
- **Hardcoded content field.** In `store_article_data`, four of the five fields
  (CSV Topic, title, link, description) are proper n8n expressions pulling from
  upstream nodes, but the `content` field is a plain hardcoded string containing
  one specific sample article about virtual data rooms, not an expression
  referencing `scrape_articles`' output. As exported, every run would store that
  same canned article text regardless of which article was actually scraped.
  This looks like leftover pinned test data that never got converted back to an
  expression, and it would need fixing before the workflow could work correctly
  end to end.
- **Scrape failures aren't isolated.** `scrape_articles` uses
  `onError: continueErrorOutput`, so a failed page scrape doesn't stop the run,
  but the error output isn't wired to anything different from the success path
  downstream. An article whose page fails to load would still flow into
  `store_article_data` with a missing or empty body, and from there into the LLM
  chain with nothing meaningful for it to summarize.
- **No pagination on the news search.** `get_articles` makes a single call to
  newsdata.io's `/latest` endpoint. If the query returns more articles than fit
  in that one page, the rest are silently dropped, there's no follow-up request
  or cursor handling.
- **Three sequential LLM calls with no validation between them.** Generate Post,
  Generate Image Prompt, and Generate Video Prompt each depend entirely on the
  previous node's raw text output and on the model actually following the "only
  output the prompt" instruction. Nothing in the graph checks that the outputs
  are non-empty or well-formed before they're spent on paid image and video
  generation calls further down the chain.

## What I learned

- Async external jobs (image-to-video here) need a real state machine in n8n,
  not just an If-and-loop-back pair. Without a status branch for failure and a
  max-attempt counter, a poll loop like this one has no way to stop itself
  short of the workflow being manually cancelled.
- Chaining several single-purpose LLM agent calls (post writer, then image
  prompt writer reading the post, then video prompt writer reading both) is an
  effective way to keep each system prompt narrow and each output predictable,
  but it does mean paid model calls stack linearly and a bad output early in the
  chain (e.g. the model ignoring the "output only the text" rule) propagates
  into every prompt after it with nothing catching it.
- Using `executeOnce: true` on a Set node like `store_article_data` is meant to
  pin the node to run against a single item context, but it does not protect
  against a field being hardcoded by accident instead of wired as an
  expression, which is exactly what happened to the `content` field here.

## What I'd do differently

- Add a real terminal condition to the video-generation poll loop: branch on a
  failed/errored task status explicitly, and cap the number of poll attempts so
  a stuck render fails the workflow instead of looping forever.
- Set an explicit wait duration on the Wait node based on Novita's actual
  typical render time, instead of leaving it at whatever n8n's default is.
- Fix the `content` field in `store_article_data` to actually reference the
  scraped article output instead of a hardcoded sample string, and add a check
  after `scrape_articles` that skips or flags articles whose scrape failed or
  came back empty, rather than letting them flow into the LLM chain unchanged.
- Add a lightweight validation step after each LLM agent (length check, or a
  rejection of empty output) before spending the paid image and video
  generation calls on whatever the model returned.
