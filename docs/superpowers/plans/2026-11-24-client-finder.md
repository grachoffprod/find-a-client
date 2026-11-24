# Искатель заказов — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python-искатель, который раз в ~15 минут на GitHub Actions собирает заказы с фриланс-площадок, отбирает их по 14 темам, через Claude пишет отклик и отправляет в Telegram и в веб-панель.

**Architecture:** Пакет `finder/`: источники (каждый — `parse()` + `fetch()`), фильтр, ИИ, Telegram, сборка в `run.py`. Состояние (`state/`) и история (`docs/data/jobs.json`) коммитятся обратно в репозиторий из workflow. Панель — статический `docs/index.html` на GitHub Pages.

**Tech Stack:** Python 3.12 (локально 3.14), httpx, feedparser, selectolax, anthropic, pyyaml, pytest.

**Spec:** `docs/2026-11-24-client-finder-design.md`

## Global Constraints

- Ключей в коде и в файлах репозитория нет: только переменные окружения `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; локально — `.env` в `.gitignore`.
- Модель по умолчанию `claude-haiku-5-5`; провайдер `anthropic` | `openrouter` в `config/settings.yaml`.
- Подпись в откликах: `Yakov`. Отклик не выдумывает опыт, кейсы, отзывы.
- Порог отправки в Telegram: `score >= 6`. Порог бюджета: `0` (любые).
- Не больше 40 заказов к ИИ за запуск; месячный лимит запросов `monthly_ai_limit: 3000` в `state/usage.json`.
- История: последние 500 заказов в `docs/data/jobs.json`.
- Источник, падающий 3 запуска подряд, даёт одно оповещение в Telegram.
- Автоматически отклики не отправляются.
- Ошибка одного источника не останавливает остальные.

## Review Focus

1. **Первый запуск** (пустой `state/seen.json`): сотни уже висящих заказов. Ожидание: всё помечается виденным, в Telegram — одно сообщение «искатель запущен, N заказов в базе», ИИ не вызывается. → Task 6.
2. **ИИ упал или вернул не-JSON**: заказ не теряется — уходит в Telegram без отклика с пометкой. → Task 4, Task 6.
3. **Спецсимволы и длина**: `<`, `&` в заголовке ломают HTML-разметку Telegram; сообщение > 4096 символов отвергается. Ожидание: экранирование и обрезка. → Task 5.
4. **Нет бюджета / бюджет текстом** («договорная»): `budget=None` проходит фильтр. → Task 3.
5. **Вёрстка площадки поменялась**: `parse()` бросает исключение или вернул 0 там, где раньше были заказы — запуск продолжается, счётчик сбоев растёт. → Task 6.

---

### Task 1: Каркас, модель заказа, конфиги

**Files:**
- Create: `requirements.txt`, `.gitignore`, `pytest.ini`, `finder/__init__.py`, `finder/models.py`, `finder/config.py`, `config/settings.yaml`, `config/topics.yaml`, `config/profile.yaml`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass Job(id: str, source: str, url: str, title: str, description: str, budget: float | None = None, currency: str | None = None, posted_at: str | None = None, lang: str = "ru", direct: bool = False)`; `id` = `f"{source}:{native_id}"`; метод `to_dict() -> dict`.
  - `load_settings() -> dict`, `load_topics() -> dict` (ключи `topics: dict[str, list[str]]`, `stop: list[str]`), `load_profile() -> dict` — читают из `config/` относительно корня репо.
  - `settings.yaml` ключи: `ai.provider`, `ai.model`, `ai.max_per_run: 40`, `ai.monthly_limit: 3000`, `notify.min_score: 6`, `filter.min_budget: 0`, `history.max_items: 500`, `health.fail_threshold: 3`, `sources.telegram_channels: [...]`, `sources.enabled: [...]`.
  - `topics.yaml`: 14 тем (ключи `landing, shop, tg_bot, mini_app, crm, booking, automation, api_integration, saas, calculator, site_template, extension, mvp, fixes`), в каждой 8–20 ключевых слов RU+EN в нижнем регистре; `stop`: логотип, smm, копирайт, logo, seo-тексты, видеомонтаж и т.п.
  - `profile.yaml`: `name: Yakov`, `services` (14 тем человеческими словами), `tools: "современный стек с ИИ-ассистентами, быстрые сроки"`, `portfolio_url: ""`, `payment: {direct: "USDT (TRC20/TON) или договоримся", platform: "через площадку"}`.

