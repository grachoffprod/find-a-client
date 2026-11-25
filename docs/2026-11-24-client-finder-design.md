# Job Finder — Design

Date: 2026-11-24 · Status: draft for approval

## Why

There is no portfolio or review history yet, so clients are unlikely to find the
freelancer on their own, and cold outreach is unappealing. A potential client is
someone who has **already** posted a project on a marketplace, a Telegram channel,
or Reddit. The finder discovers projects worldwide before other freelancers notice
them and prepares a proposal that only needs a quick review before sending.

Success means suitable jobs with draft proposals arrive in Telegram every day, and
the first 3–5 projects are won to build reviews and case studies.

## Goals

- Collect new jobs from every source that can be read automatically.
- Keep only jobs matching 14 topics: landing pages, online stores, Telegram bots,
  mini apps, CRM systems, online booking, automation, API integrations, SaaS,
  online calculators, website templates, extensions, MVPs, and improvements.
- Accept any budget, including small projects; the minimum can be raised in settings.
- For each job, provide a short Russian summary, a relevance score, a proposal in
  the client's language, and its Russian translation.
- Send jobs to a Telegram bot and display them with history in a web dashboard.
- Run in the cloud for free, without keeping a computer on.

## Non-goals

- Automatically send proposals. Marketplaces may ban accounts for this; a person sends them.
- Upwork: its project feed was removed in 2024 and pages return 403. Use it manually only.
- Read private Telegram chats through a personal account due to the account-ban risk;
  this may be a later phase.
- Build a portfolio; that is a separate project to discuss after the finder.

## Failure conditions

- Irrelevant jobs flood Telegram and make the finder unusable.
- Proposals invent experience, projects, or reviews.
- A source silently stops working without anyone knowing.
- An unexpected AI bill arrives.

## Constraints

- AI assistance makes most tasks in the 14 topics feasible.
- English is handled through translation; foreign-language content is translated into Russian.
- Marketplace payments use each platform's methods. Direct clients from Telegram or Reddit
  may pay in crypto, and a proposal may mention USDT.
- Proposals are signed with the user's name (to confirm).
- GitHub's free plan provides 2,000 Actions minutes per month for private repositories,
  while a 15-minute schedule runs about 2,900 times. Free GitHub Pages requires a public
  repository.
- Claude API uses the Haiku model and should cost a few dollars per month.

## Approaches

| Option | Approach | Advantages | Drawbacks |
|---|---|---|---|
| **A — selected** | Python script on GitHub Actions every ~15 min, Claude Haiku, Telegram bot, GitHub Pages dashboard | $0 hosting, runs without a PC | 10–20 min delay; public Telegram channels only |
| B | Same on a VPS, plus private Telegram chats through a personal account | Near real-time, more jobs | 300–500 RUB/month and account risk |
| C | n8n / Make | No code | Low free limits; does not read Kwork and similar sites |

The user selected A for zero cost and no account risk. Moving to B later would only
change where the script runs; no rewrite would be needed.

## Architecture

```text
GitHub Actions (cron */15)
  └─ run.py
       1. Collect:  sources/* → shared Job format
       2. New:      discard jobs already seen (state/seen.json)
       3. Filter:   keywords from 14 topics (RU + EN), budget ≥ threshold
       4. AI:       Claude Haiku → relevance, topic, score 1–10,
                    short Russian summary, proposal + translation
       5. Send:     Telegram bot (score ≥ threshold)
       6. History:  docs/data/jobs.json (latest 500)
       7. Commit    state + jobs.json back to the repository
GitHub Pages (docs/) → dashboard reads jobs.json
```

### Sources (checked 2026-11-24 from a home IP)

