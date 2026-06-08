from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, Property


def create_alerts_for_property(session: Session, prop: Property, is_new: bool, price_reduced: bool) -> None:
    messages: list[tuple[str, str]] = []
    if prop.score_overall >= 80:
        messages.append(("score_alto", f"Score acima de 80: {prop.city or ''} - {prop.neighborhood or ''}"))
    if (prop.discount_percent or 0) >= 40:
        messages.append(("desconto_alto", f"Desconto acima de 40%: {prop.discount_percent:.1f}%"))
    if price_reduced:
        messages.append(("reducao_preco", "Redução de preço detectada no lance mínimo."))
    if is_new and prop.score_overall >= 70:
        messages.append(("nova_oportunidade", "Nova oportunidade com score acima de 70."))

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
