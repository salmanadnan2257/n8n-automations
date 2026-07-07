# Website Screenshot Utility

## What it is

A small n8n workflow that takes a hardcoded website URL, requests a screenshot of it
from the ScreenshotOne API, and sends the resulting image to a Telegram chat.

## Why it exists

A minimal utility/demo build: given how often "take a screenshot of a URL and send it
somewhere" comes up as a building block inside larger workflows, this exists as a
standalone, three-node example of that pattern rather than a full product.

## Features

- Takes a screenshot of any website via ScreenshotOne, with ad-blocking, cookie-banner
  blocking, and tracker-blocking options set on the request.
- Delivers the screenshot straight to a Telegram chat as a photo message.
- No scheduling or external input handling: it is a manual, single-URL demo rather
  than a batch or on-demand service.

## Architecture

Trigger: `When clicking 'Execute workflow'` (Manual Trigger).

1. `Edit Fields` (Set node) hardcodes the target URL into a `url` field. As shipped
   this is a placeholder URL; change it to whatever site you want a screenshot of.
2. `HTTP Request` calls `api.screenshotone.com/take` with the URL as a query
   parameter, plus options for image format (JPG), ad/cookie-banner/tracker blocking,
   a render delay, timeout, and image quality.
3. `Send a photo message` (Telegram node, `sendPhoto` operation, `binaryData: true`)
   sends the HTTP response's binary image data to a fixed Telegram chat.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- A ScreenshotOne API account and access key. This workflow authenticates by putting
  the access key directly in the request URL's query string (ScreenshotOne's
  documented auth method) rather than through an n8n credential type, so you'll need
  to paste your own key into the `HTTP Request` node's URL in place of the
  `YOUR_API_KEY_HERE` placeholders.
- A Telegram Bot API credential, plus the numeric chat ID to send screenshots to
  (replace the `YOUR_TELEGRAM_CHAT_ID` placeholder in the Telegram node).

## Usage

Set the target URL in `Edit Fields`, then run the workflow manually. The screenshot
arrives in the configured Telegram chat within a few seconds, depending on
ScreenshotOne's render delay setting.

## Challenges

- **API key embedded directly in the request URL.** ScreenshotOne's documented
  authentication is a query-string parameter, so the key has to live in the node's
  URL field rather than in n8n's separate credential store; that makes the key easy to
  accidentally leave in an exported/shared copy of the workflow. The copy in this
  repository has the key replaced with a placeholder for exactly this reason.
- **Hardcoded single URL.** The target URL is a literal string in a Set node, so this
  can't take a URL as input from a form, webhook, or list without editing the
  workflow; it's a single-shot demo, not a service you'd call repeatedly with
  different targets.
- **No error handling for failed screenshots.** If ScreenshotOne can't render the page
  (blocked by the target site, timeout, invalid URL) the HTTP Request node just
  fails; nothing in the graph catches that and reports it back through Telegram or
  anywhere else.
- **Fixed destination chat.** The Telegram chat ID is hardcoded rather than parameterized,
  so sending a screenshot to a different chat means editing the node directly.

## What I learned

Even a three-node "screenshot and send" workflow surfaces the same authentication
tradeoff seen in larger workflows in this collection: some third-party APIs (like
ScreenshotOne here) put their auth key in the URL rather than supporting an n8n
first-class credential type, which means the key ends up living in node parameters
where it's exported in plain text with the workflow JSON, unlike properly credentialed
nodes where n8n keeps secrets out of the exported file entirely.

## What I'd do differently

I'd wrap the ScreenshotOne call so the access key comes from an n8n credential (using
generic HTTP query auth, the same pattern this collection's SEO workflows use for
SerpAPI) instead of a literal URL parameter, add a form or webhook trigger so the
target URL is an input rather than a hardcoded value, and add basic error handling so
a failed screenshot produces a Telegram error message instead of silently failing.
