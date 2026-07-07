# YouTube Transcript Fetcher (n8n)

## What it is

A three-node n8n workflow that exposes a webhook, calls a third-party transcript API (Supadata) for a YouTube video, and returns the result to the caller. It is a thin HTTP wrapper: n8n does no processing of the transcript itself, it just relays the request and response.

## Why it exists

Getting a YouTube transcript programmatically normally means scraping the video page or using a paid captions API and handling auth, rate limits, and response parsing yourself. Wrapping that in an n8n webhook turns it into a single POST call any other tool (a script, a Zapier-style automation, a chatbot backend) can hit without embedding the third-party API key in that other system.

## Features

- Single POST endpoint that triggers the whole flow.
- Calls Supadata's YouTube transcript endpoint (`https://api.supadata.ai/v1/youtube/transcript`).
- Returns the API's response directly to the original caller.
- CORS is fully open (`allowedOrigins: "*"`), so it can be called from a browser.

## Architecture

Three nodes, connected in a single linear chain, no branching and no merging:

1. **Webhook** (`n8n-nodes-base.webhook`, typeVersion 2): listens on `POST /29d300e1-7502-4dae-9ebb-42bc0d08d048`. `allowedOrigins` is set to `*`. This is the trigger; it accepts the incoming HTTP request and passes it downstream.
2. **HTTP Request** (`n8n-nodes-base.httpRequest`, typeVersion 4.2): calls `GET https://api.supadata.ai/v1/youtube/transcript` (note: default method on this node is GET, no `method` parameter is set so it does not send the incoming POST body onward). It sends a query parameter `url` and a header `x-api-key` for authentication, plus `Content-Type: application/json`.
3. **Respond to Webhook** (`n8n-nodes-base.respondToWebhook`, typeVersion 1.3): sends whatever the HTTP Request node returned straight back to the original caller, with no transformation.

Connection graph: `Webhook -> HTTP Request -> Respond to Webhook`.

**Verifying the claimed purpose against the actual JSON:** the workflow does call a real YouTube transcript API and does return a transcript, so the label is accurate in spirit. But the `url` query parameter sent to Supadata is a **hardcoded literal** (`https://www.youtube.com/watch?v=3Ju1I37jWUM`), not an expression pulling the video URL from the incoming webhook payload. As saved, this workflow ignores whatever the caller POSTs and always fetches the transcript for that one specific video. It is a working proof of concept, not yet a general-purpose "give me any video's transcript" service.

## Setup

1. Import `workflow.json` into an n8n instance (self-hosted or cloud).
2. Sign up for a Supadata account and obtain an API key from their dashboard.
3. Open the HTTP Request node and replace the placeholder header value with your real Supadata API key: `x-api-key: YOUR_API_KEY_HERE`. n8n's built-in credential store (Header Auth credential type) is a better place for this than a literal value in the node, since it keeps the key out of exported JSON entirely.
4. Change the `url` query parameter on the HTTP Request node from the hardcoded example to an expression that reads the video URL from the incoming request, for example `{{ $json.body.url }}`, so the workflow actually responds to what the caller asks for.
5. Activate the workflow and note the generated webhook URL (the `path` field in the Webhook node is the route segment n8n assigns).

## Usage

Send a POST request to the workflow's webhook URL with a JSON body containing the target video URL (once step 4 above is done), for example:

```
POST https://<your-n8n-host>/webhook/29d300e1-7502-4dae-9ebb-42bc0d08d048
Content-Type: application/json

{ "url": "https://www.youtube.com/watch?v=SOME_VIDEO_ID" }
```

The response body is whatever Supadata's transcript endpoint returns, passed through unchanged.

## Challenges

1. **Hardcoded input instead of dynamic input.** As built, the query parameter sent to Supadata never reads the webhook's incoming payload, it's a fixed test video URL. This is the biggest real issue: the workflow "works" for demos but does not do what the name implies for arbitrary videos. Fix is a one-line expression change (see Setup, step 4); it is not fixed in the saved workflow.
2. **No error handling on the HTTP Request node.** If Supadata returns a 4xx or 5xx (bad video URL, no captions available, rate limit, expired key), there's no `onError` continue path, no IF node checking status, and no fallback response. The Respond to Webhook node will just relay whatever error payload (or n8n's own execution failure) comes back, with no useful message for the caller.
3. **Open CORS with no auth on the incoming side.** `allowedOrigins: "*"` on the Webhook node means anyone can call this workflow from a browser and burn through the Supadata API quota, since the workflow itself has no authentication or rate limiting on its own inbound endpoint. The API key protects the Supadata call, not the workflow's own trigger.
4. **API key stored as a literal parameter value, not a credential.** The original export had the Supadata key typed directly into the header parameter's `value` field rather than using n8n's credential system. That means every export or backup of this workflow carries the live key in plain text unless someone remembers to scrub it, which is exactly what had to happen to publish this copy.
5. **No validation of the video URL format.** There's no check that the caller supplied a well-formed YouTube URL before forwarding it to Supadata; a malformed URL just becomes a wasted (and possibly billed) API call that fails downstream.
6. **Single point of failure on a paid third party.** The whole workflow's usefulness depends entirely on Supadata's uptime and pricing. There's no fallback transcript source and no caching, so the same video queried twice costs two API calls.

## What I learned

- n8n's `httpRequest` node defaults to GET when no `method` is set, and it does not automatically forward the trigger's inbound body to an outbound call; you have to explicitly map fields with expressions like `{{ $json.body.field }}`.
- The `respondToWebhook` node just serializes whatever data object reaches it; it has no awareness of upstream HTTP status codes unless you explicitly read and set them, so API errors from a wrapped service pass through in whatever shape that service used, not a shape your own API consumers necessarily expect.
- n8n node `parameters` blocks in an exported JSON can contain literal secret values (headers, query params, body fields) even when the workflow also has a separate, legitimate `credentials` block elsewhere for other nodes. Exporting or sharing a workflow file is not safe by default; you have to check every parameter, not just the credentials section.
- A three-node linear webhook wrapper is a genuinely useful pattern for hiding a third-party API key behind your own endpoint, but only once the input is actually wired through instead of hardcoded.

## What I'd do differently

- Wire the video URL as a real expression from the incoming webhook body from the start, rather than leaving a hardcoded test value in what was treated as a "finished" workflow.
- Move the API key into n8n's credential store (Header Auth credential) immediately rather than typing it into a node parameter, so no export of this workflow could ever leak it.
- Add an IF node (or the HTTP Request node's built-in error-continue option) to branch on failure and return a clean, typed error response instead of relaying Supadata's raw error body.
- Restrict `allowedOrigins` to a known caller instead of `*`, or add a simple shared-secret header check on the Webhook node, since right now anyone who finds the URL can trigger paid API calls.
- Add basic input validation (regex or IF node) on the incoming URL before spending an API call on something that was never a valid YouTube link.
