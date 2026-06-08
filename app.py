from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from sqlalchemy import func, select
from streamlit_folium import st_folium

from leilao_app.db import init_db, session_scope
from leilao_app.logging_config import configure_logging
from leilao_app.models import Alert, ChangeHistory, CollectionError, CollectionRun, PriceHistory, Property, ScoreHistory
from leilao_app.scheduler_worker import start_scheduler
from leilao_app.services.collector import run_collection
from leilao_app.services.importer import import_properties_csv


BASE_DIR = Path(__file__).resolve().parent


DEFAULT_IMAGE_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600" viewBox="0 0 900 600">
  <rect width="900" height="600" fill="#e8edf2"/>
  <path d="M180 390h540v90H180z" fill="#c7d0da"/>
  <path d="M245 382V210h410v172" fill="#f7f9fb" stroke="#8d9aa8" stroke-width="8"/>
  <path d="M225 220l225-125 225 125" fill="none" stroke="#607184" stroke-width="18" stroke-linecap="round"/>
  <rect x="315" y="275" width="90" height="105" fill="#dce4ec"/>
  <rect x="495" y="275" width="90" height="105" fill="#dce4ec"/>
  <rect x="420" y="310" width="65" height="72" fill="#aab8c6"/>
  <text x="450" y="530" text-anchor="middle" font-family="Arial" font-size="34" fill="#607184">Sem foto disponível</text>
