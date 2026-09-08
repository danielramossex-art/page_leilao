"""Conservative normalization shared by ingestion, search and analysis."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from ..utils import normalize_city_name, parse_money, strip_accents
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
INACTIVE = {"inativo", "indisponivel", "encerrado", "encerrada", "finalizado", "arrematado", "vendido", "cancelado", "suspenso", "sustado", "retirado"}

def safe_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlparse(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None

def normalized_key(value) -> str:
    return strip_accents(str(value or "")).strip().casefold()

def city_name(value) -> str | None:
    if not isinstance(value, str):
        return None
    name = normalize_city_name(value)
    return "Jundiaí" if normalized_key(name) == "jundiai" else name

def state_name(value) -> str | None:
    plain = normalized_key(value)
    states = {"ac", "al", "ap", "am", "ba", "ce", "df", "es", "go", "ma", "mt", "ms", "mg", "pa", "pb", "pr", "pe", "pi", "rj", "rn", "rs", "ro", "rr", "sc", "sp", "se", "to"}
    names = {"sao paulo": "SP", "minas gerais": "MG", "parana": "PR", "santa catarina": "SC"}
    return plain.upper() if plain in states else names.get(plain)

def positive_number(value) -> float | None:
    number = parse_money(value)
    return number if number is not None and number > 0 else None

def optional_count(value) -> int | None:
    number = parse_money(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None

def financing(value) -> bool | None:
    if isinstance(value, bool):
        return value
    plain = normalized_key(value)
    if plain in {"sim", "true", "1", "aceita", "aceita financiamento"}:
        return True
    if plain in {"nao", "false", "0", "nao aceita", "nao aceita financiamento"}:
        return False
    return None

def occupancy(value) -> str | None:
    plain = normalized_key(value)
    if re.fullmatch(r"(?:imovel )?desocupad[oa]", plain):
        return "Desocupado"
    if re.fullmatch(r"(?:imovel )?ocupad[oa]", plain):
        return "Ocupado"
    return None

def is_inactive(item: dict, now: datetime | None = None) -> bool:
    status = normalized_key(item.get("status"))
    if any(re.search(rf"\b{term}\b", status) for term in INACTIVE):
        return True
    closing = item.get("ends_at")
    if isinstance(closing, datetime):
        current = now or datetime.now(LOCAL_TZ)
        if current.tzinfo is None:
            current = current.replace(tzinfo=LOCAL_TZ)
        if closing.tzinfo is None:
            closing = closing.replace(tzinfo=LOCAL_TZ)
        if closing.hour == closing.minute == closing.second == 0:
            return closing.date() < current.date()
        return closing < current
    return False

def timestamp_label(value: datetime | None) -> str:
    if value is None:
        return "Não informado"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).strftime("%d/%m/%Y às %H:%M")

def source_label(item: dict) -> str:
    name = item.get("source_name") or item.get("bank_or_auctioneer") or item.get("source") or "Não informado"
    bank = item.get("institution")
    return f"{bank} • via {name}" if bank and normalized_key(bank) != normalized_key(name) else str(name)