| Source | How it is read | Status |
|---|---|---|
| Habr Freelance | RSS `freelance.habr.com/tasks.rss` | 200, readable |
| FL.ru | RSS `fl.ru/rss/all.xml` | 200, 60 jobs |
| Kwork | JSON in `kwork.ru/projects` (`window.stateData`, `wants`) | 200 |
| Freelancer.com | Public API `/api/projects/0.1/projects/active/` | 200 |
| Weblancer, Freelance.ru, PeoplePerHour, Guru | Parse listing pages | 200 |
| Hacker News monthly “Freelancer? Seeking Freelancer?” thread | Public Algolia API, no key | Reddit alternative |
| Reddit (r/forhire, etc.) | — | Since late 2025, keys require manual approval; excluded from v1 |
| Telegram public job channels | Web preview `t.me/s/<channel>` | Works; channel list must be found during implementation |
| Upwork | — | Blocked (403) |

Each source is a separate module. A source failure does not stop the others. After
three consecutive failures, Telegram receives one alert that the source stopped working.

### Shared Job format

`id` (source + native platform ID), `source`, `url`, `title`, `description`,
`budget` (number or empty), `currency`, `posted_at`, `lang`, and `direct`
(direct client, such as Telegram or Reddit, where crypto payment may be possible).

### Pre-AI filter

`config/topics.yaml` contains Russian and English keywords for 14 topics. Jobs without
a match are not sent to AI; this is the main cost control. Stop words also filter out
work such as logo design, SMM, and copywriting.

### AI (Claude Haiku)

One request per job, with a strict JSON response:
`relevant`, `topic`, `score` (1–10), `summary_ru`, `reply` (in the job's language),
`reply_ru` (translation), and `questions` (what to clarify with the client).

The prompt profile in `config/profile.yaml` contains the name, services, areas of
quick delivery, portfolio URL (empty for now), and payment details. The prompt forbids
inventing experience, case studies, and reviews. Proposals are concise: describe the
task in your own words, explain the approach, give a timeline, and ask 1–2 questions.

Safeguards: at most 40 jobs per run and a monthly request limit in `state/usage.json`.
When a limit is reached, jobs still arrive without a proposal and with a marker.

### Telegram

Send one message per job with its topic, source, budget, score, short Russian summary,
and link. Put the proposal and translation in an expandable quote so they can be copied.
The minimum score is configurable and defaults to 6.

### Web dashboard

A single static GitHub Pages page lists jobs from `jobs.json`, with filters for topic,
source, and score, and a copy-proposal button. The “applied / skipped / taken” statuses
are stored in the browser (`localStorage`); no server is needed.

### GitHub Secrets

`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`. The user adds them
to GitHub Secrets; no keys are stored in code or repository files. Local checks use a
`.env` file listed in `.gitignore`.

Choose the AI provider in settings: direct Claude API (default) or OpenRouter (crypto
payments and some free models). Switching providers takes one line.

## User decisions

- Option A: free cloud hosting.
- Use every source that can be read.
- Telegram bot and web dashboard.
- Claude API drafts proposals.
- Translate English content.
- Accept any budget.
- Crypto for direct clients, platform payment methods for marketplaces.
- Use the user's own name.

## Implementation choices (adjustable)

- **Public repository.** A private repository would not provide enough free Actions
  minutes or a free Pages dashboard. Public data includes discovered jobs and proposal
  drafts, which are already public. Secrets remain private.
- Python 3.12 with `httpx`, `feedparser`, `selectolax`, `anthropic`, and `pyyaml`.
- Telegram delivery threshold: score 6/10.
- Model: `claude-haiku-5-5`.

## Risks

- Some sites may block GitHub IP addresses; checks were only made from a home IP.
  Verify on the first run and disable blocked sources or defer them to a later phase.
- Site layouts change and can break a source module; alerts report when a source fails.
- GitHub cron can run late, sometimes 10–20 minutes after its scheduled time.

## Open implementation choices

- Exact public Telegram job channels; find and verify 5–15 active channels.
- Which subreddits to use.
- Telegram message format and dashboard appearance.
- Repository file layout.
