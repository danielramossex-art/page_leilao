from __future__ import annotations
import io
import logging
import shutil
from pathlib import Path
import pandas as pd
from ..config import FAILED_DIR, INBOX_DIR, PROCESSED_DIR
from ..db import init_db, session_scope
from ..utils import parse_date, parse_money, normalize_text
from .collector import upsert_property
from .parsing import parse_caixa_csv, parse_html, SOURCE_NAMES, host
from .quality import financing, optional_count, safe_url

logger = logging.getLogger(__name__)
COLUMN_ALIASES = {
    "id interno": "source_internal_id", "id": "source_internal_id", "código": "source_internal_id",
    "origem": "source", "fonte": "source_name", "banco": "institution", "leiloeiro": "source_name",
    "url original": "source_url", "url": "source_url", "link oficial": "official_url",
    "estado": "state", "uf": "state", "cidade": "city", "bairro": "neighborhood",
    "endereco": "address", "endereço": "address", "cep": "postal_code",
    "matricula": "registry_number", "matrícula": "registry_number", "tipo": "property_type",
    "tipo do imóvel": "property_type", "area construida": "built_area_m2", "área construída": "built_area_m2",
    "area terreno": "land_area_m2", "área do terreno": "land_area_m2",
    "valor avaliacao": "appraisal_value", "valor de avaliação": "appraisal_value",
    "valor minimo": "minimum_value", "valor mínimo": "minimum_value", "lance inicial": "minimum_value",
    "valor de venda": "minimum_value", "preço": "minimum_value", "lance atual": "current_bid_value",
    "desconto": "discount_percent", "data leilao": "auction_date", "data do leilão": "auction_date",
    "edital": "notice_url", "ocupacao": "occupancy", "ocupação": "occupancy",
    "observacoes": "notes", "observações": "notes", "modalidade": "auction_modality",
    "modalidade_leilao": "auction_modality", "dividas": "has_debts", "dívidas": "has_debts",
    "possui_dividas": "has_debts", "valor_dividas": "debt_value",
    "descricao_dividas": "debt_description", "fonte_informacao_dividas": "debt_information_source",
    "imagens": "images", "imagem": "images", "quartos": "bedrooms", "vagas": "parking_spaces",
    "financiamento": "accepts_financing", "aceita financiamento": "accepts_financing",
    "situação": "status", "situacao": "status",
}
MONEY_FIELDS = {"appraisal_value", "minimum_value", "current_bid_value", "debt_value", "built_area_m2", "land_area_m2"}

def _clean_value(value):
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return None
    return normalize_text(value) if isinstance(value, str) else value

def _read_dataframe(file_obj, suffix: str | None = None) -> pd.DataFrame:
    suffix = (suffix or ".csv").lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_obj, dtype=object)
    raw = file_obj.read()
    if suffix in {".html", ".htm"}:
        return pd.DataFrame(parse_html(raw))
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = raw.decode("cp1252")
    if "Lista de Imóveis da Caixa" in raw or "Lista de Imoveis da Caixa" in raw:
        return pd.DataFrame(parse_caixa_csv(raw))
    return pd.read_csv(io.StringIO(raw), sep="\t" if suffix == ".tsv" else None, engine="python", dtype=object)

def import_properties_dataframe(df: pd.DataFrame, default_source: str = "importacao") -> dict[str, int]:
    init_db()
    df = df.rename(columns={column: COLUMN_ALIASES.get(str(column).strip().lower(), str(column).strip()) for column in df.columns})
    if df.columns.duplicated().any():
        raise ValueError("Colunas duplicadas após normalização; revise o arquivo.")
    saved = 0
    with session_scope() as session:
        for _, row in df.iterrows():
            item = {key: _clean_value(value) for key, value in row.to_dict().items()}
            item["source"] = item.get("source") or default_source
            item["source_url"] = safe_url(item.get("source_url") or item.get("official_url"))
            if not item["source_url"]:
                continue
            source_name = SOURCE_NAMES.get(host(item["source_url"]))
            item["source_name"] = item.get("source_name") or source_name or item.get("bank_or_auctioneer") or item["source"]
            item["bank_or_auctioneer"] = item.get("bank_or_auctioneer") or item["source_name"]
            if source_name:
                item["official_url"] = item.get("official_url") or item["source_url"]
            for field in MONEY_FIELDS:
                if field in item:
                    item[field] = parse_money(item[field])
            for field in ("auction_date", "ends_at", "verified_at", "source_updated_at"):
                if field in item:
                    item[field] = parse_date(item[field])
            for field in ("latitude", "longitude"):
                if field in item:
                    item[field] = parse_money(item[field])
            if "images" in item:
                value = item["images"]
                images = value if isinstance(value, list) else str(value or "").split("|")
                item["images"] = [url.strip() for url in images if safe_url(url)]
            if "accepts_financing" in item:
                item["accepts_financing"] = financing(item["accepts_financing"])
            item["data_quality"] = item.get("data_quality") or "imported"
            if upsert_property(session, item):
                saved += 1
    return {"rows": len(df), "saved": saved, "skipped": len(df) - saved}

def import_properties_csv(file_obj, default_source: str = "importacao") -> dict[str, int]:
    return import_properties_dataframe(_read_dataframe(file_obj, ".csv"), default_source)

def import_properties_file(path: str | Path, default_source: str = "importacao") -> dict[str, int]:
    path = Path(path)
    with path.open("rb") as file_obj:
        df = _read_dataframe(file_obj, path.suffix)
    if df.empty:
        raise ValueError("Arquivo sem imóveis reconhecidos.")
    return import_properties_dataframe(df, default_source)

def import_inbox() -> dict[str, int]:
    init_db()
    supported = {".csv", ".tsv", ".xlsx", ".xls", ".html", ".htm"}
    files = [path for path in sorted(INBOX_DIR.iterdir()) if path.is_file() and path.suffix.lower() in supported]
    result = {"files": len(files), "saved": 0, "failed": 0}
    for path in files:
        if not path.exists():
            continue
        try:
            imported = import_properties_file(path, default_source=f"inbox_{path.stem}")
            if not imported["saved"]:
                raise ValueError("Arquivo sem imóveis válidos; não tratado como sucesso.")
            result["saved"] += imported["saved"]
            destination_dir = PROCESSED_DIR
        except Exception as exc:
            logger.warning("import_failed file=%s reason=%s", path.name, exc)
            result["failed"] += 1
            destination_dir = FAILED_DIR
        destination = destination_dir / path.name
        if destination.exists():
            destination = destination_dir / f"{path.stem}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S%f')}{path.suffix}"
        if path.exists():
            shutil.move(str(path), str(destination))
    return result
