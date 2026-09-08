from __future__ import annotations
from dataclasses import dataclass, field
from ..utils import calculate_discount
from .quality import financing, is_inactive, normalized_key, occupancy, positive_number, safe_url, state_name

@dataclass
class ScoreResult:
    financial: float = 0
    legal: float = 0
    liquidity: float = 0
    location: float = 0
    overall: int | None = None
    explanation: str = ""
    summary: str = ""
    classification: str = "Dados insuficientes"
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

def calculate_score(item: dict) -> ScoreResult:
    missing = [label for key, label in [("minimum_value", "Valor de venda"), ("appraisal_value", "Valor de avaliação")]
               if positive_number(item.get(key)) is None]
    missing += [label for key, label in [("city", "Cidade"), ("state", "Estado"), ("property_type", "Tipo de imóvel")]
                if not item.get(key) or normalized_key(item[key]) == "nao informado"]
    if item.get("state") and not state_name(item["state"]):
        missing.append("Estado válido")
    if missing or is_inactive(item) or item.get("data_quality") == "legacy":
        summary = "Não há dados suficientes e confiáveis para calcular o indicador."
        if is_inactive(item):
            summary = "Oferta indisponível ou encerrada; não é uma oportunidade ativa."
        return ScoreResult(explanation=summary, summary=summary, missing=missing)
    discount = calculate_discount(item["appraisal_value"], item["minimum_value"])
    score = 35 + min(50, max(-35, discount))
    reasons = [f"Desconto de {discount:.1f}% sobre a avaliação informada pela fonte."]
    occupied = occupancy(item.get("occupancy"))
    if occupied == "Desocupado":
        score += 8
        reasons.append("Imóvel desocupado: menor dificuldade operacional de posse.")
    elif occupied == "Ocupado":
        score -= 12
        reasons.append("Imóvel ocupado: possíveis custos e prazo de desocupação.")
    else:
        missing.append("Ocupação não informada")
    financed = financing(item.get("accepts_financing"))
    if financed is True:
        score += 4
        reasons.append("Aceita financiamento, sujeito às condições da fonte.")
    elif financed is False:
        score -= 4
        reasons.append("Não aceita financiamento.")
    else:
        missing.append("Financiamento não informado")
    if safe_url(item.get("notice_url")):
        score += 4
        reasons.append("Edital disponível; sua presença não garante ausência de riscos.")
    else:
        missing.append("Edital não disponível no cadastro")
    modality = normalized_key(item.get("auction_modality"))
    if "venda direta" in modality:
        score += 3
        reasons.append("Venda direta: confirme as condições de proposta e pagamento.")
    elif "2º" in modality or "2o" in modality or "segunda" in modality:
        score -= 5
        reasons.append("2º leilão: confirme a praça vigente e as regras do edital.")
    elif "judicial" in modality and "extrajudicial" not in modality:
        score -= 8
        reasons.append("Modalidade judicial: verifique processo e condições de aquisição.")
    elif modality and modality != "nao informado":
        reasons.append(f"Modalidade {item['auction_modality']}: confira as regras da oferta.")
    else:
        missing.append("Modalidade não informada")
    if normalized_key(item.get("has_debts")) == "com dividas":
        score -= 10
        reasons.append("Dívidas informadas: verificar responsabilidade e valores no edital.")
    score = max(0, min(100, round(score)))
    if occupied != "Desocupado" or missing or normalized_key(item.get("has_debts")) == "com dividas":
        score = min(score, 74)
    classification = "Oportunidade interessante" if score >= 75 else "Analisar com atenção" if score >= 40 else "Alto risco / baixo atrativo"
    summary = ("Os dados disponíveis indicam uma oportunidade potencialmente interessante."
               if score >= 75 else "Os dados disponíveis exigem atenção ao desconto e às condições da aquisição.")
    return ScoreResult(financial=score, overall=score, explanation="\n".join(reasons),
                       summary=summary, classification=classification, reasons=reasons, missing=missing)
