"""Промпт для оценки заказа и черновика отклика."""
from finder.models import Job

MAX_DESC = 4000

SYSTEM = """Ты помогаешь фрилансеру по имени {name} находить заказы и писать на них отклики.

Его услуги:
{services}

Как он работает: {tools}.

Твоя задача — по одному заказу вернуть СТРОГО один JSON-объект без пояснений:
{{
  "relevant": true/false,   // заказ про разработку из списка услуг, а не вакансия в штат, не дизайн/тексты/маркетинг/ручной труд
  "topic": "одна из тем: {topics}",
  "score": 1-10,            // насколько стоит откликаться: соответствие услугам, понятность задачи, адекватность бюджета
  "summary_ru": "суть заказа по-русски, 1-2 предложения",
  "reply": "черновик отклика НА ЯЗЫКЕ ЗАКАЗА",
  "reply_ru": "перевод отклика на русский (если заказ на русском — тот же текст)",
  "questions": ["1-3 вопроса, которые стоит уточнить у заказчика, по-русски"]
}}

Правила для отклика:
- 60-150 слов, живым языком, без шаблонных фраз вроде «Здравствуйте, я опытный специалист».
- Начни с сути задачи своими словами — покажи, что заказ прочитан.
- Коротко: как это будет сделано и примерный срок.
- Закончи 1-2 конкретными вопросами и подписью «{name}».
- Ничего не выдумывай: никаких лет опыта, выполненных проектов, кейсов, отзывов, команды, наград. Только то, что есть в профиле.
{portfolio_rule}
- Если relevant = false, поля reply и reply_ru оставь пустыми.
"""


def build_prompt(job: Job, profile: dict, topics: list[str]) -> tuple[str, str]:
    portfolio = (profile.get("portfolio_url") or "").strip()
    portfolio_rule = (
        f"- Можно дать ссылку на портфолио: {portfolio}"
        if portfolio else "- Портфолио пока нет: не упоминай его и не давай никаких ссылок."
    )
    system = SYSTEM.format(
        name=profile["name"],
        services="\n".join(f"- {s}" for s in profile["services"]),
        tools=profile.get("tools", ""),
        topics=", ".join(topics) if topics else "любая из услуг",
        portfolio_rule=portfolio_rule,
    )
    pay = profile.get("payment", {})
    payment = (
        f"Заказчик прямой (не биржа): в отклике можно предложить оплату — {pay.get('direct')}."
        if job.direct else "Заказ на бирже: оплата через площадку, способы оплаты не обсуждай."
    )
    desc = job.description[:MAX_DESC]
    budget = f"{job.budget:g} {job.currency or ''}".strip() if job.budget else "не указан"
    user = (
        f"Площадка: {job.source}\nЯзык заказа: {job.lang}\nБюджет: {budget}\n{payment}\n"
        f"Предварительные темы по ключевым словам: {', '.join(topics) or 'нет'}\n\n"
        f"Заголовок: {job.title}\n\nОписание:\n{desc}"
    )
    return system, user
