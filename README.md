# Job Finder

Every ~15 minutes, the finder collects new projects from freelance platforms,
filters them by your topics, drafts a proposal with AI, and sends it to Telegram.
All discovered jobs appear in the web dashboard.

**Sources:** Freelancer.com, PeoplePerHour, Guru, and Hacker News (the “Who is
hiring?” thread; contract and freelance roles only).

You review and send proposals yourself. The finder only discovers jobs and
prepares draft text.

---

## Setup (~15 minutes, once)

### 1. Telegram bot

1. Open **@BotFather** in Telegram, choose `/newbot`, enter a name, and copy the **token**.
2. Open your new bot and press **Start** (send it any message).
3. Find your **chat ID** by opening
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser (replace `<TOKEN>`
   with your token) and locating `"chat":{"id": 123456789` — that number is your chat ID.

### 2. AI API key (choose one)

- **Claude API:** console.anthropic.com → Settings → Billing (add at least $5) → API Keys → Create Key.
- **OpenRouter:** openrouter.ai → Keys → Create Key. Then set `provider: openrouter`
  in `config/settings.yaml` and choose a model from openrouter.ai/models.

### 3. GitHub repository

1. On github.com, choose **New repository**, enter a name such as `client-finder`,
   select **Public**, and click **Create**. A public repository provides enough free
   Actions minutes and enables the dashboard. Your keys stay private in repository secrets.
2. Upload this folder, excluding `.venv`.

### 4. Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `TELEGRAM_CHAT_ID` | Number from step 1.3 |
| `ANTHROPIC_API_KEY` | Claude key, if you chose Claude |
| `OPENROUTER_API_KEY` | OpenRouter key, if you chose OpenRouter |

Store keys here only, not in files or chats.

### 5. Enable the workflow and dashboard

1. Go to **Settings → Actions → General → Workflow permissions**, select **Read and write**, and save.
2. Open **Actions → Job Finder → Run workflow**. The first run marks existing jobs
   as seen and sends one “Finder started” message. Later runs send only new jobs.
3. Go to **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`** and save.
   The dashboard will be available at `https://<your-user>.github.io/<repository-name>/`.

---

## Configuration

Edit the files in `config/` (on GitHub, use the pencil icon):

- `settings.yaml` — AI model, minimum Telegram score (`min_score`), minimum budget,
  and enabled sources.
- `topics.yaml` — topics, keywords, and stop words.
- `profile.yaml` — your name, services, payment method, and portfolio URL. Add a URL
  to `portfolio_url` when you have one, and AI will include it in proposals.

## Troubleshooting

- **A source stops working:** you will receive an alert. Remove it from
  `sources.enabled` in `settings.yaml` if needed.
- **Jobs arrive without proposals:** check the AI key in repository secrets and its balance.
- **No jobs arrive:** open the latest run under **Actions** and check the log for
  the number of jobs found on each source.

## Development

```sh
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest
.venv/Scripts/python -m finder.run  # without keys, messages are printed to the console
```

For local runs, store keys in `.env` (this file is not committed to git).
