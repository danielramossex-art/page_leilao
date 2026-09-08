from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, Property


def _second_round_alert(prop: Property) -> tuple[str, str] | None:
    match = re.search(
        r"2[ªa]\s*Pra[çc]a:\s*([0-9]{2}/[0-9]{2}/[0-9]{4}\s+[0-9]{2}:[0-9]{2})(?:\s+(R\$\s*[\d\.\,]+))?",
        prop.notes or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    date_text = match.group(1)
    value_text = match.group(2) or "valor nao informado"
    return ("segunda_praca", f"Acompanhar 2a praca em {date_text} com lance previsto de {value_text}.")


def create_alerts_for_property(session: Session, prop: Property, is_new: bool, price_reduced: bool) -> None:
    messages: list[tuple[str, str]] = []
    if prop.opportunity_score is not None and prop.opportunity_score >= 80:
        messages.append(("score_alto", f"Score acima de 80: {prop.city or ''} - {prop.neighborhood or ''}"))
    if (prop.discount_percent or 0) >= 40:
        messages.append(("desconto_alto", f"Desconto acima de 40%: {prop.discount_percent:.1f}%"))
    if price_reduced:
        messages.append(("reducao_preco", "Reducao de preco detectada no lance minimo."))
    if is_new and prop.opportunity_score is not None and prop.opportunity_score >= 75:
        messages.append(("nova_oportunidade", "Nova oportunidade com score acima de 70."))

    second_round = _second_round_alert(prop)
    if second_round:
        messages.append(second_round)

    for alert_type, message in messages:
        existing = session.execute(
            select(Alert).where(
                Alert.property_id == prop.id,
                Alert.alert_type == alert_type,
                Alert.acknowledged.is_(False),
            )
        ).scalar_one_or_none()
        if not existing:
            session.add(Alert(property_id=prop.id, alert_type=alert_type, message=message))
