from __future__ import annotations

import shutil
import re
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

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


def _parse_money_values(text: str) -> list[float]:
    return [value for value in (parse_money(match) for match in re.findall(r"R\$\s*[\d\.\,]+", text)) if value is not None]


def _infer_property_type_from_text(text: str) -> str | None:
    lower = text.lower()
    for kind in ["apartamento", "apartamentos", "casa", "terreno", "galpão", "galpao", "sobrado", "chácaras", "chácara", "loja", "imóvel urbano"]:
        if kind in lower:
            return kind.replace("galpao", "galpão").title()
    return None


def _parse_leilaoimovel_html(file_obj) -> pd.DataFrame:
    html = file_obj.read()
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    links = {a.get_text(" ", strip=True): a.get("href") for a in soup.select("a[href]")}
    text = soup.get_text("\n")
    city_match = re.search(r"Cidade:\s*([A-Za-zÀ-ÿ\s]+)\((SP|MG|PR|SC)\)", text)
    default_city = city_match.group(1).strip() if city_match else None
    default_state = city_match.group(2).strip() if city_match else None

    pattern = re.compile(
        r"(R\$\s*[\d\.\,]+(?:\s+R\$\s*[\d\.\,]+)?\s*(?:\d{1,3}%?)?\s+"
        r".{0,90}?\s+em\s+(?:Leilão|Venda Direta|Compra Direta).*?\s+em\s+"
        r"(?P<city>[A-Za-zÀ-ÿ\s]+)\s*/\s*(?P<state>SP|MG|PR|SC)\s*-\s*(?P<code>\d+)\s+"
        r"(?P<rest>.*?))"
        r"(?=(?:Data de encerramento:|R\$\s*[\d\.\,]+(?:\s+R\$\s*[\d\.\,]+)?\s*(?:\d{1,3}%?)?\s+.{0,90}?\s+em\s+(?:Leilão|Venda Direta|Compra Direta)|EFETUE LOGIN|$))",
        flags=re.IGNORECASE | re.DOTALL,
    )
    rows: list[dict] = []
    for match in pattern.finditer(text):
        block = re.sub(r"\s+", " ", match.group(0)).strip()
        code = match.group("code")
        city = match.group("city").strip() or default_city
        state = match.group("state").strip() or default_state
        money_values = _parse_money_values(block)
        discount_match = re.search(r"(\d{1,3})\s*%", block)
        discount = parse_percent(discount_match.group(1)) if discount_match else None
        type_ = _infer_property_type_from_text(block)
        auction_date_match = re.search(r"(?:Data de encerramento|1ª Praça|2ª Praça):\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?)", block)
        modality = infer_modality(block)
        debts, debt_value, debt_source = infer_debts(block)
        source_url = next((href for label, href in links.items() if code in label or code in str(href)), None)
        if source_url and source_url.startswith("/"):
            source_url = "https://www.leilaoimovel.com.br" + source_url
        source_url = source_url or f"https://www.leilaoimovel.com.br/leilao-de-imovel/{(city or '').lower().replace(' ', '-')}-{(state or '').lower()}"

        minimum = money_values[0] if money_values else None
        appraisal = money_values[1] if len(money_values) > 1 else None
        address = re.sub(r"^.*?-\s*" + re.escape(code), "", block).strip()
        address = re.split(r"1ª Praça:|2ª Praça:|Data de encerramento:", address)[0].strip(" -")

        rows.append(
            {
                "source": "leilaoimovel_html",
                "source_internal_id": code,
                "bank_or_auctioneer": "Leilão Imóvel",
                "source_url": source_url,
                "state": state,
                "city": city,
                "neighborhood": None,
                "address": address[:500] if address else None,
                "property_type": type_,
                "appraisal_value": appraisal,
                "minimum_value": minimum,
                "current_bid_value": minimum,
                "discount_percent": discount,
                "auction_date": parse_date(auction_date_match.group(1)) if auction_date_match else None,
                "occupancy": "Não informado",
                "notes": block[:2000],
                "auction_modality": modality,
                "has_debts": debts,
                "debt_value": debt_value,
                "debt_information_source": debt_source,
                "images": "",
            }
        )
    return pd.DataFrame(rows)


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
        position = file_obj.tell()
        df = _parse_leilaoimovel_html(file_obj)
        if not df.empty:
            return df
        file_obj.seek(position)
        try:
            tables = pd.read_html(file_obj)
            if not tables:
                return pd.DataFrame()
            return max(tables, key=len)
        except Exception:
            return pd.DataFrame()
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
