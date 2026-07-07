# Credentials required

- **Google Sheets OAuth2 credential**: used by "1️⃣ Fetch All Scripts" and "1️⃣2️⃣ Save
  HeyGen URL" to read video scripts and write back the raw HeyGen video URL.
- **ElevenLabs credential**: used by "6️⃣ Generate AI Voice" (the ElevenLabs community
  node) to synthesize narration audio from script text. Needs a configured voice id
  as well (the export ships a `YOUR_VOICE_ID` placeholder).
- **HTTP Header Auth credential** (generic), reused across four different providers
  through separate node instances, each needs its own actual key configured after
  import:
  - HeyGen API, used by "7️⃣ Upload Audio to HeyGen", "8️⃣ Create Avatar Video", and
    "🔟 Check Video Status".
  - FFmpeg-as-a-service API (`api.ffmpeg-api.com`), used by "1️⃣3️⃣ Prepare FFmpeg
    Upload" and "1️⃣6️⃣ Crop to Vertical 9:16".
  - Submagic API (`api.submagic.co`), used by "1️⃣7️⃣ Add Captions & B-roll" and
    "1️⃣9️⃣ Check Submagic Status".

A Google Sheet is expected with, at minimum, columns for Topics, Scripts, Heygen
Video, and Final Video (the last of these is read but never written, see the
README's Challenges section).
