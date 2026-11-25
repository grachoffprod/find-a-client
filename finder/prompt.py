"""Prompt for job evaluation and draft replies."""
from finder.models import Job

MAX_DESC = 4000

SYSTEM = """You help a freelancer named {name} find projects and write proposals for them.

Services:
{services}

How they work: {tools}.

For each project, return exactly one JSON object with no extra explanation:
{{
  "relevant": true/false,   // a development project matching the services, not employment, design, writing, marketing, or manual labor
  "topic": "one of: {topics}",
  "score": 1-10,            // how worthwhile it is to apply: fit, clarity, and reasonable budget
  "summary_ru": "a 1–2 sentence summary of the project in Russian",
  "reply": "a draft proposal written in the language of the job",
  "reply_ru": "a Russian translation of the proposal (same text if the job is in Russian)",
  "questions": ["1–3 questions to clarify with the client, in Russian"]
}}

Proposal rules:
- Write 60–150 words in a natural voice. Avoid stock phrases such as “Hello, I am an experienced specialist.”
- Start by describing the task in your own words to show you read the brief.
- Briefly explain how you would approach it and give an estimated timeline.
- End with 1–2 specific questions and sign with “{name}”.
- Do not invent years of experience, completed projects, case studies, reviews, a team, or awards. Use only details from the profile.
{portfolio_rule}
- If relevant = false, leave reply and reply_ru empty.
"""


def build_prompt(job: Job, profile: dict, topics: list[str]) -> tuple[str, str]:
    portfolio = (profile.get("portfolio_url") or "").strip()
    portfolio_rule = (
        f"- You may include this portfolio link: {portfolio}"
        if portfolio else "- There is no portfolio yet. Do not mention it or include any links."
    )
    system = SYSTEM.format(
        name=profile["name"],
        services="\n".join(f"- {s}" for s in profile["services"]),
        tools=profile.get("tools", ""),
        topics=", ".join(topics) if topics else "any service",
        portfolio_rule=portfolio_rule,
    )
    pay = profile.get("payment", {})
    payment = (
        f"Direct client (not a marketplace): you may suggest this payment method — {pay.get('direct')}."
        if job.direct else "Marketplace project: payment is handled by the platform; do not discuss payment methods."
    )
    desc = job.description[:MAX_DESC]
    budget = f"{job.budget:g} {job.currency or ''}".strip() if job.budget else "not specified"
    user = (
        f"Source: {job.source}\nJob language: {job.lang}\nBudget: {budget}\n{payment}\n"
        f"Preliminary keyword topics: {', '.join(topics) or 'none'}\n\n"
        f"Title: {job.title}\n\nDescription:\n{desc}"
    )
    return system, user
