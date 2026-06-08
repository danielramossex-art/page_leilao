from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    financial: float
    legal: float
    liquidity: float
    location: float
    overall: float
    explanation: str
    summary: str


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


def calculate_score(item: dict) -> ScoreResult:
    discount = item.get("discount_percent") or 0
    minimum_value = item.get("minimum_value") or item.get("current_bid_value") or 0
    appraisal_value = item.get("appraisal_value") or 0
    occupancy = (item.get("occupancy") or "").lower()
    has_debts = item.get("has_debts") or "Não informado"
    neighborhood_classification = item.get("neighborhood_classification") or "Bairro Médio"

    financial = 35 + min(discount, 60) * 0.9
    if appraisal_value and minimum_value and minimum_value < appraisal_value:
        financial += 8
    if minimum_value <= 0:
        financial -= 20

    legal = 78
    if "ocupado" in occupancy:
        legal -= 25
    if has_debts == "Com dívidas":
        legal -= 25
    elif has_debts == "Não informado":
        legal -= 8
    if item.get("auction_modality") == "Judicial":
        legal -= 8

    liquidity = 55
    if minimum_value >= 120_000:
        liquidity += 8
    if discount >= 35:
        liquidity += 10
    if item.get("property_type") and "terreno" in item["property_type"].lower():
        liquidity -= 5
    if neighborhood_classification == "Bairro Bom":
        liquidity += 12
    elif neighborhood_classification == "Bairro de Atenção":
        liquidity -= 18

    location = 62
    if neighborhood_classification == "Bairro Bom":
        location += 20
    elif neighborhood_classification == "Bairro de Atenção":
        location -= 25
    if item.get("latitude") and item.get("longitude"):
        location += 5

    financial = clamp(financial)
    legal = clamp(legal)
    liquidity = clamp(liquidity)
    location = clamp(location)
    overall = clamp(financial * 0.35 + legal * 0.25 + liquidity * 0.2 + location * 0.2)

    classification = "Oportunidade interessante" if overall >= 70 else "Atenção" if overall >= 40 else "Alto risco"
    explanation = (
        f"Financeiro {financial:.0f}/100 pelo desconto de {discount:.1f}%; "
        f"Jurídico {legal:.0f}/100 considerando ocupação e dívidas; "
        f"Liquidez {liquidity:.0f}/100; Localização {location:.0f}/100. "
        f"Classificação geral: {classification}."
    )
    risk = "moderado"
    if legal < 50:
        risk = "alto"
    elif legal >= 75:
        risk = "baixo"
    summary = (
        f"Imóvel em {neighborhood_classification.lower()}, desconto de {discount:.1f}% "
        f"e risco jurídico {risk}. Recomenda-se conferir edital, matrícula, ocupação e débitos antes de ofertar lance."
    )
    return ScoreResult(financial, legal, liquidity, location, overall, explanation, summary)
