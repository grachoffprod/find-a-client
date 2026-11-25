"""Job sources. Each provides parse(raw) -> list[Job] and fetch(client, ...) -> list[Job]."""
from finder.sources import freelancer, guru, hn, pph

SOURCES = {
    "freelancer": freelancer.fetch,
    "hn": hn.fetch,
    "pph": pph.fetch,
    "guru": guru.fetch,
}
