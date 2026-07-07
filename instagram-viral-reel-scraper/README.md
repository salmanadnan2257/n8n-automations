# Instagram Viral Reel Scraper

## Status note

This workflow was recovered from a JSON backup file, not from a live n8n instance. No workflow with a matching name or id was found in the current n8n instance when this project was assembled. It could not be confirmed as live or in production. Treat it as a draft or a superseded build until proven otherwise. The workflow's own `active` flag in the JSON is also set to `false`.

## What it is

An n8n workflow triggered by a web form. A user submits one or more Instagram usernames and a target reel count, the workflow calls an HTTP endpoint (intended to be a third-party Instagram scraping API, though the exact endpoint is not saved in this file), converts each reel's video to audio, transcribes the audio with OpenAI Whisper, feeds the transcript plus engagement numbers into an AI agent for content strategy suggestions, and appends the results to two separate Google Sheets.

That is the intended design based on the node graph and connections. Several nodes are missing configuration (detailed below), so as saved this workflow could not run end to end without additional setup.

## Why it exists

The stated goal is to save a content creator or agency the manual work of pulling reel performance stats, watching/transcribing videos by hand, and writing up what worked or didn't. Instead: submit a username, get back an AI-written breakdown of what to change next time.

## Features

- Web form intake for one or more Instagram usernames and a reel count, using n8n's Form Trigger node.
- An HTTP call meant to pass the username list and result limit to a scraping backend as JSON.
- Video-to-audio conversion via CloudConvert's synchronous jobs API (mp4 to mp3).
- Audio transcription via OpenAI's Whisper endpoint (n8n's LangChain OpenAI node, audio/transcribe operation).
- An AI Agent node (LangChain agent, backed by a `gpt-4o-mini` chat model) that takes views, likes, comments, transcript, and caption and returns a content strategy critique.
- Two Google Sheets append operations for logging results at two different points in the pipeline.

## Architecture

Node types, in execution order per the connections graph:

1. **On form submission1** (`n8n-nodes-base.formTrigger`) : collects two fields, "Instagram Usernames" and "How many reels would you like scraped" (a number field).
2. **HTTP Request** (`n8n-nodes-base.httpRequest`) : POST with a JSON body of `resultsLimit` and `username` built from the form fields. This node has no `url` parameter saved in the JSON at all, so the actual scraping service (Apify, RapidAPI, or something else) cannot be identified from this file. This is the node that is supposed to do the actual Instagram scraping; as saved, it is not configured with a destination.
3. **HTTP Request4** (`n8n-nodes-base.httpRequest`) : POST to `https://sync.api.cloudconvert.com/v2/jobs`, with a job definition that imports a file from `{{ $json.videoUrl }}`, converts it from mp4 to mp3, and exports the result by URL. The Authorization header is present but has an empty "Bearer " value, so the real CloudConvert API key is not stored in this file.
4. **OpenAI** (`@n8n/n8n-nodes-langchain.openAi`) : resource `audio`, operation `transcribe`. Takes the converted audio and returns a transcription (Whisper).
5. **Google Sheets2** (`n8n-nodes-base.googleSheets`) : operation `append`. Both `documentId` and `sheetName` are saved as empty strings, so this node is not pointed at any real spreadsheet in this file.
6. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`) : a defined prompt that reads `$json.Views`, `$json.Likes`, `$json.Comments`, `$json.Transcript`, and `$json.Caption`, and asks the model to act as a content strategist and suggest improvements. It has no tool nodes wired into it (no `ai_tool` connections in the graph), so despite being an "agent" node it behaves as a single prompt-and-respond call, not a multi-step tool-using agent.
7. **OpenAI Chat Model** (`@n8n/n8n-nodes-langchain.lmChatOpenAi`) : model `gpt-4o-mini`, connected to AI Agent via the `ai_languageModel` link. This is the language model backing the agent, not a separate pipeline step.
8. **Google Sheets1** (`n8n-nodes-base.googleSheets`) : operation `append`, final step. Same as Google Sheets2, `documentId` and `sheetName` are saved empty.

Full connection chain: On form submission1 -> HTTP Request -> HTTP Request4 -> OpenAI -> Google Sheets2 -> AI Agent -> Google Sheets1, with OpenAI Chat Model feeding the AI Agent as its language model.

There is no Set/Edit Fields node, no IF/Switch node, no loop or batching node (like Split In Batches), and no error-handling branch anywhere in the graph. Every field the AI Agent prompt expects (Views, Likes, Comments, Transcript, Caption) is assumed to just pass through the earlier nodes unchanged.

## Setup

To actually run this workflow, you would need to:

1. Import `workflow.json` into an n8n instance.
2. Configure the first HTTP Request node with the real scraping API endpoint, auth, and request format your chosen scraper expects. This file does not contain that endpoint.
3. Add a real CloudConvert API key to the Authorization header on HTTP Request4.
4. Attach a real OpenAI credential (the credential pointer in this file, "Open AI Arete Key", refers to a credential stored in someone's n8n instance; it is not a usable key here).
5. Point both Google Sheets nodes at real spreadsheet IDs and sheet/tab names, and set up a Google Sheets OAuth2 credential.
6. Verify the scraping API's response actually contains fields named `Views`, `Likes`, `Comments`, `Caption`, and `videoUrl` (or add a Set/Edit Fields node to rename them), since the AI Agent prompt and the CloudConvert job body reference those exact keys.

## Usage

Once configured, a user opens the form, enters an Instagram username (or usernames) and how many reels to scrape, and submits. The workflow is expected to scrape reel stats, convert and transcribe each reel's audio, run the AI agent's analysis, and append rows to the two configured sheets. As delivered in this JSON, none of the external endpoints or sheet targets are wired up, so this is a description of the intended flow, not a verified end-to-end run.

## Challenges

1. **The core scraping call has no URL.** The first HTTP Request node builds a JSON body (`resultsLimit`, `username`) but has no `url` field saved anywhere in its parameters. Without that endpoint, this workflow cannot scrape anything, and there is no way to tell from this file which scraping provider it was built against.
2. **Field pass-through through a transcription node is fragile.** The AI Agent prompt reads `$json.Views`, `$json.Likes`, `$json.Comments`, `$json.Caption` after the data has already gone through an audio conversion call and an OpenAI transcription call. n8n's OpenAI transcribe operation typically returns a transcription result, which can replace rather than merge with the incoming item's other fields depending on version and options. If that happens, the original stats and caption would be gone by the time the AI Agent runs, and the prompt would show blank values. There is no Merge node in the graph to recombine the original item metadata with the transcript.
3. **Both Google Sheets nodes are unconfigured.** `documentId` and `sheetName` are saved as empty strings on both Google Sheets1 and Google Sheets2, and neither node has explicit column mappings. As saved, both append calls would fail immediately since there's no spreadsheet to write to.
4. **No batching or per-item error handling for multiple reels.** The form lets a user request more than one reel per username, but there is no Split In Batches node, no rate limiting, and no IF/error branch anywhere. If one reel's video URL is bad, or the scraper returns an empty or partial result, there's nothing in the graph to catch that; it would just error the whole execution or silently pass bad data forward.
5. **The AI Agent has no tools.** It is built as a LangChain "agent" node, which suggests multi-step tool use, but only a chat model is attached (via `ai_languageModel`). No `ai_tool` connections exist. Functionally this node behaves like a plain prompt completion, not an agent that can look anything up or take further action.
6. **CloudConvert's synchronous jobs endpoint has real limits.** `sync.api.cloudconvert.com` is meant for quick, small jobs and can time out or reject larger video files; there is no fallback to the async jobs API or a retry step if a conversion job fails or exceeds sync limits.

## What I learned

- n8n's item-based execution model means multi-item flows (multiple reels here) don't need an explicit loop node to run per item, but that also means there's no natural point to add batching, delays, or per-item error handling unless you deliberately add one (like Split In Batches or an IF node).
- The LangChain "agent" node type in n8n is not automatically an agent with tool access; it needs explicit `ai_tool` connections. Without them it is a single LLM call with a system-style prompt, wired the same way a Basic LLM node would be, just under the Agent node type.
- OpenAI's audio transcription node operation is a distinct resource/operation pair (`resource: audio`, `operation: transcribe`) from the chat completion nodes, and its output shape needs to be checked explicitly if later nodes depend on fields from before the transcription step.
- Google Sheets append nodes in n8n store the target document and sheet as resource-locator objects (`__rl`, `mode`, `value`) that can be saved blank without n8n complaining until the node actually runs, so an exported workflow JSON can look complete while being unusable.

## What I'd do differently

- I would not ship the first HTTP Request node without a saved URL. Even a placeholder like `https://YOUR-SCRAPER-ENDPOINT/run` would make it obvious in the JSON what service this was built for, instead of leaving a silent gap.
- I would add a Set/Edit Fields node right after the scrape and right after the transcription step to explicitly map and preserve Views, Likes, Comments, Caption, and Transcript, instead of hoping they survive passthrough.
- I would replace the single unconfigured Google Sheets append at the end with one clearly-named, fully configured sheet, and drop the mid-pipeline Google Sheets2 append unless there's a real reason to log twice; as built it just adds a second point of failure with no visible purpose.
- I would add at least one IF node or error branch around the scrape and conversion calls, since both depend on an external service that can return empty results, rate-limit, or fail outright.
- I would attach real tools to the AI Agent node (a search tool, or a sheet-read tool for historical comparison) if the intent was genuinely to have it act as an agent, or rename it to reflect that it's a single-prompt analysis step if not.