</svg>
"""
DEFAULT_IMAGE = "data:image/svg+xml;base64," + base64.b64encode(DEFAULT_IMAGE_SVG.encode("utf-8")).decode("ascii")


def money(value: float | None) -> str:
    if value is None:
        return "Não informado"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float | None) -> str:
    return "Não informado" if value is None else f"{value:.1f}%"


def date_fmt(value: datetime | None) -> str:
    return "Não informado" if value is None else value.strftime("%d/%m/%Y")


def score_color(score: float) -> str:
    if score >= 70:
        return "#1f9d55"
    if score >= 40:
        return "#d99a0b"
    return "#c2362b"


def tag_class(value: str) -> str:
    plain = (value or "").lower()
    if "bom" in plain or "sem" in plain or "extrajudicial" in plain:
        return "tag tag-good"
    if "atenção" in plain or "com" in plain or "judicial" in plain:
        return "tag tag-alert"
    return "tag tag-neutral"


def h(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


@st.cache_data(ttl=60)
def load_properties(city: str | None = None) -> pd.DataFrame:
    with session_scope() as session:
        query = select(Property).order_by(Property.score_overall.desc(), Property.discount_percent.desc())
        if city and city != "Todas":
            query = query.where(Property.city == city)
        props = session.execute(query).scalars().all()
        rows = []
        for prop in props:
            rows.append(
                {
                    "id": prop.id,
                    "source": prop.source,
                    "source_url": prop.source_url,
                    "bank_or_auctioneer": prop.bank_or_auctioneer,
                    "state": prop.state,
                    "city": prop.city,
                    "neighborhood": prop.neighborhood,
                    "address": prop.address,
                    "latitude": prop.latitude,
                    "longitude": prop.longitude,
                    "property_type": prop.property_type,
                    "built_area_m2": prop.built_area_m2,
                    "land_area_m2": prop.land_area_m2,
                    "appraisal_value": prop.appraisal_value,
                    "minimum_value": prop.minimum_value,
                    "discount_percent": prop.discount_percent,
                    "auction_date": prop.auction_date,
                    "occupancy": prop.occupancy,
                    "auction_modality": prop.auction_modality,
                    "has_debts": prop.has_debts,
                    "neighborhood_classification": prop.neighborhood_classification,
                    "score_overall": prop.score_overall,
                    "score_financial": prop.score_financial,
                    "score_legal": prop.score_legal,
                    "score_liquidity": prop.score_liquidity,
                    "score_location": prop.score_location,
                    "automatic_summary": prop.automatic_summary,
                    "primary_image": next((img.image_url for img in prop.images if img.is_primary), None),
                }
            )
        return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def load_cities() -> list[str]:
    with session_scope() as session:
        cities = session.execute(select(Property.city).where(Property.city.is_not(None)).distinct().order_by(Property.city)).scalars().all()
        return ["Todas"] + [city for city in cities if city]


def load_property_detail(property_id: int) -> Property | None:
    with session_scope() as session:
        prop = session.get(Property, property_id)
        if not prop:
            return None
        prop.images
        prop.price_history
        prop.score_history
        prop.change_history
        return prop


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {padding-top: 1.1rem; max-width: 1360px;}
        * {box-sizing: border-box;}
        .app-topbar {background:#0a3d62; color:#fff; border-radius: 8px; padding: 16px 20px; margin-bottom: 14px; width:100%;}
        .app-topbar strong {display:block; font-size: 22px; line-height:1.2;}
        .app-topbar span {display:block; color:#dbeafe; font-size: 13px; line-height:1.35; margin-top: 5px; overflow-wrap:anywhere;}
        .search-panel {border:1px solid #d8dee6; border-radius:8px; background:#fff; padding:16px; margin: 4px 0 18px;}
        .search-title {font-size:16px; font-weight:800; color:#111827; margin: 0 0 10px;}
        .listing-toolbar {display:flex; align-items:center; justify-content:space-between; gap:12px; margin: 10px 0 14px;}
        .listing-count {font-size: 18px; color:#1f2937; font-weight: 750;}
        .listing-count span {color:#f58220;}
        .view-toggle {display:flex; gap:8px; color:#475467; font-weight:650; font-size:14px;}
        .view-toggle span {border:1px solid #d8dee6; border-radius:6px; padding:6px 10px; background:#fff;}
        .view-toggle .active {background:#0a3d62; color:#fff; border-color:#0a3d62;}
        .empty-state {border:1px solid #d8dee6; border-radius:8px; background:#fff; padding:22px; margin-top:12px;}
        .empty-state strong {display:block; font-size:18px; color:#111827; margin-bottom:6px;}
        .empty-state p {color:#475467; margin:0 0 12px;}
        .empty-actions {display:flex; flex-wrap:wrap; gap:10px;}
        .empty-actions code {background:#eef2f6; border-radius:6px; padding:7px 9px;}
        h1, h2, h3 {letter-spacing: 0;}
        .metric-strip {display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 8px 0 18px;}
        .metric-box {border: 1px solid #d8dee6; border-radius: 8px; padding: 12px; background: #ffffff;}
        .metric-box span {display:block; color:#667085; font-size: 13px;}
        .metric-box strong {display:block; color:#1f2937; font-size: 22px; margin-top: 4px;}
        .auction-card {display:grid; grid-template-columns: minmax(190px, 245px) minmax(280px, 1fr) minmax(220px, 285px); gap:0; border: 1px solid #d8dee6; border-radius: 8px; overflow:visible; background:#fff; margin-bottom: 14px;}
        .auction-card img {width:100%; height:100%; min-height:205px; object-fit: cover; display:block; background:#e8edf2; border-radius: 8px 0 0 8px;}
        .auction-main {min-width:0; padding: 14px 16px; border-right:1px solid #edf0f3;}
        .auction-kind {font-size: 13px; color:#0a3d62; font-weight:800; text-transform: uppercase; margin-bottom: 7px; overflow-wrap:anywhere;}
        .auction-location {font-size: 17px; line-height:1.25; font-weight: 800; color:#111827; margin-bottom: 6px; overflow-wrap:anywhere;}
        .auction-address {font-size: 14px; line-height:1.35; color:#475467; margin-bottom: 10px; overflow-wrap:anywhere;}
        .auction-main p {line-height:1.4; margin: 8px 0 0; overflow-wrap:anywhere;}
        .auction-facts {display:flex; flex-wrap:wrap; gap:8px 10px; color:#475467; font-size:13px; margin:8px 0 10px; overflow-wrap:anywhere;}
        .auction-side {min-width:0; padding: 14px; background:#fafafa; border-radius: 0 8px 8px 0;}
        .round-label {font-size:12px; color:#667085; font-weight:700; text-transform:uppercase;}
        .price-main {font-size:18px; line-height:1.18; color:#111827; font-weight:850; margin:3px 0 8px; overflow-wrap:anywhere;}
        .date-line {font-size:13px; line-height:1.35; color:#475467; margin-bottom:10px; overflow-wrap:anywhere;}
        .discount-box {display:inline-flex; align-items:center; justify-content:center; min-width:54px; border-radius:7px; background:#f58220; color:#fff; font-weight:850; padding:5px 8px; margin-bottom: 9px;}
        .score-side {display:flex; align-items:center; justify-content:space-between; gap:8px; border-top:1px solid #e5e7eb; padding-top:10px; margin-top:8px;}
        .open-btn {display:block; width:100%; text-align:center; border-radius:7px; background:#0a3d62; color:#fff !important; text-decoration:none; padding:10px 8px; font-size:14px; line-height:1.2; font-weight:800; margin-top: 10px; white-space:normal; overflow-wrap:anywhere;}
        .tag-row {display:flex; flex-wrap:wrap; gap: 6px; margin: 8px 0 10px;}
        .tag {display:inline-flex; align-items:center; max-width:100%; border-radius: 999px; padding: 3px 9px; font-size: 12px; line-height:1.25; font-weight: 650; overflow-wrap:anywhere;}
        .tag-good {background:#e7f6ee; color:#126b3a;}
        .tag-alert {background:#fff3d9; color:#8a5a00;}
        .tag-neutral {background:#eef2f6; color:#475467;}
        .score-pill {display:inline-flex; align-items:center; justify-content:center; min-width: 54px; border-radius: 8px; color:#fff; padding: 6px 9px; font-weight: 800;}
        .value-grid {display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 10px 0;}
        .value-grid div {border-top: 1px solid #edf0f3; padding-top: 8px;}
        .value-grid span {display:block; color:#667085; font-size: 12px;}
        .value-grid strong {font-size: 14px; color:#1f2937;}
        @media (max-width: 1050px) {
            .auction-card {grid-template-columns: 220px minmax(0, 1fr);}
            .auction-side {grid-column: 1 / -1; border-top:1px solid #edf0f3; border-radius: 0 0 8px 8px;}
            .auction-card img {border-radius: 8px 0 0 0;}
        }
        @media (max-width: 760px) {
            .metric-strip, .value-grid {grid-template-columns: 1fr 1fr;}
            .auction-card {grid-template-columns: 1fr;}
            .auction-card img {height:210px; border-radius: 8px 8px 0 0;}
            .auction-main {border-right:0; border-bottom:1px solid #edf0f3;}
            .listing-toolbar {align-items:flex-start; flex-direction:column;}
            .price-main {font-size:17px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(df: pd.DataFrame) -> None:
    count = len(df)
    avg_score = df["score_overall"].mean() if count else 0
    high = len(df[df["score_overall"] >= 80]) if count else 0
    avg_discount = df["discount_percent"].dropna().mean() if count and "discount_percent" in df else 0
    st.markdown(
        f"""
        <div class="metric-strip">
          <div class="metric-box"><span>Imóveis monitorados</span><strong>{count}</strong></div>
          <div class="metric-box"><span>Score médio</span><strong>{avg_score:.1f}</strong></div>
          <div class="metric-box"><span>Score acima de 80</span><strong>{high}</strong></div>
          <div class="metric-box"><span>Desconto médio</span><strong>{avg_discount:.1f}%</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_property_card(row: pd.Series) -> None:
    image = row.get("primary_image") or DEFAULT_IMAGE
    score = float(row.get("score_overall") or 0)
    area = row.get("built_area_m2")
    if pd.isna(area) or area is None:
        area = row.get("land_area_m2") if "land_area_m2" in row else None
    area_text = "Área não informada" if pd.isna(area) or area is None else f"{float(area):.2f}m²".replace(".", ",")
    kind = row.get("property_type") or "Imóvel"
    location = f"{row.get('city') or 'Cidade não informada'} / {row.get('state') or '--'}"
    neighborhood = row.get("neighborhood") or "Bairro não informado"
    address = row.get("address") or "Endereço não informado"
    discount = row.get("discount_percent")
    discount_text = "Score" if pd.isna(discount) or discount is None else f"{float(discount):.0f}% off"
    st.markdown(
        f"""
        <div class="auction-card">
          <img src="{h(image)}" alt="Foto do imóvel">
          <div class="auction-main">
            <div class="auction-kind">{h(kind)}</div>
            <div class="auction-location">{h(location)} - {h(neighborhood)}</div>
            <div class="auction-address">{h(address)}</div>
            <div class="auction-facts">
              <span>{h(area_text)}</span>
              <span>{h(row.get('bank_or_auctioneer') or 'Origem não informada')}</span>
              <span>{h(row.get('occupancy') or 'Ocupação não informada')}</span>
            </div>
            <div class="tag-row">
              <span class="{tag_class(row.get('neighborhood_classification'))}">{h(row.get('neighborhood_classification') or 'Bairro Médio')}</span>
              <span class="{tag_class(row.get('auction_modality'))}">{h(row.get('auction_modality') or 'Não informado')}</span>
              <span class="{tag_class(row.get('has_debts'))}">{h(row.get('has_debts') or 'Não informado')}</span>
            </div>
            <p>{h(row.get('automatic_summary') or 'Parecer ainda não disponível.')}</p>
          </div>
          <div class="auction-side">
            <div class="round-label">Valor de avaliação</div>
            <div class="price-main">{money(row.get('appraisal_value'))}</div>
            <div class="round-label">Lance inicial</div>
            <div class="price-main">{money(row.get('minimum_value'))}</div>
            <div class="date-line">Leilão: {date_fmt(row.get('auction_date'))}</div>
            <div class="discount-box">{discount_text}</div>
            <div class="score-side">
              <div>
                <div class="round-label">Score</div>
                <strong>{score:.1f}/100</strong>
              </div>
              <span class="score-pill" style="background:{score_color(score)}">{score:.0f}</span>
            </div>
            <a class="open-btn" href="{h(row.get('source_url'))}" target="_blank">Abrir anúncio original</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ver detalhes", key=f"detail_{row['id']}"):
        st.session_state["selected_property_id"] = int(row["id"])


def render_monitor(df: pd.DataFrame) -> None:
    render_metrics(df)
    st.markdown(
        f"""
        <div class="listing-toolbar">
          <div class="listing-count"><span>{len(df)}</span> resultados oportunidades encontradas</div>
          <div class="view-toggle"><span>Mapa</span><span class="active">Lista</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if df.empty:
        render_empty_state()
        return
    for _, row in df.iterrows():
        render_property_card(row)


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="empty-state">
          <strong>Nenhum imóvel carregado ainda</strong>
          <p>As fontes públicas testadas estão bloqueando coleta automatizada por robots.txt ou CAPTCHA. Para visualizar a plataforma com dados reais, importe um CSV na aba Admin.</p>
          <div class="empty-actions">
            <code>samples/imoveis_importacao.csv</code>
            <code>Admin > Importar imóveis por CSV</code>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail(df: pd.DataFrame) -> None:
    if df.empty:
        render_empty_state()
        return
    options = {f"#{int(row.id)} · {row.city or 'Sem cidade'} · {row.neighborhood or 'Sem bairro'} · Score {row.score_overall:.0f}": int(row.id) for row in df.itertuples()}
    selected = st.session_state.get("selected_property_id") or next(iter(options.values()))
    labels = list(options.keys())
    selected_label = next((label for label, value in options.items() if value == selected), labels[0])
    chosen_label = st.selectbox("Imóvel", labels, index=labels.index(selected_label))
    prop = load_property_detail(options[chosen_label])
    if not prop:
        st.warning("Imóvel não encontrado.")
        return

    images = [img.image_url for img in prop.images] or [DEFAULT_IMAGE]
    st.subheader(f"{prop.city or 'Cidade não informada'} · {prop.neighborhood or 'Bairro não informado'}")
    st.markdown(f"[Abrir anúncio oficial]({prop.source_url})")
    st.image(images, use_column_width=True)

    left, right = st.columns([1, 1])
    with left:
        st.write("**Dados completos**")
        st.dataframe(
            pd.DataFrame(
                [
                    ["Origem", prop.bank_or_auctioneer],
                    ["Estado", prop.state],
                    ["Cidade", prop.city],
                    ["Bairro", prop.neighborhood],
                    ["Endereço", prop.address],
                    ["CEP", prop.postal_code],
                    ["Matrícula", prop.registry_number],
                    ["Tipo", prop.property_type],
                    ["Área construída", prop.built_area_m2],
                    ["Área terreno", prop.land_area_m2],
                    ["Avaliação", money(prop.appraisal_value)],
                    ["Lance inicial", money(prop.minimum_value)],
                    ["Desconto", pct(prop.discount_percent)],
                    ["Ocupação", prop.occupancy],
                    ["Modalidade", prop.auction_modality],
                    ["Dívidas", prop.has_debts],
                    ["Valor dívidas", money(prop.debt_value)],
                    ["Descrição dívidas", prop.debt_description],
                    ["Fonte dívidas", prop.debt_information_source],
                    ["Edital", prop.notice_url],
                    ["Observações", prop.notes],
                ],
                columns=["Campo", "Valor"],
            ),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        st.write("**Score detalhado**")
        st.progress(int(prop.score_overall), text=f"Score geral: {prop.score_overall:.1f}/100")
        st.write(prop.score_explanation)
        st.write(f"**Bairro:** {prop.neighborhood_classification}")
        st.write(prop.neighborhood_reason)
        st.write("**Parecer automático**")
        st.write(prop.automatic_summary)
        if prop.latitude and prop.longitude:
            fmap = folium.Map(location=[prop.latitude, prop.longitude], zoom_start=15, tiles="OpenStreetMap")
            folium.Marker([prop.latitude, prop.longitude], tooltip=prop.city, popup=prop.source_url).add_to(fmap)
            st_folium(fmap, height=360, use_container_width=True)
        else:
            st.info("Sem latitude/longitude para mapa individual.")

    st.write("**Histórico de preços**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Data": item.captured_at,
                    "Avaliação": item.appraisal_value,
                    "Lance mínimo": item.minimum_value,
                    "Lance atual": item.current_bid_value,
                    "Desconto": item.discount_percent,
                }
                for item in prop.price_history
            ]
        ),
        use_container_width=True,
    )
    st.write("**Histórico de score**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Data": item.captured_at,
                    "Financeiro": item.score_financial,
                    "Jurídico": item.score_legal,
                    "Liquidez": item.score_liquidity,
                    "Localização": item.score_location,
                    "Geral": item.score_overall,
                }
                for item in prop.score_history
            ]
        ),
        use_container_width=True,
    )
    st.write("**Histórico de alterações**")
    st.dataframe(
        pd.DataFrame(
            [
                {"Data": item.changed_at, "Campo": item.field_name, "Antes": item.old_value, "Depois": item.new_value}
                for item in prop.change_history
            ]
        ),
        use_container_width=True,
    )


