# N8N Automations

This folder collects n8n workflow automations built for Digitalise Agency, curated the
same way the code projects elsewhere in this Portfolio were: surveyed, approved line by
line in `../N8N_WORKFLOW_PROPOSALS.md`, then given its own documented folder here.

n8n is a visual workflow automation tool. Building in it is still engineering work: each
project below chains together triggers, API calls, LLM steps, and data transforms into a
working system, the same design thinking as writing code, expressed as a node graph
instead of text. Each folder contains the exported workflow JSON (importable directly
into n8n) plus a README explaining what it does, how it is built, and its honest limits.

## What is not here yet

Most of the originally-blocked automations were unblocked once the owner enabled
per-workflow MCP access in n8n's settings and got built in later passes:
`linkedin-extractor-from-google-maps/`, `submagic-video-clip-generator/`,
`heygen-ai-video-production/`, `instagram-posting-workflow/`,
`instagram-link-finder-outreach/`, `fathom-native-node-integration/`,
`gmail-outreach-follow-ups/`, `calcom-trigger-workflow/`, and
`subscriber-email-sequence/`. Several of those READMEs disclose real defects found once
the actual node graph could be read (dead ends, disabled triggers, duplicate logic); read
each one's own Challenges section for specifics.

Five automations remain not built, by owner's choice, because MCP access was not enabled
for them and their source is not otherwise accessible (not in the 2025-11-15 backup
export, not on disk):

- Fathom.ai Workflow with Webhook Node (a sibling to the native-node version that is
  built)
- Submagic - Video Clip Generator, the main build (a sibling to the demo version that is
  built)
- Submagic Testing
- Heygen - AI Video Production, the main build (a sibling to the demo version that is
  built)
- Hi-Tec Scripting Agent Automation, a client-named automation

To complete any of these later, enable MCP access on that specific workflow in n8n's
settings, the same way the others above were unblocked.

Two more approved automations were only partially recoverable: the second "Instant VAPI
Call" workflow (sibling to the one documented in `vapi-call-trigger-utility/`) and two
sibling variants of the Instagram Reel Analyzer (sibling to the one documented in
`instagram-reel-analyzer/`) have no accessible source either. Each of those two folders
documents the one variant that could be verified and states plainly what is missing.

## Naming and anonymization

A few workflows are named after real clients or named after their live n8n id rather
than what they do. Where that was the case, the folder name and README describe the
automation by its function, not by a client's name or an unrelated tutorial creator's
handle; any such naming mismatch or lineage (course-derived, community-template-derived)
is disclosed honestly in the individual README, consistent with the attribution rules in
`../PROJECT_STANDARDS.md`.
