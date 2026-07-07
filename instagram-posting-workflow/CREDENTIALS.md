# Credentials required

- **Facebook Graph API credential**: used by "Creating Container ID" and "Facebook
  Graph API1" to call the Instagram publishing endpoints (`media` and
  `media_publish` edges) through the Facebook Graph API. This needs a Facebook app
  with Instagram Graph API access and a long-lived access token tied to an Instagram
  Business or Creator account connected to a Facebook Page.
- An **Instagram Business Account ID** (referred to as `Node` in the workflow's `Set
  Image & Caption` node) is required as a parameter, not a credential; it identifies
  which Instagram account to publish to.
