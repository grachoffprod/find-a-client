# Job Finder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python finder that collects freelance projects through GitHub Actions every ~15 minutes, filters them by 14 topics, drafts proposals with Claude, and sends them to Telegram and a web dashboard.

**Architecture:** The `finder/` package contains sources (each with `parse()` and `fetch()`), filtering, AI, Telegram, and orchestration in `run.py`. Workflow runs commit `state/` and `docs/data/jobs.json` back to the repository. The dashboard is a static `docs/index.html` on GitHub Pages.

**Tech stack:** Python 3.12 (local 3.14), httpx, feedparser, selectolax, anthropic, pyyaml, pytest.

**Spec:** `docs/2026-11-24-client-finder-design.md`

## Global constraints

- No keys in code or repository files. Use environment variables `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID`; locally, use `.env` listed in `.gitignore`.
- Default model: `claude-haiku-5-5`; provider is `anthropic` or `openrouter` in `config/settings.yaml`.
- Sign proposals as `Yakov`. Never invent experience, case studies, or reviews.
- Send to Telegram when `score >= 6`. Minimum budget is `0` (any budget).
- Send at most 40 jobs to AI per run; monthly request limit `monthly_ai_limit: 3000` in `state/usage.json`.
- Keep the latest 500 jobs in `docs/data/jobs.json`.
- A source that fails 3 runs in a row triggers one Telegram alert.
- Do not send proposals automatically.
- A failure in one source must not stop the others.

## Review focus

1. **First run** (empty `state/seen.json`): hundreds of existing jobs may be found. Mark all as seen, send one “finder started, N jobs in database” message, and do not call AI. → Task 6.
2. **AI fails or returns invalid JSON:** do not lose the job; send it to Telegram without a proposal and mark it. → Tasks 4 and 6.
3. **Special characters and length:** `<` and `&` in titles can break Telegram HTML; messages over 4096 characters are rejected. Escape and truncate. → Task 5.
4. **No budget or text budget** (for example, “negotiable”): `budget=None` passes the filter. → Task 3.
5. **A site's layout changes:** `parse()` may raise or return zero jobs where it used to find some. Continue the run and increment its failure counter. → Task 6.

---

### Task 1: Scaffold, Job model, and configuration

**Files:** Create `requirements.txt`, `.gitignore`, `pytest.ini`, `finder/__init__.py`, `finder/models.py`, `finder/config.py`, `config/settings.yaml`, `config/topics.yaml`, `config/profile.yaml`, and `tests/test_config.py`.

**Interfaces:**

- `@dataclass Job(id: str, source: str, url: str, title: str, description: str, budget: float | None = None, currency: str | None = None, posted_at: str | None = None, lang: str = "ru", direct: bool = False)`; `id` is `f"{source}:{native_id}"`; provide `to_dict() -> dict`.
- `load_settings()`, `load_topics()` (keys `topics: dict[str, list[str]]`, `stop: list[str]`), and `load_profile()` read from `config/` relative to the repository root.
- `settings.yaml` keys: `ai.provider`, `ai.model`, `ai.max_per_run: 40`, `ai.monthly_limit: 3000`, `notify.min_score: 6`, `filter.min_budget: 0`, `history.max_items: 500`, `health.fail_threshold: 3`, `sources.telegram_channels: [...]`, `sources.enabled: [...]`.
- `topics.yaml`: 14 topics (`landing, shop, tg_bot, mini_app, crm, booking, automation, api_integration, saas, calculator, site_template, extension, mvp, fixes`), each with 8–20 lowercase Russian and English keywords; `stop` includes logo, SMM, copywriting, SEO text, video editing, and similar work.
- `profile.yaml`: `name: Yakov`, 14 human-readable services, `tools: "modern stack with AI assistants, fast turnaround"`, empty `portfolio_url`, and payment options (`USDT (TRC20/TON) or discuss` for direct clients; `through the platform` for marketplaces).

- [ ] **Step 1:** Add httpx, feedparser, selectolax, anthropic, pyyaml, pytest to `requirements.txt`; add `.env`, `__pycache__/`, `.venv/` to `.gitignore`; create a virtual environment and install dependencies.
- [ ] **Step 2 — tests:** `test_topics_cover_all_14` checks 14 topics and at least 8 keywords per topic; `test_profile_name` checks `Yakov`; `test_job_id_and_dict` checks `Job(id="kwork:1", ...).to_dict()["id"]`.
- [ ] **Step 3:** Run `pytest tests/test_config.py -v` and confirm it fails; implement the config and model, then confirm it passes.
- [ ] **Step 4:** Initialize git and commit `feat: scaffold, job model, configs`.

### Task 2: Sources

