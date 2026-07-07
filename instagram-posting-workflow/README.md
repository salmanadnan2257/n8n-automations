# Instagram Posting Workflow

## What it is

A small, manually-triggered n8n workflow that posts a single image and caption to
Instagram using the Facebook Graph API's two-step publish flow: create a media
container with an image URL and caption, then publish that container by id.

As exported, the image URL and caption are hardcoded demo values, not parameters
pulled from any input. The image is a specific Unsplash stock photo URL, and the
caption is literally the text "Hello from n8n! 👋 This is an automated post. #n8n
#automation #instagram". This workflow, run as-is, only ever posts that one fixed
demo image with that one fixed caption; nothing changes between runs unless someone
edits the Set node by hand.

## Why it exists

It demonstrates the minimum viable shape of posting to Instagram through the
Graph API from n8n: the "create container, then publish container" two-call
pattern that the API requires. As a demo, it's a reference for exactly what that
two-step call sequence looks like, not a ready-to-run posting tool.

## Features

- Manual trigger, no scheduling.
- Sets an image URL, caption text, and Instagram node id as static values.
- Creates a media container via the Graph API's `media` edge.
- Publishes the container via the `media_publish` edge, using the container id
  returned by the first call.

## Architecture

Node-by-node, in execution order:

1. **When clicking 'Execute workflow'** (`manualTrigger`): starts the workflow.
2. **Set Image & Caption** (`set`): assigns three static string fields:
   `imageUrl` (an Unsplash stock photo URL), `captionText` ("Hello from n8n!" plus
   hashtags), and `Node` (the Instagram Business Account id used in the API calls,
   scrubbed to a placeholder in this copy).
3. **Creating Container ID** (`facebookGraphApi`, POST, `media` edge, Graph API
   v22.0): sends `image_url` and `caption` as query parameters to create a media
   container, returning a container id.
4. **Facebook Graph API1** (`facebookGraphApi`, POST, `media_publish` edge): sends
   the container's `creation_id` (from step 3's response) along with the same
   image URL and caption, to publish the post.

A sticky note in the original export points to a YouTube setup walkthrough
(`https://www.youtube.com/watch?v=PXcDqmamX2Q`), suggesting this was built by
following a tutorial rather than from scratch.

## Setup

Import via n8n's Workflows menu > Import from File, pointing at `workflow.json`.

Credentials needed after import (see `CREDENTIALS.md`): a Facebook Graph API
credential with Instagram publishing permissions, tied to a Facebook app with
Instagram Graph API access. You also need your own Instagram Business Account id in
place of the `YOUR_INSTAGRAM_BUSINESS_ACCOUNT_ID` placeholder in the "Set Image &
Caption" node.

## Usage

Click "Execute workflow" in the n8n editor. It will attempt to post the hardcoded
Unsplash image with the hardcoded caption to whatever Instagram account the
configured id and credential point at. To post anything else, edit the "Set Image &
Caption" node's values directly, or replace that node with one that reads from a
real input source (a form, a spreadsheet row, a webhook payload).

## Challenges

- **Nothing here is actually dynamic.** There's no input mechanism at all: no form
  trigger, no webhook, no spreadsheet read. The image and caption are baked into a
  Set node. Anyone wanting to post different content needs to hand-edit that node
  before every run, which defeats the point of "automating" a post.
- **No error handling on either Graph API call.** If container creation fails (bad
  image URL, expired token, rate limit), the second node has nothing to catch that
  and just fails the whole execution with no retry, no fallback, and no notification.
- **No verification that publishing actually succeeded.** The workflow ends right
  after the `media_publish` call; there's no follow-up call to check the post
  actually went live, and no node that surfaces the API's response to a human.
- **Instagram Business Account id was hardcoded in the export.** The original file
  had a real numeric account id embedded directly in the Set node's parameters,
  which I've replaced with a placeholder here. That's a config value that identifies
  a specific real Instagram account and shouldn't ship in a public repo.
- **No rate-limit or duplicate-post protection.** Running this workflow twice in a
  row posts the identical image and caption twice, with nothing checking whether
  that content was already posted.

## What I learned

The Graph API's container-then-publish pattern is a genuinely two-step commit: the
first call only stages the media, and nothing is actually posted until the second
call references that container's id. Seeing it broken into two explicit n8n nodes
made that separation clearer than reading the API docs alone.

## What I'd do differently

I'd replace the hardcoded Set node with a real input source (at minimum, a Google
Sheets read so different posts can queue up), add a status-check call after
publishing to confirm the post went live, and add basic error handling so a failed
container creation doesn't just die silently.