def render_map(df: pd.DataFrame) -> None:
    if df.empty or not {"latitude", "longitude"}.issubset(df.columns):
        st.info("Nenhum imóvel com coordenadas geográficas ainda.")
        return
    mapped = df.dropna(subset=["latitude", "longitude"])
    if mapped.empty:
        st.info("Nenhum imóvel com coordenadas geográficas ainda.")
        return
    center = [mapped["latitude"].mean(), mapped["longitude"].mean()]
    fmap = folium.Map(location=center, zoom_start=6, tiles="OpenStreetMap")
    for _, row in mapped.iterrows():
        color = "green" if row["score_overall"] >= 70 else "orange" if row["score_overall"] >= 40 else "red"
        html = f"""
        <strong>{row.get('city') or ''} - {row.get('neighborhood') or ''}</strong><br>
        Score: {row.get('score_overall'):.1f}<br>
        Lance: {money(row.get('minimum_value'))}<br>
        <a href="{row.get('source_url')}" target="_blank">Abrir anúncio</a>
        """
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=8,
            color=color,
            fill=True,
            fill_opacity=0.8,
            popup=folium.Popup(html, max_width=320),
        ).add_to(fmap)
    st_folium(fmap, height=650, use_container_width=True)


def render_ranking(df: pd.DataFrame) -> None:
    required = {"score_overall", "discount_percent", "score_liquidity", "score_legal"}
    if df.empty or not required.issubset(df.columns):
        render_empty_state()
        return
    top = df.sort_values(["score_overall", "discount_percent", "score_liquidity", "score_legal"], ascending=[False, False, False, False]).head(50)
    st.dataframe(
        top[
            [
                "id",
                "city",
                "neighborhood",
                "bank_or_auctioneer",
                "minimum_value",
                "discount_percent",
                "score_overall",
                "score_liquidity",
                "score_legal",
                "source_url",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_alerts() -> None:
    with session_scope() as session:
        alerts = session.execute(select(Alert).order_by(Alert.created_at.desc()).limit(200)).scalars().all()
        rows = [
            {
                "Data": alert.created_at,
                "Tipo": alert.alert_type,
                "Imóvel": alert.property_id,
                "Mensagem": alert.message,
                "Reconhecido": alert.acknowledged,
            }
            for alert in alerts
        ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_admin() -> None:
    st.write("**Importação CSV**")
    st.caption("Use este bloco para alimentar a aplicação quando as fontes públicas bloquearem coleta automatizada.")
    sample_path = BASE_DIR / "samples" / "imoveis_importacao.csv"
    col_a, col_b = st.columns([0.35, 0.65])
    with col_a:
        if st.button("Carregar exemplo local", use_container_width=True):
            with sample_path.open("rb") as file_obj:
                result = import_properties_csv(file_obj)
            st.cache_data.clear()
            st.success(f"Exemplo carregado: {result['saved']} registro(s) salvo(s).")
            st.rerun()
    with col_b:
        st.info("Para dados reais, baixe/monte um CSV no formato do arquivo de exemplo e importe abaixo.")

    uploaded = st.file_uploader("Importar imóveis por CSV", type=["csv"])
    if uploaded is not None and st.button("Importar CSV", use_container_width=True):
        try:
            result = import_properties_csv(uploaded)
            st.cache_data.clear()
            st.success(f"Importação concluída: {result['saved']} registros salvos de {result['rows']} linhas.")
            st.rerun()
        except Exception as exc:
            st.error(f"Falha ao importar CSV: {exc}")

    with session_scope() as session:
        last_run = session.execute(select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(1)).scalar_one_or_none()
        total = session.scalar(select(func.count(Property.id))) or 0
        by_state = pd.DataFrame(session.execute(select(Property.state, func.count(Property.id)).group_by(Property.state)).all(), columns=["Estado", "Qtd"])
        by_city = pd.DataFrame(session.execute(select(Property.city, func.count(Property.id)).group_by(Property.city).order_by(func.count(Property.id).desc())).all(), columns=["Cidade", "Qtd"])
        by_source = pd.DataFrame(session.execute(select(Property.bank_or_auctioneer, func.count(Property.id)).group_by(Property.bank_or_auctioneer)).all(), columns=["Origem", "Qtd"])
        errors = pd.DataFrame(
            [
                {"Data": error.occurred_at, "Fonte": error.source, "URL": error.url, "Erro": error.error_message}
                for error in session.execute(select(CollectionError).order_by(CollectionError.occurred_at.desc()).limit(100)).scalars().all()
            ]
        )
        runs = pd.DataFrame(
            [
                {
                    "Fonte": run.source,
                    "Início": run.started_at,
                    "Fim": run.finished_at,
                    "Sucesso": run.success,
                    "Encontrados": run.items_found,
                    "Salvos": run.items_saved,
                    "Erro": run.error_message,
                }
                for run in session.execute(select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(100)).scalars().all()
            ]
        )

    st.write(f"**Última atualização:** {last_run.finished_at if last_run and last_run.finished_at else 'Nunca'}")
    st.write(f"**Quantidade de imóveis:** {total}")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Quantidade por estado**")
        st.dataframe(by_state, use_container_width=True, hide_index=True)
        st.write("**Quantidade por banco/leiloeiro**")
        st.dataframe(by_source, use_container_width=True, hide_index=True)
    with col2:
        st.write("**Quantidade por cidade**")
        st.dataframe(by_city, use_container_width=True, hide_index=True)
    st.write("**Erros de coleta**")
    st.dataframe(errors, use_container_width=True, hide_index=True)
    st.write("**Execuções de coleta**")
    st.dataframe(runs, use_container_width=True, hide_index=True)


def main() -> None:
    configure_logging()
    init_db()
    st.set_page_config(page_title="Monitor de Leilões Imobiliários", page_icon="home", layout="wide")
    inject_css()

    if "scheduler_started" not in st.session_state:
        try:
            start_scheduler()
            st.session_state["scheduler_started"] = True
        except Exception:
            st.session_state["scheduler_started"] = False

    st.markdown(
        """
        <div class="app-topbar">
          <strong>Leilões de Imóveis</strong>
          <span>SP, MG, PR e SC · Caixa · BB · Santander · Itaú · Leiloeiros oficiais</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Coletar agora", use_container_width=False):
        with st.spinner("Coletando fontes públicas..."):
            result = run_collection()
            st.cache_data.clear()
            st.success(f"Coleta concluída: {result['items_found']} encontrados, {result['items_saved']} salvos, {result['errors']} erros.")

    with st.container(border=True):
        st.markdown('<div class="search-title">Buscar leilões</div>', unsafe_allow_html=True)
        city = st.selectbox("Cidade", load_cities(), index=0, label_visibility="visible")
    df = load_properties(city)
    tabs = st.tabs(["Monitor", "Detalhes", "Mapa", "Top 50 Oportunidades", "Alertas", "Admin"])
    with tabs[0]:
        render_monitor(df)
    with tabs[1]:
        render_detail(df)
    with tabs[2]:
        render_map(df)
    with tabs[3]:
        render_ranking(df)
    with tabs[4]:
        render_alerts()
    with tabs[5]:
        render_admin()


if __name__ == "__main__":
    main()
