# Credentials required

External services and credentials this workflow's nodes need. No real values are
stored anywhere in this project; each of these is configured in n8n's own credential
store (or, where noted, pasted into a node's own auth fields) by whoever runs the
workflow.

- **Google Sheets OAuth2**: read the ideas row and write status/link updates back to
  the sheet (`Grab Idea`, `Video Status`, `Update Sheet` nodes).
- **Google Drive OAuth2**: upload the generated audio file and make it link-shareable
  so Creatomate can pull it (`Upload to Drive`, `Share File` nodes).
- **OpenAI API**: GPT-4o access for the image prompt agent (`GPT 4o` node).
- **Google Gemini (PaLM) API**: Gemini 2.0 Flash access for the sound prompt agent
  (`Flash 2.0` node).
- **YouTube OAuth2**: upload the finished short as an unlisted video (`Upload Video`
  node).
- **Gmail OAuth2**: send the completion notification email (`Notification` node).
- **PiAPI API key**: text-to-image generation via the Flux model (`Generate Image`,
  `Get Images` nodes); also used by the disabled Kling video-generation branch. Not
  wired to any credential in the exported file, needs to be added.
- **Runway API key**: image-to-video clip generation (`Generate Videos`, `Get Videos`
  nodes). Not wired to any credential in the exported file, needs to be added.
- **ElevenLabs API key**: ambient sound generation (`Generate Audio` node). Not wired
  to any credential in the exported file, needs to be added.
- **Creatomate API key**: final video render from the template (`Render Video` node).
  The exported file shows a placeholder bearer token in the node's own header
  parameter rather than an n8n credential; replace it with a real key through n8n's
  credential store or the node's parameters.