**Files:** Create `finder/sources/__init__.py`, source modules, `finder/http.py`, `tests/fixtures/<source>.*`, and `tests/test_sources.py`.

**Interfaces:**

- Each source module provides pure `parse(raw: str) -> list[Job]` and `fetch(client: httpx.Client) -> list[Job]` functions. The Telegram source also takes `channels: list[str]`.
- `finder/sources/__init__.py` exports `SOURCES: dict[str, Callable]`, mapping names to `fetch` functions.
- `finder/http.py` provides `make_client() -> httpx.Client` with a browser User-Agent, timeout 20, and redirects enabled.
- Sources in the original design: Habr RSS at `https://freelance.habr.com/tasks.rss`; FL.ru RSS at `https://www.fl.ru/rss/all.xml`; Kwork JSON from `window.stateData.wants` at `https://kwork.ru/projects`; Freelancer API at `https://www.freelancer.com/api/projects/0.1/projects/active/?limit=50&full_description=true&job_details=true` (English); Hacker News Algolia search for the latest `Ask HN: Freelancer? Seeking Freelancer?` story, then top-level comments containing `SEEKING FREELANCER` (`direct=True`, English); public Telegram page `https://t.me/s/<channel>` and `.tgme_widget_message` blocks (`direct=True`); Weblancer, Freelance.ru, PeoplePerHour, and Guru HTML listings.
- Parse a numeric budget when available; otherwise use `None`, never zero for missing data.

- [ ] **Step 1:** Save one real response per source in `tests/fixtures/` (curl with a browser User-Agent).
- [ ] **Step 2:** Find and verify 5–15 active public Telegram channels for development jobs. Each `t.me/s/<name>` page should have at least one `.tgme_widget_message_text`; record them in `settings.yaml`.
- [ ] **Step 3 — tests:** For each source, verify the fixture yields at least one job, with a unique source-prefixed `id`, an HTTP `url`, and a nonempty `title`. Check Hacker News keeps no `SEEKING WORK` comments and jobs without budgets use `budget is None`.
- [ ] **Step 4:** Run tests and confirm failure, implement the sources, then confirm they pass.
- [ ] **Step 5:** Run a live check with `python -c "from finder.sources import SOURCES; ..."`. Print the job count per source; each should be positive, or the source should be disabled with a reason in a comment.
- [ ] **Step 6:** Commit `feat: job sources`.

### Task 3: Topic filter and seen-job store

**Files:** Create `finder/filter.py`, `finder/state.py`, and `tests/test_filter.py`.

- `match_topics(job, topics, stop)` returns topics whose words occur in the lowercase title and description; return `[]` when a stop word occurs.
- `passes_budget(job, min_budget)` returns `True` when `budget is None`.
- `SeenStore(path)` provides `.load()`, `.is_new(job_id)`, `.add(job_id)`, `.save()`, and `.is_empty`; retain at most 20,000 recent IDs.
- [ ] **Step 1 — tests:** Check a Russian Telegram bot request matches `tg_bot`; an English landing page matches `landing`; a logo request is blocked; missing budget passes; and seen IDs round-trip through `tmp_path`.
- [ ] **Step 2:** Confirm tests fail, implement, confirm they pass, and commit `feat: topic filter and seen store`.

### Task 4: AI analysis and proposal drafts

**Files:** Create `finder/ai.py`, `finder/prompt.py`, and `tests/test_ai.py`.