- [ ] **Step 1:** `requirements.txt`: httpx, feedparser, selectolax, anthropic, pyyaml, pytest. `.gitignore`: `.env`, `__pycache__/`, `.venv/`. Создать `.venv`, установить.
- [ ] **Step 2: Тест** `tests/test_config.py::test_topics_cover_all_14` — `len(load_topics()["topics"]) == 14` и в каждой ≥ 8 слов; `test_profile_name` — `load_profile()["name"] == "Yakov"`; `test_job_id_and_dict` — `Job(id="kwork:1", ...).to_dict()["id"] == "kwork:1"`.
- [ ] **Step 3:** Запустить `pytest tests/test_config.py -v` → FAIL. Реализовать, → PASS.
- [ ] **Step 4:** `git init`, commit `feat: scaffold, job model, configs`.

### Task 2: Источники

**Files:**
- Create: `finder/sources/__init__.py`, `finder/sources/{habr,flru,kwork,freelancer,hn,telegram,weblancer,freelance_ru,pph,guru}.py`, `finder/http.py`, `tests/fixtures/<source>.*`, `tests/test_sources.py`

**Interfaces:**
- Consumes: `Job`.
- Produces:
  - В каждом модуле: `parse(raw: str) -> list[Job]` (чистая функция) и `fetch(client: httpx.Client) -> list[Job]` (скачать + `parse`). `telegram.fetch(client, channels: list[str])`.
  - `finder/sources/__init__.py`: `SOURCES: dict[str, Callable]` — имя → `fetch`.
  - `finder/http.py`: `make_client() -> httpx.Client` (браузерный User-Agent, timeout 20, follow_redirects).
- Источники (из дизайна): habr — RSS `https://freelance.habr.com/tasks.rss`; flru — RSS `https://www.fl.ru/rss/all.xml`; kwork — `https://kwork.ru/projects`, JSON из `window.stateData`, массив `wants`; freelancer — `https://www.freelancer.com/api/projects/0.1/projects/active/?limit=50&full_description=true&job_details=true` (lang `en`); hn — Algolia: найти последний пост `Ask HN: Freelancer? Seeking Freelancer?` (`hn.algolia.com/api/v1/search_by_date?query=...&tags=story,author_whoishiring`), взять его комментарии верхнего уровня, оставить только с `SEEKING FREELANCER` (direct=True, lang `en`); telegram — `https://t.me/s/<channel>`, блоки `.tgme_widget_message` (direct=True); weblancer, freelance_ru, pph, guru — HTML списков заказов.
- Бюджет: число, если найдено; иначе `None`. Никогда не 0 вместо «нет данных».

- [ ] **Step 1:** Скачать по одному реальному ответу каждого источника в `tests/fixtures/` (curl с браузерным UA).
- [ ] **Step 2:** Найти и проверить 5–15 живых публичных Telegram-каналов с заказами на разработку (у каждого `t.me/s/<name>` отдаёт ≥ 1 `.tgme_widget_message_text`); записать в `settings.yaml`.
- [ ] **Step 3: Тесты** `test_sources.py`: для каждого источника `test_<name>_parses_fixture` — `len(parse(fixture)) >= 1`, у каждого заказа непустые `id` (с префиксом источника), `url` (http), `title`; `test_hn_keeps_only_seeking_freelancer` — ни в одном `title+description` нет `SEEKING WORK`; `test_budget_absent_is_none` — у заказа без бюджета в фикстуре `budget is None`.
- [ ] **Step 4:** Запустить → FAIL, реализовать, → PASS.
- [ ] **Step 5:** Живая проверка: `python -c "from finder.sources import SOURCES; ..."` печатает число заказов по каждому источнику; все > 0 либо источник убран из `sources.enabled` с причиной в комментарии.
- [ ] **Step 6:** Commit `feat: job sources`.

### Task 3: Фильтр и память виденного

**Files:**
- Create: `finder/filter.py`, `finder/state.py`, `tests/test_filter.py`

**Interfaces:**
- Produces:
  - `match_topics(job: Job, topics: dict[str, list[str]], stop: list[str]) -> list[str]` — темы, чьи слова встречаются в `title + description` (нижний регистр); `[]`, если есть стоп-слово.
  - `passes_budget(job: Job, min_budget: float) -> bool` — `True` при `budget is None`.
  - `class SeenStore(path)`: `.load()`, `.is_new(job_id) -> bool`, `.add(job_id)`, `.save()`, `.is_empty -> bool`; хранит ≤ 20000 последних id.

