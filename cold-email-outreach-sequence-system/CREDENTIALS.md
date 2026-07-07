# Credentials required

- Google Gemini (Google PaLM) API: used by every `lmChatGoogleGemini` node in the
  subject line, first email, and five follow-up workflows to generate email copy.
- Tavily API: used by `Online_Research.json` for general web search, news search,
  and LinkedIn profile/company extraction on each lead.
- Instantly.ai API: used by `NEW___Add_Leads_to_Instantly.json` to push the
  finished lead and its generated email sequence into the correct outreach
  campaign.
- Google Sheets API: used to read and write the lead list that the workflows
  operate on (name, company, title, LinkedIn URLs, research results, generated
  copy).

No real values for any of the above are present in this folder.
