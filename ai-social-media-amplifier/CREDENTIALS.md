# Credentials

- **Airtable** (Personal Access Token): used by "Search Item", "Create Item", "Update X Status", and "Update L Status" to check for already-posted items, log new posts, and mark posting status per platform.
- **OpenAI API**: used by "Generate Content" (model `gpt-4o-mini`) to write the Twitter and LinkedIn post copy.
- **Telegram Bot API**: used by "Ping Me" to send the owner a preview of the drafted posts before they go out.
- **X (Twitter) API**: used by the "X" node to publish the generated tweet.
- **LinkedIn API**: used by the "LinkedIn" node to publish the generated LinkedIn post under a configured person URN.
