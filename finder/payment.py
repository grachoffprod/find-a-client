"""Cheap keyword check of payment terms in a job text (no AI cost).

Returns "risk" (needs documents / RU-only payout), "ok" (crypto/EUR/UAH friendly) or None.
"""
import re

RISK = re.compile(
    r"только (на )?(карт\w* )?(рф|сбер|тиньк|тинек)|самозанят|\bип\b|\bооо\b|договор с|"
    r"паспорт|верификац\w+ (личност|документ)|kyc|тольк\w+ (юр|для рф)|сбербанк|тинькофф|юmoney|юмани|qiwi|киви|"
    r"only (russian|rub)|passport required|id verification",
    re.I,
)
OK = re.compile(
    r"usdt|usdc|крипт|crypto|bitcoin|\bbtc\b|paypal|\bwise\b|iban|\beur\b|євро|евро|\bгрн\b|\buah\b|"
    r"приват ?банк|privat|monobank|\bmono\b|payoneer|stripe",
    re.I,
)


def payment_flag(text: str) -> str | None:
    if RISK.search(text):
        return "risk"
    if OK.search(text):
        return "ok"
    return None
