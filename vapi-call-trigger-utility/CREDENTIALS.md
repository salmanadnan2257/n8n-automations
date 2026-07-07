# Credentials required

- **Google Sheets OAuth2 credential**: used to read the lead list ("Google Sheets" node),
  read it a second way for the unused icebreaker branch ("Google Sheets1", disabled),
  and append or update the call-result row after each call ("Google Sheets3" node).
- **HTTP Header Auth credential holding a VAPI private API key**: used by the three
  nodes that call the VAPI API directly ("Update VAPI", "Call VAPI", "Get Call") to
  reconfigure the assistant, start the call, and poll for its status.
- **Google PaLM/Gemini API credential**: used by the "Google Gemini Chat Model" node,
  which powers the "AI Agent" icebreaker-generation branch. That branch is not on the
  live execution path (see the README's Architecture section), so this credential is
  not required for the workflow's main call-triggering function, but n8n will want some
  credential assigned to import or run the file without errors on that node.
- **A VAPI assistant, phone number, and (if kept) VAPI tool integrations**: not an n8n
  credential, but required account setup on VAPI's side. The assistant ID and phone
  number ID are referenced directly in the "Update VAPI" and "Call VAPI" node
  parameters and need to point at resources that exist in your own VAPI account.