- `Analysis` has `relevant`, `topic`, `score`, `summary_ru`, `reply`, `reply_ru`, and `questions` fields.
- `build_prompt(job, profile, topics)` returns `(system, user)` and truncates the job description to 4,000 characters. The system prompt requires the specified JSON schema, a 60–150 word proposal in the job's language signed `Yakov`, no invented experience/case studies/reviews/tenure, optional direct-client payment details from `profile.payment.direct`, and a portfolio URL only when nonempty.
- `parse_analysis(text)` extracts the first JSON object (including from a ```json fence), clamps score to 1–10, and raises `ValueError` on invalid input.
- `analyze(job, profile, settings, topics)` calls the selected provider (`anthropic` SDK `messages.create` with `max_tokens=1200`, or OpenRouter POST to `https://openrouter.ai/api/v1/chat/completions` with httpx), then returns `parse_analysis`; propagate errors.
- `UsageCounter(path)` provides `.can_spend()`, `.spend()`, and `.save()`; store month as `YYYY-MM` and reset on month change.
- [ ] **Step 1 — tests:** Cover plain/fenced JSON, invalid JSON, score clamping, 10,000-character description truncation, prompt restrictions and signature, and monthly usage reset.
- [ ] **Step 2:** Confirm tests fail, implement, and confirm they pass.
- [ ] **Step 3:** If a key is available in `.env`, manually call `analyze` on a fixture job and verify the response parses. Skip and report this step if no key is available.
- [ ] **Step 4:** Commit `feat: AI analysis and reply drafts`.

### Task 5: Telegram

**Files:** Create `finder/telegram_bot.py` and `tests/test_telegram.py`.

- `format_job(job, analysis)` returns HTML with topic, source, budget (or “not specified”), score, Russian summary, and link; put the proposal in an expandable block quote, with a translation when the job is not Russian. If analysis is missing, show a “proposal not generated” marker. Escape all user-provided text with `html.escape`. Limit the output to 4096 characters, truncating the proposal/description first.
- `send(text, token, chat_id, client)` calls `sendMessage` with `disable_web_page_preview=True`; on HTTP 429, wait `retry_after` once.
- [ ] **Step 1 — tests:** Check HTML escaping, 4096-character limit, missing-analysis marker, and absent-budget label.
- [ ] **Step 2:** Confirm tests fail, implement, confirm they pass, and commit `feat: telegram formatting and sending`.

### Task 6: `run.py` pipeline

**Files:** Create `finder/run.py`, `finder/health.py`, `finder/history.py`, and `tests/test_run.py`.

- `update_health(...)` counts consecutive failures, returns alert text exactly at the threshold, and resets on success. Store data in `state/health.json`. A failure is an exception or zero jobs from a source that previously returned more than zero.
- `append_history(path, items, max_items)` prepends entries and trims to `max_items`. Each entry contains `job.to_dict()`, `analysis` (dict or null), `topics`, and UTC ISO `found_at`.
- `run(sources, settings, topics, profile, notifier, analyzer, state_dir, history_path)` returns stats `{fetched, new, matched, analyzed, sent, errors}`. Pass dependencies as parameters to keep tests offline.
- `main()` reads environment and config, creates real dependencies, calls `run`, and prints stats; launch with `python -m finder.run`.
- Flow: on first run (`SeenStore.is_empty`), mark all jobs seen and send one “Finder started: N jobs already in the database; only new jobs will be sent” message without AI. Otherwise, filter new jobs, run AI within limits, set analysis to `None` on errors, send when analysis is missing or relevant with a score at least `min_score`, then save history and seen state. Mark each job seen after attempting to process it, even when AI fails.
- [ ] **Step 1 — tests:** Use fake sources, notifier, and analyzer to check first-run behavior, AI failure notification, low-score history, source-failure isolation, one alert at the health threshold, the 40-job AI cap (remaining jobs sent without proposals), and capped history.
- [ ] **Step 2:** Confirm tests fail, implement, and confirm they pass.
- [ ] **Step 3:** Run `python -m finder.run` locally without Telegram keys (the notifier prints to the console); ensure no crash. Run again and check `new == 0` or close to it.
- [ ] **Step 4:** Commit `feat: pipeline`.

### Task 7: Web dashboard

**Files:** Create `docs/index.html` and `docs/data/jobs.json` (initially `[]`).

- Read the Task 6 history format. Build a single-page dashboard loading `data/jobs.json` with job cards (topic, source, budget, score, summary, link, expandable proposal and translation, and copy button), filters for topic/source/minimum score/status, and statuses (new/applied/skipped/taken) stored in `localStorage` by `job.id`. Support dark/light themes and mobile layouts.
- [ ] **Step 1:** Open locally with `python -m http.server` from `docs/` using real Task 6 history. Check filters, copying, and status persistence after reload.
- [ ] **Step 2:** Commit `feat: dashboard`.

### Task 8: GitHub Actions and setup guide

**Files:** Create `.github/workflows/finder.yml` and `README.md`.

- Workflow: cron `"*/15 * * * *"` plus `workflow_dispatch`; `permissions: contents: write`; `concurrency: finder` with no parallel runs; Python 3.12 and pip cache; run `python -m finder.run` with secrets from `secrets.*`; then commit `state/` and `docs/data/` as `github-actions[bot]` only when changed, using `git pull --rebase` before push.
- README (originally Russian): create a public repository, upload code, add three GitHub secrets, find `TELEGRAM_CHAT_ID` through `getUpdates`, configure Pages to use branch `main` and `/docs`, run the workflow, and explain how to change topics, threshold, and model.
- [ ] **Step 1:** Write the workflow and README; validate YAML with `python -c "import yaml; yaml.safe_load(open(...))"`.
- [ ] **Step 2:** Run full `pytest -v`; all tests should pass.
- [ ] **Step 3:** Commit `feat: GitHub Actions workflow and setup guide`.
