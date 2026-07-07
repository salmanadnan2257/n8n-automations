## What it is

A small n8n workflow that, on a manual click, downloads one specific image from
Google Drive and posts it to LinkedIn twice: once as a personal profile post and
once as a company page post. Five nodes total, no branching logic, no error
handling beyond n8n's defaults.

## Why it exists

LinkedIn's native posting flow (open the app, attach an image, type the same
caption twice for a personal account and a company page) is repetitive when the
same announcement needs to go out from both. This workflow removes the manual
"upload and retype" step for that specific pattern: one image, one caption,
two destinations.

## Features

- One click (manual trigger) fetches a named file from Google Drive and posts it
  to both a personal LinkedIn profile and a LinkedIn company page in the same run.
- Uses n8n's native Google Drive and LinkedIn nodes, so authentication is handled
  by n8n's credential store rather than by API keys embedded in the workflow.
- The two LinkedIn posts run in parallel from the same downloaded file, so there
  is no duplicate download.

## Architecture

Five nodes, four of them functional (the fifth is a sticky note with setup
instructions):

1. `When clicking 'Execute workflow'` (`n8n-nodes-base.manualTrigger`): the only
   trigger. Nothing else can start this workflow; there is no schedule, webhook,
   or file-watch trigger.
2. `Download file` (`n8n-nodes-base.googleDrive`, operation `download`): pulls a
   single hardcoded file by Drive file ID (cached display name `1.mainsq.jpg`)
   and attaches it to the item as binary data.
3. `Create a personal post` (`n8n-nodes-base.linkedIn`): reads the binary data
   from `Download file` and posts it to the account owner's personal LinkedIn
   profile, with `shareMediaCategory` set to `IMAGE` and a fixed caption.
4. `Create a company post` (`n8n-nodes-base.linkedIn`, same node type, `postAs`
   set to `organization`): same binary input, same fixed caption, posted to a
   LinkedIn company page instead of the personal profile.

Data flow: `Download file`'s single output connects to both LinkedIn nodes at
once (fan-out, not a loop or a Merge node). Both LinkedIn nodes are terminal;
nothing reads their output, so there is no confirmation step, no logging node,
and no reconciliation if one post succeeds and the other fails.

## Setup

1. In n8n, add credentials for:
   - Google Drive OAuth2 (used by `Download file`)
   - LinkedIn OAuth2 (used by both `Create a personal post` and
     `Create a company post`; the exported workflow points both nodes at the
     same credential entry, so the connected LinkedIn app needs both personal
     posting scope and company-page admin access on that one account)
2. Import `workflow.json` into n8n.
3. Reassign both credential slots to your own Google Drive and LinkedIn
   connections (the IDs in the file are pointers into someone else's n8n
   instance and will not resolve in yours).
4. In `Download file`, replace the hardcoded file ID with the file you actually
   want to post, using the file picker (the `list` mode resource locator).
5. In both LinkedIn nodes, replace the hardcoded caption text with your own.

## Usage

Open the workflow in n8n and click "Execute workflow." The run downloads the
configured file and immediately fires both LinkedIn posts. There is no preview
step and no confirmation prompt: clicking the trigger publishes to both
LinkedIn destinations right away.

## Challenges

- **Fixed caption text.** Both LinkedIn nodes have the exact same string typed
  into the `text` parameter (`"Testing Linkedin is Easy with n8n "`, with a
  trailing space). There is no variable, no expression, and no upstream node
  that produces the caption dynamically. As shipped, this workflow can only
  ever post that one sentence; every run is identical content. Not addressed:
  making it useful for more than one post would require adding an input node
  (form trigger, Set node, or similar) upstream of both LinkedIn nodes.

- **No shared caption source.** Even if the caption were made dynamic, it is
  duplicated across two separate node parameter fields rather than computed
  once and referenced twice. Editing the message means editing it in two
  places and keeping them in sync by hand. Not addressed in this graph; a Set
  node before the fan-out would fix it.

- **Fixed source file.** `Download file`'s file ID is hardcoded to one specific
  Drive file (cached name `1.mainsq.jpg`). The workflow cannot be pointed at
  "whatever image was uploaded today" without editing the node directly. There
  is no folder-watch trigger or expression-based file selection.

- **No error isolation between the two posts.** The two LinkedIn nodes run in
  parallel off the same upstream node with no Merge, IF, or Error Trigger node
  anywhere in the graph. If the company post fails (wrong org permissions,
  expired token, rate limit) after the personal post already succeeded, the
  workflow has no way to detect or report the mismatch: n8n will mark the run
  as failed, but the personal post is already live and cannot be rolled back
  from inside this graph. Not addressed.

- **No explicit binary property name on the LinkedIn nodes.** The LinkedIn
  node parameters set `shareMediaCategory: "IMAGE"` but do not carry a visible
  reference to which binary property from `Download file` to use. That means
  both LinkedIn nodes are relying on n8n's implicit default binary property
  name matching what `Download file` produces. If a future version of the
  Google Drive node changes its default binary property name, both posts break
  silently until someone opens the workflow and checks. Not addressed.

- **No visible organization ID on the company-page node.** `Create a company
  post` sets `postAs: "organization"` but the exported parameters do not show
  an explicit organization URN or ID field. I could not determine from this
  JSON alone whether that value lives inside the LinkedIn credential, is
  resolved at runtime through the connected account's linked pages, or was
  simply left at an n8n UI default that did not get exported. This is a real
  gap in what the file alone tells you, stated plainly rather than guessed at.

## What I learned

- In n8n, a single node output can fan out to multiple downstream nodes
  without a Merge node at all; Merge is only needed when two branches need to
  converge back into one, not when they both terminate independently. This
  workflow's `Download file` to two LinkedIn nodes is a legitimate fan-out,
  not a shortcut around a missing Merge node.
- The LinkedIn node's `postAs` parameter (`organization` vs. the personal
  default) is what switches the same node type between profile and page
  posting, rather than there being two distinct LinkedIn node types.
- Credential blocks in an exported n8n workflow (`credentials: { linkedInOAuth2Api: { id, name } }`)
  are references into that instance's credential store, not the credentials
  themselves. A workflow export is safe to share as long as no parameter value
  duplicates a secret outside that block, which is worth checking by hand
  rather than assuming.
- Google Drive's resource locator (`"mode": "list"`) stores both the file ID
  and a cached display name/URL for convenience in the n8n editor; only the
  `value` (the ID) is used at execution time, the cached fields are UI sugar.

## What I'd do differently

- Replace the two hardcoded caption strings with a single upstream Set node
  feeding both LinkedIn nodes through an expression, so there is exactly one
  place to edit the message.
- Add an Error Trigger or an IF node after `Create a personal post` so a
  failed company-page post doesn't leave the run in a half-published state
  with no notification.
- Swap the manual trigger for something that matches how this would actually
  get used: a form trigger for picking the file and typing the caption per
  run, since as built this workflow only ever posts one exact image with one
  exact sentence.
- Confirm and document, rather than leave ambiguous, whether the organization
  target for the company post is configurable per run or fixed to whatever
  the LinkedIn credential resolves to; right now that's a real unknown even to
  someone reading the exported JSON directly.
