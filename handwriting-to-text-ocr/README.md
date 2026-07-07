# Handwriting to Text OCR

## What it is

A small n8n webhook service that accepts a base64-encoded image (typically a photo of
handwriting), asks Google Gemini to transcribe the handwriting into plain text, and
returns the transcription as a JSON response.

## Why it exists

A minimal, single-purpose OCR-style API endpoint: send an image, get back text. Built
as a standalone building block rather than a full application, useful anywhere an
upstream system (a form, a mobile app, another workflow) needs handwriting-to-text
without standing up a dedicated OCR service.

## Features

- Webhook-triggered, synchronous request/response (the caller gets the transcription
  back in the same HTTP response, via `responseMode: responseNode`).
- Accepts an image as a base64 data URL string in the request body.
- Uses Google Gemini's image-analysis capability (`gemini-2.5-flash`) with a prompt
  strictly constrained to return only the transcribed text, no markdown, no commentary.
- Returns a clean JSON object (`{ "text": "..." }`) rather than raw model output.

## Architecture

Trigger: `Webhook` (POST, `responseMode: responseNode`, meaning the response is sent
explicitly by a later node rather than immediately on receipt).

1. `Webhook` receives a POST request. The expected body shape is
   `{ "url": "data:image/...;base64,<data>" }`, a data-URL-style base64 image string.
2. `Edit Fields` (Set node) extracts just the base64 payload by splitting the incoming
   `body.url` string on the comma and taking the second half (dropping the
   `data:image/...;base64,` prefix).
3. `Convert to File` (`n8n-nodes-base.convertToFile`, operation `toBinary`) turns that
   base64 string into actual binary image data n8n can pass to the next node.
4. `Analyze image` (`@n8n/n8n-nodes-langchain.googleGemini`, resource `image`,
   operation `analyze`, model `gemini-2.5-flash`) receives the binary image with a
   prompt instructing it to act as a handwriting-to-text converter and return only the
   transcribed text.
5. `Respond to Webhook` builds the JSON response by reading
   `$json.content.parts[0].text` (Gemini's response structure) and returning it as
   `{ "text": "<transcription>" }`, using `JSON.stringify` to safely escape the text
   for the response body.

## Setup

In n8n: Workflows menu > Import from File, select `workflow.json`.

External accounts and credentials needed:
- Google Gemini (PaLM API) credential, for the image-analysis node.

Since this is a webhook-triggered workflow, it must be active in n8n (or run via the
test webhook URL during development) to accept requests; note the production webhook
path/URL n8n assigns after activation.

## Usage

POST a JSON body like `{"url": "data:image/png;base64,<your base64 image data>"}` to
the workflow's webhook URL. The response is `{"text": "<transcribed handwriting>"}`.

## Challenges

- **No input validation.** The `Edit Fields` node assumes `body.url` is always a
  well-formed data URL containing a comma-separated base64 payload; a malformed
  request (missing field, non-data-URL string, or an already-bare base64 string with
  no comma) would produce a broken or empty split result with no validation error
  telling the caller what went wrong.
- **No file-type or size checks.** Nothing in the graph checks that the uploaded data
  is actually an image, or caps its size before sending it to Gemini; a very large
  payload or a non-image file would be sent straight to the model.
- **Single fixed prompt, no language or format options.** The transcription prompt is
  a hardcoded string; there's no way to pass a language hint, request structured
  output (e.g., line-by-line), or handle multi-page input without editing the workflow
  itself.
- **No error path back to the caller.** If Gemini fails to parse the image (blank
  image, non-handwriting content, safety filter trigger), the `Respond to Webhook`
  node still tries to read `$json.content.parts[0].text`, which would throw rather
  than return a clean error response to the caller.

## What I learned

A synchronous webhook-in, webhook-out OCR pattern is simple to build in n8n once you
account for the base64 handling step: incoming JSON payloads carry images as data-URL
strings, and n8n's binary data model needs an explicit `Convert to File` step before
an image-analysis node can use it as an actual image rather than a text string.

## What I'd do differently

I'd add input validation on the incoming request (confirm `body.url` exists and is a
data URL before attempting the split), wrap the Gemini call in error handling that
returns a proper error JSON response instead of throwing on unexpected model output,
and add a basic size/type check before forwarding the image to the model.
