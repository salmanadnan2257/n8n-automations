# Social Media Poster

## What it is

A chat-triggered n8n workflow where a single AI router agent takes a natural-language request ("write me a post about X") and dispatches it to one of six platform-specific sub-workflow tools: X/Twitter, Instagram, Facebook, LinkedIn, Threads, and YouTube Shorts, each implemented as a call back into this same workflow with a different `route` parameter.

## Why it exists

Posting the same idea across multiple platforms usually means writing near-duplicate copy by hand for each one, in each platform's voice and length constraints. This workflow centralizes that behind one chat interface: describe what you want posted, and a router agent picks which platform-specific tool (and by extension, which prompt/format) to invoke, rather than the user needing six different tools or workflows.

## Features

- Single chat entry point (`@n8n/n8n-nodes-langchain.chatTrigger`) for all platforms.
- One LLM-backed router agent that selects the correct posting tool based on the request, using Google Gemini as its model.
- Six tool-workflow nodes (`@n8n/n8n-nodes-langchain.toolWorkflow`), one per platform, each a self-call into this workflow's own ID with a distinct `route` value plus the original `chatInput`.
- Conversation memory via a windowed buffer so the agent has context across a chat session.

## Architecture

1. **When chat message received** (`@n8n/n8n-nodes-langchain.chatTrigger`) is the entry point for a chat message.
2. **Social Media Router Agent** (`@n8n/n8n-nodes-langchain.agent`) is the only decision-making node. Its system prompt is deliberately narrow: it does not answer questions directly, its only job is to pick and call the right tool from the six available and return the tool's response verbatim. It is wired to:
   - **Google Gemini Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGoogleGemini`, model `gemini-2.5-flash-preview-05-20`) as its language model.
   - **Window Buffer Memory** (`@n8n/n8n-nodes-langchain.memoryBufferWindow`) as its conversation memory.
   - Six **toolWorkflow** nodes as its available tools: `create_x_twitter_posts_tool`, `create_instagram_posts_tool`, `create_facebook_posts_tool`, `create_linkedin_posts_tool`, `create_threads_posts_tool`, and `create_youtube_short_tool`. Each tool node's `workflowId` is set to `{{ $workflow.id }}`, meaning each "tool" is actually this same workflow called again, with a `route` field (e.g. `xtwitter`, `instagram`, `linkedin`) and the original `chatInput` passed as fields.
3. There are no nodes in this export that branch on the incoming `route` field to actually generate or post platform-specific content. The six tool nodes call back into the workflow's own ID, but nothing here reads `route` to decide what happens next.

## Setup

1. In n8n, go to Workflows > Import from File and select `workflow.json`.
2. Create/attach a **Google Gemini API** credential on the "Google Gemini Chat Model" node.
3. Because each tool node calls back into `{{ $workflow.id }}`, this workflow must be saved/activated first so it has a stable ID before the self-referencing tool calls will resolve correctly.
4. This export contains only the router half of the system: a real deployment would need the receiving side (a Switch or If node keyed on `route`, plus the actual platform API nodes such as Twitter, LinkedIn, Facebook Graph API, Instagram Graph API, Threads API, and YouTube Data API) added, since none of that exists in this file.
5. Open the workflow's chat panel to test once credentials are attached.

## Usage

Open the chat trigger's test panel (or an embedded chat widget pointed at this workflow) and type a request like "post about our new product launch on LinkedIn." The router agent picks the matching tool and calls back into the workflow with `route` set accordingly.

## Challenges

- **The workflow only contains the router, not the handlers.** All six tool nodes call back into this same workflow's ID with a `route` value, but there is no node in this file (Switch, If, or otherwise) that reads `route` and does something different per platform. As exported, calling any tool loops back into the chat trigger's own agent again rather than reaching real posting logic.
- **No actual platform API nodes are present.** There's no Twitter, LinkedIn, Facebook, Instagram, Threads, or YouTube node anywhere in the graph. The "tools" only pass a route label and the user's raw prompt; the content generation and the actual API call to each platform would have to live in logic this file doesn't include.
- **Self-referencing workflow ID as an architecture choice.** Using `{{ $workflow.id }}` for every tool means all six "sub-workflows" are really the same workflow re-entering itself. That's a compact way to keep everything in one file, but it also means there's no way to tell, from this export alone, how deep the recursion is meant to go or how it's supposed to terminate without the missing route-handling logic.
- **No error handling on the router agent.** If the LLM picks the wrong tool, or none, there's no fallback branch, retry, or user-facing error message; the chat interaction would just fail silently or return whatever the agent decided to say.
- **`YouTube Short` tool passes an `llm` field via `$fromAI`,** the only tool of the six that does this, suggesting the intended sub-workflow needed a model reference passed through, further evidence the actual downstream generation/posting logic (which would need that field) isn't part of this export.

## What I learned

A single-workflow "router agent with tool-workflow self-calls" pattern is a compact way to sketch a multi-platform dispatcher without building six separate workflows up front, but reading this file made clear that sketch and implementation are different things: the routing decision (which tool to call) is fully wired here, while the actual work each tool is supposed to do (write and post content) is not, so this file describes an intent more than a working pipeline end to end.

## What I'd do differently

I would add a Switch node right after the trigger point that each tool workflow calls back into, keyed on the `route` field, with a real branch per platform containing the actual generation prompt and the platform's API node, so the router's tool calls resolve to something concrete. I'd also add an explicit fallback/error branch on the router agent for the case where no tool matches the request.
