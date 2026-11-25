"""Job sources. Each provides parse(raw) -> list[Job] and fetch(client, ...) -> list[Job]."""
from finder.sources import flru, freelance_ru, freelancer, guru, hn, kwork, pph, telegram

SOURCES = {
    "freelancer": freelancer.fetch,
    "hn": hn.fetch,
    "pph": pph.fetch,
    "flru": flru.fetch,
    "kwork": kwork.fetch,
    "freelance_ru": freelance_ru.fetch,
    "telegram": telegram.fetch,  # needs a channel list: fetch(client, channels)
    "guru": guru.fetch,
}