- [ ] **Step 1: Тесты:** `test_bot_order_matches_tg_bot` («Нужен телеграм бот для записи» → содержит `tg_bot`); `test_english_landing` («Need a landing page» → `landing`); `test_stop_word_blocks` («Нарисовать логотип для лендинга» → `[]`); `test_no_budget_passes` (`budget=None`, min 1000 → True); `test_seen_roundtrip` (add/save/load в tmp_path → `is_new` False).
- [ ] **Step 2:** FAIL → реализовать → PASS. Commit `feat: topic filter and seen store`.

### Task 4: ИИ-анализ и отклик

**Files:**
- Create: `finder/ai.py`, `finder/prompt.py`, `tests/test_ai.py`

**Interfaces:**
- Consumes: `Job`, `load_profile()`, `load_settings()`.
- Produces:
  - `@dataclass Analysis(relevant: bool, topic: str, score: int, summary_ru: str, reply: str, reply_ru: str, questions: list[str])`.
  - `build_prompt(job: Job, profile: dict, topics: list[str]) -> tuple[str, str]` — (system, user). Описание обрезается до 4000 символов. System требует: только JSON указанной схемы; отклик на языке заказа, 60–150 слов, подпись `Yakov`; не выдумывать опыт, кейсы, отзывы, сроки работы на рынке; для `job.direct` можно упомянуть оплату из `profile.payment.direct`; `portfolio_url` упоминать, только если не пустой.
  - `parse_analysis(text: str) -> Analysis` — достаёт первый JSON-объект из текста (допускает ```json-обёртку), `score` зажат в 1..10; при мусоре — `ValueError`.
  - `analyze(job: Job, profile: dict, settings: dict, topics: list[str]) -> Analysis` — вызывает провайдера (`anthropic`: SDK `messages.create`, `max_tokens=1200`; `openrouter`: POST `https://openrouter.ai/api/v1/chat/completions` через httpx), возвращает `parse_analysis`. Исключения пробрасывает.
  - `class UsageCounter(path)`: `.can_spend() -> bool`, `.spend()`, `.save()`; месяц `YYYY-MM`, сброс при смене месяца.

- [ ] **Step 1: Тесты:** `test_parse_plain_json`; `test_parse_fenced_json`; `test_parse_garbage_raises`; `test_score_clamped` (15 → 10); `test_prompt_truncates_description` (описание 10000 символов → в user-части ≤ 4000 символов описания); `test_prompt_forbids_fake_experience` (в system есть запрет и `Yakov`); `test_usage_resets_on_new_month`.
- [ ] **Step 2:** FAIL → реализовать → PASS.
- [ ] **Step 3:** Ручной вызов `analyze` на одном заказе из фикстуры с ключом из `.env` (ключ вписывает пользователь) — ответ разбирается. Если ключа нет — шаг пропустить и сказать об этом.
- [ ] **Step 4:** Commit `feat: AI analysis and reply drafts`.

### Task 5: Telegram

**Files:**
- Create: `finder/telegram_bot.py`, `tests/test_telegram.py`

**Interfaces:**
- Produces:
  - `format_job(job: Job, a: Analysis | None) -> str` — HTML parse_mode: тема, площадка, бюджет (или «не указан»), оценка, `summary_ru`, ссылка; отклик в `<blockquote expandable>` + перевод (если язык не ru); при `a is None` — строка «⚠️ отклик не сгенерирован». Весь пользовательский текст через `html.escape`. Результат ≤ 4096 символов (отклик/описание обрезаются первыми).
  - `send(text: str, token: str, chat_id: str, client: httpx.Client) -> bool` — `sendMessage`, `disable_web_page_preview=True`; при 429 ждёт `retry_after` один раз.

- [ ] **Step 1: Тесты:** `test_escapes_html` (title `"<b>Бот & CRM"` → в выводе `&lt;b&gt;` и `&amp;`); `test_length_limit` (описание 20000 → `len ≤ 4096`); `test_no_analysis_marker`; `test_budget_none_shows_not_specified`.
- [ ] **Step 2:** FAIL → реализовать → PASS. Commit `feat: telegram formatting and sending`.

### Task 6: Конвейер `run.py`

**Files:**
- Create: `finder/run.py`, `finder/health.py`, `finder/history.py`, `tests/test_run.py`

**Interfaces:**
- Consumes: всё выше.
- Produces:
  - `update_health(health: dict, source: str, ok: bool, threshold: int) -> str | None` — счётчик подряд идущих сбоев; текст оповещения ровно при достижении `threshold`; `ok` сбрасывает. Хранится в `state/health.json`. «Сбой» = исключение ИЛИ 0 заказов у источника, который в прошлый раз давал > 0.
  - `append_history(path, items: list[dict], max_items: int)` — новые сверху, обрезка до `max_items`. Элемент: `job.to_dict()` + `analysis` (dict или null) + `topics` + `found_at` (ISO UTC).
  - `run(sources: dict, settings, topics, profile, notifier: Callable[[str], bool], analyzer: Callable, state_dir, history_path) -> dict` — статистика `{fetched, new, matched, analyzed, sent, errors}`; зависимости передаются параметрами, чтобы тестировать без сети.
  - `main()` — читает env и конфиги, собирает реальные зависимости, вызывает `run`, печатает статистику. `python -m finder.run`.
- Логика: первый запуск (`SeenStore.is_empty`) → всё в seen, одно сообщение «Искатель запущен: N заказов уже в базе, присылаю только новые», без ИИ. Иначе: новые → фильтр → ИИ (лимиты; при исключении `Analysis=None`) → отправка, если `a is None` или (`a.relevant` и `a.score >= min_score`) → история → seen.save. Заказ помечается виденным после попытки обработки, даже при ошибке ИИ.

- [ ] **Step 1: Тесты** (фейковые источники/notifier/analyzer): `test_first_run_marks_all_seen_sends_one`; `test_ai_failure_still_notifies`; `test_low_score_not_sent_but_in_history`; `test_broken_source_does_not_stop_others` (один источник бросает исключение, второй отдаёт заказ → он отправлен, `errors == 1`); `test_health_alert_once_at_threshold`; `test_ai_cap_per_run` (50 подходящих → analyzer вызван 40 раз, остальные отправлены без отклика); `test_history_capped`.
- [ ] **Step 2:** FAIL → реализовать → PASS.
- [ ] **Step 3:** Локальный прогон `python -m finder.run` без ключей Telegram (notifier печатает в консоль) — без падений; повторный прогон — `new == 0` или близко к нулю.
- [ ] **Step 4:** Commit `feat: pipeline`.

### Task 7: Веб-панель

**Files:**
- Create: `docs/index.html`, `docs/data/jobs.json` (пустой `[]`)

**Interfaces:**
- Consumes: формат элемента истории из Task 6.
- Produces: одна страница без сборки: загружает `data/jobs.json`, карточки заказов (тема, площадка, бюджет, оценка, кратко, ссылка, раскрывающийся отклик + перевод, кнопка «Скопировать отклик»), фильтры по теме / площадке / мин. оценке / статусу, статусы «новый / откликнулся / пропустил / взял» в `localStorage` по `job.id`. Тёмная и светлая тема, мобильная вёрстка.

- [ ] **Step 1:** Сделать страницу; открыть локально (`python -m http.server` в `docs/`) с реальной историей из прогона Task 6; проверить в браузере фильтры, копирование, сохранение статуса после перезагрузки.
- [ ] **Step 2:** Commit `feat: dashboard`.

### Task 8: GitHub Actions и инструкция

**Files:**
- Create: `.github/workflows/finder.yml`, `README.md`

**Interfaces:**
- Produces: workflow `schedule: cron "*/15 * * * *"` + `workflow_dispatch`; `permissions: contents: write`; `concurrency: finder` (без параллельных запусков); Python 3.12, pip cache, `python -m finder.run` с секретами из `secrets.*`; затем коммит `state/` и `docs/data/` от `github-actions[bot]`, только если есть изменения (`git diff --quiet || ...`), с `git pull --rebase` перед push.
- README на русском: создать публичный репозиторий; загрузить код; Settings → Secrets → добавить 3 секрета; узнать `TELEGRAM_CHAT_ID` (написать боту, открыть `getUpdates`); Settings → Pages → ветка `main`, папка `/docs`; Actions → Run workflow; как менять темы/порог/модель.

- [ ] **Step 1:** Написать workflow и README; проверить YAML (`python -c "import yaml; yaml.safe_load(open(...))"`).
- [ ] **Step 2:** Полный `pytest -v` → всё PASS.
- [ ] **Step 3:** Commit `feat: GitHub Actions workflow and setup guide`.
