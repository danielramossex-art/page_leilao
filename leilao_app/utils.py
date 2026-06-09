from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Any


TARGET_STATES = {"SP", "MG", "PR", "SC"}


def only_digits(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D+", "", value)
    return digits or None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def normalize_city_name(value: str | None) -> str | None:
    value = normalize_text(value)
    if not value:
        return None
    value = value.replace("ă", "ã").replace("Ă", "Ã")
    words = value.title().split()
    lowercase_words = {"Da", "Das", "De", "Do", "Dos", "E"}
    normalized = [word.lower() if word in lowercase_words else word for word in words]
    return " ".join(normalized)


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def parse_money(value: str | float | int | None) -> float | None:
    if value is None or isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    cleaned = value.replace("\xa0", " ")
    cleaned = re.sub(r"[^\d,.-]", "", cleaned)
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_percent(value: str | float | int | None) -> float | None:
    if isinstance(value, (float, int)):
        return float(value)
    parsed = parse_money(value)
    return parsed


def parse_area(value: str | float | int | None) -> float | None:
    return parse_money(value)


def parse_date(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    value = normalize_text(value)
    if not value:
        return None
    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def infer_state(*parts: str | None) -> str | None:
    text = " ".join(part or "" for part in parts).upper()
    for state in TARGET_STATES:
        if re.search(rf"\b{state}\b", text):
            return state
    state_names = {
        "SAO PAULO": "SP",
        "MINAS GERAIS": "MG",
        "PARANA": "PR",
        "SANTA CATARINA": "SC",
    }
    plain = strip_accents(text)
    for name, uf in state_names.items():
        if name in plain:
            return uf
    return None


def infer_modality(text: str | None) -> str:
    plain = strip_accents((text or "").lower())
    if "extrajudicial" in plain or "alienacao fiduciaria" in plain:
        return "Extrajudicial"
    if "judicial" in plain or "vara" in plain or "processo" in plain:
        return "Judicial"
    return "Não informado"


def infer_debts(text: str | None) -> tuple[str, float | None, str | None]:
    plain = strip_accents((text or "").lower())
    if any(term in plain for term in ["sem debito", "sem onus", "quitado", "livre de debitos"]):
        return "Sem dívidas", None, "Indicação textual do edital/anúncio"
    if any(term in plain for term in ["debito", "divida", "condominio", "iptu", "onus", "laudemio"]):
        money_match = re.search(r"R\$\s*[\d\.\,]+", text or "")
        return "Com dívidas", parse_money(money_match.group(0)) if money_match else None, "Indicação textual do edital/anúncio"
    return "Não informado", None, None


def make_fingerprint(values: list[Any]) -> str:
    payload = "|".join(normalize_text(str(value)) or "" for value in values)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculate_discount(appraisal_value: float | None, minimum_value: float | None) -> float | None:
    if not appraisal_value or not minimum_value or appraisal_value <= 0:
        return None
    return round(max(0, (1 - minimum_value / appraisal_value) * 100), 2)
