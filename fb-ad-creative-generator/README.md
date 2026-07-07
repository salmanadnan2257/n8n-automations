# FB Ad Creative Generator

## What it is

An n8n workflow that scrapes a currently running Facebook ad from a competitor
(or any advertiser matching a keyword), downloads its creative image, and uses
GPT-4o to describe the image and rewrite the concept into rebranded "change
request" prompts for a new ad. It stops short of generating the new image
itself: the last node hands back three text prompts, not a finished creative.

## Why it exists

The node names and hardcoded values (a Drive folder informally cached as
"PPC Thievery", a search query for the keyword "automation", a brand name and
"Get your AI Automation today" style copy baked into the rewrite instructions)
point to a paid-ads research tool: pull live ad creative from Facebook's public
Ad Library for a niche, then use it as a starting point for the user's own ad
variations instead of designing from a blank page. That inference is
reasonable from the workflow itself; there is no further documentation in the
source file confirming the exact use case, so this is inferred, not confirmed.

## Features

- Pulls up to 20 currently active Facebook ads for a keyword and country from
  the public Ad Library, via a third-party Apify scraper actor.
- Filters out ads that have no usable static image (video-only or carousel ads
  without a `snapshot.images` entry are dropped).
- Caps processing to the first 2 matching ads per run to bound API usage.
- Archives the source ad images to Google Drive automatically.
- Uses GPT-4o vision to produce a detailed written description of an ad's
  layout, copy, and design.
- Uses a second GPT-4o call to turn that description into three JSON-formatted
  "change request" prompts that rebrand the ad while keeping layout and
  approximate text length unchanged.

## Architecture

Node types and data flow, in execution order:

