from __future__ import annotations

from ..utils import strip_accents


GOOD_HINTS = [
    "centro",
    "jardim",
    "vila nova",
    "batel",
    "savassi",
    "funcionarios",
    "campinas",
    "moema",
    "pinheiros",
    "perdizes",
    "trindade",
]

ATTENTION_HINTS = [
    "zona rural",
    "distrito industrial",
    "periferia",
    "ocupacao",
    "invasao",
]


def classify_neighborhood(city: str | None, neighborhood: str | None, score_inputs: dict[str, float | None]) -> tuple[str, str]:
    name = strip_accents((neighborhood or "").lower())
    discount = score_inputs.get("discount_percent") or 0
    minimum_value = score_inputs.get("minimum_value") or 0

    if any(hint in name for hint in ATTENTION_HINTS):
        return "Bairro de Atenção", "Sinal textual de risco urbano ou baixa liquidez no bairro informado."
    if any(hint in name for hint in GOOD_HINTS):
        return "Bairro Bom", "Boa infraestrutura presumida, maior presença de serviços e liquidez acima da média local."
    if discount >= 45 and minimum_value >= 150_000:
        return "Bairro Médio", "Liquidez potencial razoável, mas sem dados públicos suficientes para classificar como bairro premium."
    return "Bairro Médio", "Classificação conservadora por ausência de dados públicos granulares de infraestrutura e preço por metro quadrado."
