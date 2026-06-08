from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from ..config import FAILED_DIR, INBOX_DIR, PROCESSED_DIR
from ..db import init_db, session_scope
from ..utils import calculate_discount, infer_debts, infer_modality, make_fingerprint, normalize_text, parse_area, parse_date, parse_money, parse_percent
from .collector import upsert_property


COLUMN_ALIASES = {
    "id interno": "source_internal_id",
    "id": "source_internal_id",
    "origem": "source",
    "banco": "bank_or_auctioneer",
    "leiloeiro": "bank_or_auctioneer",
    "url original": "source_url",
    "url": "source_url",
    "estado": "state",
    "cidade": "city",
    "bairro": "neighborhood",
    "endereco": "address",
    "endereço": "address",
    "cep": "postal_code",
    "latitude": "latitude",
    "longitude": "longitude",
    "matricula": "registry_number",
    "matrícula": "registry_number",
    "tipo": "property_type",
    "tipo do imóvel": "property_type",
    "area construida": "built_area_m2",
    "área construída": "built_area_m2",
    "area terreno": "land_area_m2",
    "área do terreno": "land_area_m2",
    "valor avaliacao": "appraisal_value",
    "valor de avaliação": "appraisal_value",
    "valor minimo": "minimum_value",
    "valor mínimo": "minimum_value",
    "lance inicial": "minimum_value",
    "lance atual": "current_bid_value",
    "desconto": "discount_percent",
    "percentual de desconto": "discount_percent",
    "data leilao": "auction_date",
    "data do leilão": "auction_date",
    "edital": "notice_url",
    "ocupacao": "occupancy",
    "ocupação": "occupancy",
    "observacoes": "notes",
    "observações": "notes",
    "modalidade": "auction_modality",
    "modalidade_leilao": "auction_modality",
    "dividas": "has_debts",
    "dívidas": "has_debts",
    "possui_dividas": "has_debts",
    "valor_dividas": "debt_value",
    "descricao_dividas": "debt_description",
    "fonte_informacao_dividas": "debt_information_source",
    "imagens": "images",
}


MONEY_FIELDS = {"appraisal_value", "minimum_value", "current_bid_value", "debt_value"}
AREA_FIELDS = {"built_area_m2", "land_area_m2"}


def _canonical_column(column: str) -> str:
    return COLUMN_ALIASES.get(column.strip().lower(), column.strip())


def _clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return normalize_text(value)
    return value


def _read_dataframe(file_obj, suffix: str | None = None) -> pd.DataFrame:
    suffix = (suffix or "").lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_obj)
    if suffix in {".html", ".htm"}:
        tables = pd.read_html(file_obj)
        if not tables:
            return pd.DataFrame()
        return max(tables, key=len)
    return pd.read_csv(file_obj, sep=None, engine="python")


def import_properties_dataframe(df: pd.DataFrame, default_source: str = "importacao") -> dict[str, int]:
    init_db()
    df = df.rename(columns={column: _canonical_column(column) for column in df.columns})
    saved = 0

    with session_scope() as session:
        for _, row in df.iterrows():
            item = {key: _clean_value(value) for key, value in row.to_dict().items()}
            item["source"] = item.get("source") or default_source
            item["bank_or_auctioneer"] = item.get("bank_or_auctioneer") or item.get("source") or "Importação manual"
            item["source_url"] = item.get("source_url") or ""
            if not item["source_url"]:
                continue

            for field in MONEY_FIELDS:
                item[field] = parse_money(item.get(field))
            for field in AREA_FIELDS:
                item[field] = parse_area(item.get(field))
            item["discount_percent"] = parse_percent(item.get("discount_percent")) or calculate_discount(
                item.get("appraisal_value"),
                item.get("minimum_value"),
            )
            item["auction_date"] = parse_date(item.get("auction_date"))
            item["latitude"] = float(item["latitude"]) if item.get("latitude") else None
            item["longitude"] = float(item["longitude"]) if item.get("longitude") else None
            item["images"] = [url.strip() for url in str(item.get("images") or "").split("|") if url.strip()]

            evidence = " ".join(str(item.get(field) or "") for field in ["notes", "debt_description", "auction_modality", "has_debts"])
            item["auction_modality"] = item.get("auction_modality") or infer_modality(evidence)
            if not item.get("has_debts"):
                debts, debt_value, debt_source = infer_debts(evidence)
                item["has_debts"] = debts
                item["debt_value"] = item.get("debt_value") or debt_value
                item["debt_information_source"] = item.get("debt_information_source") or debt_source

            item["fingerprint"] = make_fingerprint(
                [
                    item.get("source"),
                    item.get("source_internal_id"),
                    item.get("source_url"),
                    item.get("state"),
                    item.get("city"),
                    item.get("address"),
                    item.get("minimum_value"),
                ]
            )
            upsert_property(session, item)
            saved += 1
    return {"rows": len(df), "saved": saved}


def import_properties_csv(file_obj, default_source: str = "importacao") -> dict[str, int]:
    return import_properties_dataframe(_read_dataframe(file_obj, ".csv"), default_source)


def import_properties_file(path: str | Path, default_source: str = "importacao") -> dict[str, int]:
    path = Path(path)
    with path.open("rb") as file_obj:
        df = _read_dataframe(file_obj, path.suffix)
    return import_properties_dataframe(df, default_source)


def import_inbox() -> dict[str, int]:
    init_db()
    supported = {".csv", ".tsv", ".xlsx", ".xls", ".html", ".htm"}
    files = [path for path in sorted(INBOX_DIR.iterdir()) if path.is_file() and path.suffix.lower() in supported]
    result = {"files": len(files), "saved": 0, "failed": 0}
    for path in files:
        try:
            imported = import_properties_file(path, default_source=f"inbox_{path.stem}")
            result["saved"] += imported["saved"]
            destination = PROCESSED_DIR / path.name
            if destination.exists():
                destination = PROCESSED_DIR / f"{path.stem}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}{path.suffix}"
            shutil.move(str(path), str(destination))
        except Exception:
            result["failed"] += 1
            destination = FAILED_DIR / path.name
            if destination.exists():
                destination = FAILED_DIR / f"{path.stem}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}{path.suffix}"
            shutil.move(str(path), str(destination))
    return result