1. **Manual Trigger** (`n8n-nodes-base.manualTrigger`, "When clicking 'Execute
   workflow'") starts the run by hand.
2. **Set** (`n8n-nodes-base.set`, "g_drive_folder_id") defines the destination
   Google Drive folder ID and the creative brief text (target brand name and
   the visual direction for the rewrite) used later in the flow.
3. **HTTP Request** (`n8n-nodes-base.httpRequest`, "scrape_fb_ads") POSTs to
   Apify's `curious_coder~facebook-ads-library-scraper` actor
   (`run-sync-get-dataset-items` endpoint), authenticated with a generic HTTP
   header credential holding the Apify API token. The request body is a
   hardcoded Facebook Ad Library search URL and asks for up to 20 results.
4. **Filter** (`n8n-nodes-base.filter`, "filter_images") keeps only items where
   `snapshot.images[0].original_image_url` exists, dropping ads with no static
   image.
5. **Limit** (`n8n-nodes-base.limit`) caps the list to the first 2 items.
6. **HTTP Request** (`n8n-nodes-base.httpRequest`, "download_static_images")
   downloads the binary image from each ad's image URL.
7. **Google Drive** (`n8n-nodes-base.googleDrive`, "upload_files") uploads the
   downloaded binary to the configured Drive folder.
8. **Google Drive** (`n8n-nodes-base.googleDrive`, "Google Drive", share
   operation) sets the uploaded file's sharing permission to "anyone with the
   link: writer" so it has a public `webContentLink` that an external API can
   fetch by URL.
9. **OpenAI** (`@n8n/n8n-nodes-langchain.openAi`, "OpenAI", resource `image`,
   operation `analyze`, model `gpt-4o`) runs vision analysis on the shared
   image URL, prompted to describe the ad "extremely comprehensively".
10. **OpenAI** (`@n8n/n8n-nodes-langchain.openAi`, "OpenAI1", chat completion,
    model `gpt-4o`) takes that description and rewrites it into three JSON
    "change request" prompts intended for an image-editing model, following
    rules that preserve asset placement, swap in the target brand name, and
    keep new copy roughly the same length as the original.

There is also a disconnected node, **Google Drive** (`n8n-nodes-base.googleDrive`,
"create_folder", resource `folder`), which creates a "PPC Thievery" folder in
Drive's root. It has no incoming or outgoing connections in the saved graph,
so it does not run as part of the main flow; it looks like a one-time manual
setup step (matching a sticky note near it titled "Create G Drive Folder")
rather than dead weight, but that is inferred from position and naming, not
confirmed by the workflow itself.

The workflow's final output is three text prompts describing changes to make
to the ad. There is no image generation or editing node in this workflow, so
turning those prompts into an actual finished image is a manual step outside
what is built here.

## Setup

1. In n8n: **Workflows** menu > **Import from File**, select `workflow.json`.
2. Create and attach the following credentials (see `CREDENTIALS.md`):
   - An HTTP Header Auth credential holding an Apify API token, attached to
     the "scrape_fb_ads" node.
   - A Google Drive OAuth2 credential, attached to the "upload_files",
     "Google Drive" (share), and "create_folder" nodes.
   - An OpenAI API credential, attached to both OpenAI nodes.
3. Edit the "g_drive_folder_id" Set node:
   - Replace `YOUR_GDRIVE_FOLDER_ID_HERE` with a real Drive folder ID you have
     write access to (both occurrences, including the `cachedResultUrl`).
   - Replace the placeholder brand name and creative-direction text with your
     own, since the original hardcodes a specific rebrand instruction.
4. Optionally run the disconnected "create_folder" node once by hand if you
   want the workflow to create its own destination folder rather than reusing
   an existing one.
5. Edit the Facebook Ad Library search URL inside "scrape_fb_ads" if you want
   a different keyword or country than the one baked in.

## Usage

Click the manual trigger to run the workflow end to end. It scrapes matching
ads, keeps the first two with a usable static image, uploads and publicly
shares those images on Drive, has GPT-4o describe each one, and outputs three
rebranded "change request" prompts per image. Those prompts still need to be
fed into an image generation or editing tool by hand to produce the actual new
ad creative; this workflow does not do that step.

## Challenges

- **Facebook Ad Library scraping reliability.** Scraping Facebook directly is
  fragile and against its terms, so the workflow offloads that to a
  third-party Apify actor (`curious_coder~facebook-ads-library-scraper`)
  instead of an in-house scraper. It does not address what happens if that
  actor's output schema changes or Facebook blocks it: the HTTP Request node
  has no retry or continue-on-fail configured, so a failure there stops the
  run.
- **Not every scraped ad has a usable image.** Video ads, carousel ads, and
  ads with no `snapshot.images` entry would break a naive download step. This
  is handled directly: the "filter_images" node checks that
  `snapshot.images[0].original_image_url` exists before anything downstream
  runs.
- **Image download failures.** Dead links, ads pulled by the advertiser
  mid-run, or unexpected content types could break the download step. This is
  not handled: "download_static_images" has no retry, no continue-on-fail, and
  no content-type check, so one bad URL fails that item.
- **Overly broad file sharing.** The "Google Drive" share node sets every
  uploaded file to "anyone with the link: writer", not "reader". That's more
  permissive than needed just to let OpenAI's vision endpoint fetch the image
  by URL, and it is not scoped down anywhere in the workflow.
- **LLM output format.** The second OpenAI node is instructed by prompt text
  alone to return strict JSON (`{"variants": [...]}`), with no output parser
  or schema validation node in the graph. A model response that includes
  extra prose or malformed JSON would break anything expecting clean JSON
  downstream, and nothing here would catch that.
- **No final image generation step.** The workflow produces three text change
  requests but never calls an image generation or editing model to actually
  produce the new ad. It stops one step short of a finished creative; the last
  mile is manual work outside the workflow.

## What I learned

- Apify's hosted actors are a practical way to get scrape data into n8n
  without building or maintaining a scraper: a generic HTTP Header Auth
  credential plus a POST to the actor's `run-sync-get-dataset-items` endpoint
  is enough, no dedicated Apify node is needed.
- n8n's Google Drive node's `webContentLink` generally needs the file shared
  publicly before an external API like OpenAI's vision endpoint can fetch it
  by URL, since that API has no way to authenticate against Drive's OAuth
  scope. That is why the share step exists between upload and analysis.
- The langchain OpenAI node's `image` resource ("analyze") and its chat
  resource are separate operations that have to be chained as two nodes: the
  vision description comes back as plain text, and needs to be handed to a
  second chat-style node manually rather than getting rewritten in one step.
- Enforcing structured JSON output through prompt wording alone, with no
  parser node, is fragile and depends entirely on the model following
  instructions correctly every run.

## What I'd do differently

- Add retry and continue-on-fail handling on the Apify HTTP Request node and
  the image download node so one bad ad or one flaky scrape doesn't stop the
  whole run.
- Scope the Drive share permission down to reader instead of writer, or avoid
  public sharing altogether by passing image bytes directly to the vision
  step instead of relying on a public link.
- Add a structured output parser node after the second OpenAI call instead of
  trusting prompt-only JSON formatting.
- Wire in an actual image generation node so the workflow produces a finished
  rebranded image, not just three candidate text prompts that still need
  manual follow-through.
- Either reconnect the orphaned "create_folder" node into the main flow or
  remove it, so it's clear whether it's a deliberate one-time setup step or
  leftover from an earlier version.
- Parameterize the search keyword, country, and brand name (for example
  through a form trigger) instead of hardcoding them in the Set node, so the
  workflow can be reused across niches without editing the JSON each time.
