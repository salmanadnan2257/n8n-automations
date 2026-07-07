# Credentials

External services and credentials this workflow's nodes require to run:

- **OpenAI API**: used for the Newsletter Expert agent's chat model, the Project
  Planner's JSON restructuring call, and the Create Title node's subject line
  generation (model referenced: gpt-4o-mini).
- **Anthropic API**: used for the Research Team agent's and Editor agent's chat
  model.
- **Gmail OAuth2**: used by the Send Newsletter node to deliver the finished
  newsletter by email.
- **Tavily API key**: used by the Tavily HTTP Request node inside the tavily
  sub-workflow, to run the live web searches both AI agents call as a tool. Set
  directly in the node's JSON body rather than n8n's credential store in the
  original workflow.
