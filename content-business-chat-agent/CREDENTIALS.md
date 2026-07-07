# Credentials

External services and credentials this workflow's nodes require to run:

- **OpenAI API**: used for the AI Agent's chat model that powers the conversation.
- **Google Calendar OAuth2**: used by both calendar tool nodes, one to check
  existing availability, one to create a new booked event with the visitor as an
  attendee. Both point at the business's own calendar account.
