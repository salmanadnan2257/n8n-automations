# AI Workout Generator

## What it is

An n8n workflow that takes a fitness profile submitted through a webhook, generates a personalized one-week workout plan with an LLM, and emails the plan back to the requester.

## Why it exists

Writing a workout plan by hand for every new client or lead takes time and follows a repeatable pattern: collect a profile (goals, fitness level, equipment, limitations), turn it into a structured 7-day schedule, deliver it. This workflow automates the generation and delivery so a form submission produces a ready-to-use plan without a human writing it out.

## Features

- Single webhook endpoint that accepts a fitness profile and an email address in the POST body.
- LLM-generated 7-day workout schedule constrained by a strict system prompt (no filler text, no markdown, exercise name/sets/reps/rest only).
- Automatic email delivery of the finished plan to the address supplied in the request.

## Architecture

Three nodes, linear flow:

1. **Webhook** (`n8n-nodes-base.webhook`, POST) receives the request. It expects a JSON body with a `program` field (the profile summary text) and an `email_address` field.
2. **AI Agent** (`@n8n/n8n-nodes-langchain.agent`) receives `{{ $json.body.program }}` as its prompt input. It is wired to a **Google Gemini Chat Model** node (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`) as its language model. The agent's system message is a long, strict instruction set: output only the raw plan text, start with "Day 1:", no markdown, no headings, no explanatory sections, and the plan must respect any stated health limitations and available equipment.
3. **Send email** (`n8n-nodes-base.emailSend`, SMTP) sends the agent's `output` field to `{{ $('Webhook').item.json.body.email_address }}` as a plain text email.

There is no validation node between the webhook and the agent: whatever the caller sends in `program` goes straight into the LLM prompt, and whatever the caller sends in `email_address` is used as the send-to address with no format check.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create/attach credentials for:
   - **Google Gemini API** (Google PaLM/Gemini credential type in n8n) on the "Google Gemini Chat Model" node.
   - **SMTP** credential on the "Send email" node, and set a real "From" address in place of the `YOUR_SENDER_EMAIL@example.com` placeholder.
3. Activate the workflow to expose the webhook, or run it manually with a test payload while building.
4. POST a JSON body like `{"program": "<profile summary text>", "email_address": "someone@example.com"}` to the webhook URL n8n assigns.

## Usage

Send a POST request to the webhook with the client's profile summary as free text in `program` and the address to deliver the plan to in `email_address`. The workflow returns no synchronous response body to the caller; the plan arrives by email once the LLM call and send complete.

## Challenges

- **No output format enforcement beyond prompting.** The agent's only guarantee that the output is "just the plan" is the system prompt. There is no code node that strips stray markdown or leading commentary if the model does not comply exactly, so a model drift or edge case can leak formatting into the email.
- **No input validation on the webhook body.** `program` and `email_address` are read directly with no check that either field exists or that `email_address` looks like an email. A malformed request would either error deep in the SMTP node or silently email the wrong address if it happens to look valid.
- **No safety review of health limitations.** The prompt tells the model to respect stated health limitations, but nothing in the graph checks that the model actually did, there's no second pass or rule-based filter on generated exercises, so correctness depends entirely on the LLM.
- **Single point of failure for delivery.** If the SMTP send fails (bad credential, provider throttling), the whole run fails with no retry node and no fallback notification to the requester or the workflow owner.
- **Synchronous webhook with no immediate response.** Because email generation and delivery happen after the webhook trigger with no explicit "respond to webhook" step tailored to the caller, whoever calls this webhook has no way to know from the HTTP response whether the plan actually got emailed.

## What I learned

Reading this graph made clear how much of an "AI agent" node's reliability rests on prompt engineering alone when there's no downstream node to check its output. A three-node workflow like this is fast to build and demo, but the lack of any validation, retry, or confirmation step means it is a proof of concept rather than something to run unattended for real users without more scaffolding.

## What I'd do differently

I would add a Set or Code node right after the webhook to validate `email_address` format and reject/short-circuit malformed input before it reaches the LLM call, add a "Respond to Webhook" node so the caller gets an explicit success/failure acknowledgment instead of relying on the email arriving, and put a retry (or at least an error-branch notification) around the SMTP send so a delivery failure doesn't just vanish.
