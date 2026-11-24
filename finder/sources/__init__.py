"""Источники заказов. Каждый: parse(raw) -> list[Job] и fetch(client, ...) -> list[Job]."""
from finder.sources import flru, freelance_ru, freelancer, guru, hn, kwork, pph, telegram

SOURCES = {
    "flru": flru.fetch,
    "kwork": kwork.fetch,
    "freelancer": freelancer.fetch,
    "hn": hn.fetch,
    "telegram": telegram.fetch,  # нужен список каналов: fetch(client, channels)
    "freelance_ru": freelance_ru.fetch,
    "pph": pph.fetch,
    "guru": guru.fetch,
}
