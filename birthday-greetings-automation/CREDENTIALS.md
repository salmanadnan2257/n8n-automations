# Credentials required

- **SMTP credential**: used by the "Send email" node to send the birthday
  message (host, port, username, password for any SMTP-capable mail provider).

No credential is needed for the Webhook trigger itself; it's an unauthenticated
public endpoint as exported (see the README's Challenges section for why that
matters if this is deployed as-is).
