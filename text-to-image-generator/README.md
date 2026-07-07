## What it is

An n8n workflow that takes a job-application form submission, renders a personalized "welcome card" image from a design template, and emails that image link to the applicant.

The workflow's internal name is "Text -> Image," which suggests AI text-to-image generation (a prompt going into something like DALL-E or Stable Diffusion). That is not what it does. There is no AI image model anywhere in this graph. It fills a single text layer on a fixed, pre-designed template using the Templated.io API (a template-rendering service, not a generative model) and emails the result. The README title in this repository reflects the folder name it was archived under, not the workflow's actual behavior; that gap is called out explicitly here and in the Challenges section below.

## Why it exists

To automate the "someone applied to join the team" moment: capture a name and email through a form, generate a branded welcome graphic with that name on it, and send it out, without anyone manually opening a design tool per applicant.

## Features

- Public web form trigger with two required fields (Full Name, Email).
- Automatic rendering of a preset "Welcome Team" template with the submitter's name burned into a text layer.
- Automatic email delivery of the welcome message with a link to the rendered image.
- A second, disabled email node left in the graph as an unused variant (see Challenges).

## Architecture

Four nodes, three active, one disabled:

1. **On form submission** (`n8n-nodes-base.formTrigger`, typeVersion 2.2): renders a public form titled "Join our team!" with two required fields, Full Name and Email. This is the workflow's only trigger.
2. **Templated** (`n8n-nodes-templated.templated`, typeVersion 1): calls the Templated.io API to render template id `7165f24b-b71e-45b8-8842-a18bbcd69f43` (cached name "Welcome Team"). It sets one layer, `your-name`, with `text` bound to the form's `Full Name` field via an expression: `{{ $('On form submission').item.json['Full Name'] }}`. It also sets `color`, `background`, and `border_color` on that layer. The node's output includes a `render_url` field pointing at the rendered image.
3. **Send Email** (`n8n-nodes-base.emailSend`, typeVersion 2.1): sends a plain-text SMTP email to a fixed recipient with the subject "Welcome to the Team," body text pulling the Full Name from the trigger and the `render_url` from the Templated node.
4. **Send Email1** (`n8n-nodes-base.emailSend`, typeVersion 2.1, `disabled: true`): a second email node wired after "Send Email," using `operation: sendAndWait` (n8n's human-in-the-loop pause, normally used for approval steps) with the same subject and a near-identical message. It is disabled, so it never runs; it sits in the connections graph as a dead end.

Data flow: form submission -> Templated (renders image, produces render_url) -> Send Email (delivers render_url by email) -> Send Email1 (wired but disabled, never executes).

There is no branching, no merge node, and no error-handling path. Every node has exactly one outgoing connection.

## Setup

1. Import `workflow.json` into an n8n instance (Import from File, or paste into the workflow editor).
2. Create a Templated.io API credential in n8n and attach it to the "Templated" node. You need a Templated.io account with a template matching the layer name `your-name` (or edit the layer name/template id to match your own template).
3. Create an SMTP credential in n8n and attach it to the "Send Email" node (and "Send Email1" if you ever enable it).
4. Replace the placeholder values in `fromEmail` and `toEmail` on both email nodes with real addresses. As shipped in this repository those fields are scrubbed placeholders (`YOUR_SENDER_EMAIL_HERE` / `YOUR_RECIPIENT_EMAIL_HERE`); the original workflow hardcoded one fixed recipient, which only worked because it was a personal single-recipient setup, not a real multi-applicant pipeline (see Challenges).
5. Activate the workflow and note the form's webhook path from the "On form submission" node to get your public form URL.

## Usage

Open the form URL, submit a Full Name and Email, and the workflow renders the template with that name and emails a link to the result. The email always goes to whatever address is hardcoded in `toEmail` on the "Send Email" node. It does not use the Email field the form actually collects.

## Challenges

- **The workflow's name doesn't match its function.** It's called "Text -> Image" but there's no generative AI model in it. It's a parametric template fill: one string goes into one fixed text layer. Anyone maintaining this needs to know Templated.io is a design-template renderer, not an image generation model, or they'll assume it can take arbitrary prompts. It can't; changing the visual output means editing the template in Templated.io, not the workflow.
- **The collected Email field is never used.** The form asks for and requires an email address, but "Send Email" sends to a hardcoded `toEmail`, not to `{{ $('On form submission').item.json['Email'] }}`. As built, this only worked as a single-operator notification tool ("tell me when someone applied"), not as a way to email the actual applicant. That's a real bug if the intent was ever to notify the applicant.
- **No wait or check for render completion.** The workflow reads `render_url` straight off the Templated node's output and emails it immediately, with no verification that the rendered image actually exists at that URL yet. If the rendering service needs any processing time after the API call returns, this graph has no polling loop, wait node, or retry to account for that, so the email could go out with a link that isn't ready.
- **A dead, half-configured node sits in the graph.** "Send Email1" duplicates "Send Email" almost exactly but uses `sendAndWait`, an operation meant to pause a workflow until someone responds (used for approval steps), not for a one-way welcome notice. It's disabled, so it's harmless today, but it's wired into the connections graph as if it were live, which is confusing for anyone reading this workflow expecting every connected node to run.
- **No error handling anywhere.** If the Templated API call fails (bad credential, deleted template, rate limit) or the SMTP send fails, the workflow just fails. There's no IF node, no error trigger, no retry, no fallback email path.
- **Form has no email format validation.** "Email" is marked required but n8n's form trigger doesn't validate email syntax, and since the field isn't even used downstream, a malformed address the user typed just gets silently discarded (see the unused-field issue above).

## What I learned

- n8n's community node `n8n-nodes-templated.templated` calls Templated.io's template-rendering API by template id and per-layer overrides (text, color, background, border color); it is a positional/parametric fill, not a prompt-driven generator, and the distinction matters for anyone reading a workflow by name alone.
- n8n expressions like `$('Node Name').item.json['Field']` pull a specific upstream node's output by name regardless of direct connection order, which is how "Templated" reached back to the trigger node's `Full Name` field and how "Send Email" reached the "Templated" node's `render_url`, two hops upstream.
- The `emailSend` node's `sendAndWait` operation is a distinct approval/pause mechanism, not a normal send; using it correctly requires the workflow to actually stop and wait on a response, which this graph's disabled second node never does.
- `disabled: true` nodes still appear in the `connections` graph in the exported JSON; disabling a node doesn't remove its wiring, it just skips it at execution time, so reading connections alone can overstate what actually runs.

## What I'd do differently

- Rename the workflow to reflect what it does (personalized welcome-card renderer and mailer), not what it sounds like it might do.
- Wire the applicant's actual submitted email into "Send Email" instead of a hardcoded address, or make the hardcoded recipient an explicit, documented design choice (internal notification only) rather than leaving it looking like a bug.
- Delete "Send Email1" entirely rather than leaving a disabled, half-wired duplicate in the graph. If a real approval step is needed, build it properly with `sendAndWait` and an actual reviewer, don't leave a broken echo of the main send node.
- Add a check or wait step after "Templated" to confirm the render actually finished before emailing a link to it, rather than assuming `render_url` is immediately valid.
- Add at least one error path: catch a failed Templated call or failed SMTP send and do something visible (log it, alert a human), instead of letting the whole execution just die.
