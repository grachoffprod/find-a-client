# Искатель заказов

Каждые ~15 минут собирает новые заказы с фриланс-площадок, отбирает подходящие
по вашим темам, пишет через ИИ черновик отклика и присылает в Telegram. Все
найденные заказы видны в веб-панели.

**Площадки:** FL.ru, Kwork, Freelancer.com, Freelance.ru, PeoplePerHour, Guru,
Hacker News (ветка «Who is hiring?», только контракт/фриланс), публичные
Telegram-каналы с заказами.

Откликаетесь вы сами: искатель только находит заказы и готовит текст.

---

## Запуск (один раз, ~15 минут)

### 1. Telegram-бот

1. В Telegram откройте **@BotFather** → `/newbot` → придумайте имя → получите **токен**.
2. Откройте своего нового бота и нажмите **Start** (напишите ему что угодно).
3. Узнайте свой **chat id**: откройте в браузере
   `https://api.telegram.org/bot<ТОКЕН>/getUpdates` (вместо `<ТОКЕН>` — ваш токен)
   и найдите `"chat":{"id": 123456789` — это число и есть chat id.

### 2. Ключ ИИ (один из двух)

- **Claude API:** console.anthropic.com → Settings → Billing (пополнить от $5) → API Keys → Create Key.
- **OpenRouter:** openrouter.ai → Keys → Create Key. Тогда в `config/settings.yaml`
  поставьте `provider: openrouter` и имя модели с openrouter.ai/models.

### 3. Репозиторий на GitHub

1. github.com → **New repository** → имя, например `client-finder` → **Public** →
   Create. (Публичный нужен, чтобы бесплатно хватило минут и работала веб-панель.
   Ключи при этом никто не увидит — они хранятся в секретах.)
2. Загрузите туда эту папку (кроме `.venv`).

### 4. Секреты

Репозиторий → **Settings → Secrets and variables → Actions → New repository secret**.
Добавьте:

| Имя | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен от @BotFather |
| `TELEGRAM_CHAT_ID` | число из шага 1.3 |
| `ANTHROPIC_API_KEY` | ключ Claude (если выбрали Claude) |
| `OPENROUTER_API_KEY` | ключ OpenRouter (если выбрали OpenRouter) |

Ключи вставляйте только сюда — не в файлы и не в чаты.

### 5. Включить

1. **Settings → Actions → General → Workflow permissions → Read and write** → Save.
2. **Actions** → «Искатель заказов» → **Run workflow**.
   Первый запуск запоминает уже висящие заказы и присылает одно сообщение
   «Искатель запущен». Дальше приходят только новые.
3. **Settings → Pages → Source: Deploy from a branch → `main` / `/docs`** → Save.
   Через пару минут панель будет по адресу `https://<ваш-логин>.github.io/<имя-репозитория>/`.

---

## Настройки

Всё меняется в файлах папки `config/` (на GitHub — значок карандаша):

- `settings.yaml` — модель ИИ, порог оценки для Telegram (`min_score`), минимальный
  бюджет, список площадок и Telegram-каналов.
- `topics.yaml` — темы и ключевые слова; стоп-слова.
- `profile.yaml` — имя, услуги, способ оплаты, ссылка на портфолио
  (как появится — впишите в `portfolio_url`, и ИИ начнёт давать её в откликах).

## Если что-то не так

- **Площадка перестала читаться** — придёт сообщение «⚠️ Площадка … не читается».
  Её можно убрать из `sources.enabled` в `settings.yaml`.
- **Заказы приходят без откликов** — проверьте ключ ИИ в секретах и баланс.
- **Ничего не приходит** — Actions → последний запуск → лог: там видно, сколько
  заказов нашлось на каждой площадке.

## Для разработки

```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest
.venv/Scripts/python -m finder.run     # без ключей сообщения печатаются в консоль
```

Ключи для локального запуска — в файл `.env` (он не попадает в git).
