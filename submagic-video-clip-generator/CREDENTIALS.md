# Credentials required

- **Google Sheets OAuth2 credential**: used by the "New Video Added" trigger, "Update
  Status", "Save Clips to Sheet", and "Mark Complete" nodes to poll and write to a
  Google Sheet.
- **HTTP Header Auth credential** (generic): used by "Generate Clips" and "Check Clip
  Status" to authenticate against the clip-generation API (Submagic-style endpoint,
  `api.submagic.co`). Needs whatever header name and API key that provider issues
  (for example `X-API-Key`).

Two Google Sheets are expected to exist before this runs: a "Video Queue" sheet with
columns for status, youtube_url, project_id, created_at, clips_generated, and
completed_at; and a "Generated Clips" sheet with columns for youtube_id, clip_id,
title, duration, virality_score, download_url, and created_at.
