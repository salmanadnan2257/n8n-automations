# Credentials

External services and credentials this workflow's nodes require, with no real
values ever stored here.

- **OpenAI API**: used by the Model node (`@n8n/n8n-nodes-langchain.lmChatOpenAi`)
  to run the `gpt-4.1-mini` chat model that powers the joke agent's responses.

No other credentials are required:

- The Joke API and API docs tool nodes call `v2.jokeapi.dev`, a public API that
  needs no authentication.
- There is no Telegram node in this workflow, so no Telegram Bot API token is
  needed.
