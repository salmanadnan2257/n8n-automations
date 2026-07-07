# Credentials required

This workflow will not run without the following external accounts, each wired up as
an n8n credential. None of the values are present in `workflow.json`, only pointers to
credential entries by name.

- **Google Gemini API key** (Google AI Studio / Google PaLM API credential type in
  n8n). Used by every `lmChatGoogleGemini` node, which backs all the copywriting
  agents and all the image/video prompt-writing agents. This is the only LLM provider
  used anywhere in the workflow.
- **Runware.ai API key**, sent as a generic HTTP header credential. Used by the
  `Generate Image` nodes that call `https://api.runware.ai/v1` to turn a written image
  prompt into an actual generated image.
- **Novita.ai API key**, sent as a generic HTTP header credential. Used by the
  `Image-to-Video - POST/GET` and `Text-to-Video - POST/GET` nodes that call
  `https://api.novita.ai/v3/async/wan-i2v`, `.../wan-t2v`, and `.../task-result`
  (Wan image-to-video and text-to-video models) to turn a written video prompt, and
  in the image-to-video case the generated still, into a short video clip.
- **n8n instance** (self-hosted or cloud) to host the form trigger and run the
  workflow. The entry point is a form (`Submit Social Post Details`), not a webhook
  called from another system, so no other inbound integration is required.

No spreadsheet, CMS, or social-platform posting credential is used anywhere in this
workflow. The generated post text, image prompt, video prompt, image URL, and video
URL are assembled in the final `Set` and `Merge` nodes and handed back as the form's
own response (the form trigger's response mode is "last node"), not pushed anywhere
else. Publishing the result to an actual social platform is not part of this workflow.
