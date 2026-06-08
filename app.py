from __future__ import annotations

import base64
from datetime import datetime

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
        .main .block-container {padding-top: 1.4rem; max-width: 1320px;}
        h1, h2, h3 {letter-spacing: 0;}
        .metric-strip {display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 8px 0 18px;}
        .metric-box {border: 1px solid #d8dee6; border-radius: 8px; padding: 12px; background: #ffffff;}
        .metric-box span {display:block; color:#667085; font-size: 13px;}
        .metric-box strong {display:block; color:#1f2937; font-size: 22px; margin-top: 4px;}
        .property-card {border: 1px solid #d8dee6; border-radius: 8px; overflow:hidden; background:#fff; margin-bottom: 16px;}
        .property-card img {width:100%; aspect-ratio: 16/9; object-fit: cover; display:block; background:#e8edf2;}
        .property-body {padding: 14px 16px;}
        .property-title {font-size: 18px; font-weight: 700; color:#111827; margin-bottom: 6px;}
        .property-meta {color:#667085; font-size: 13px; margin-bottom: 10px;}
        .tag-row {display:flex; flex-wrap:wrap; gap: 6px; margin: 8px 0 10px;}
        .tag {display:inline-flex; align-items:center; border-radius: 999px; padding: 3px 9px; font-size: 12px; font-weight: 650;}
        .tag-good {background:#e7f6ee; color:#126b3a;}
        .tag-alert {background:#fff3d9; color:#8a5a00;}
        .tag-neutral {background:#eef2f6; color:#475467;}
        .score-pill {display:inline-flex; align-items:center; justify-content:center; min-width: 60px; border-radius: 8px; color:#fff; padding: 6px 10px; font-weight: 800;}
        .value-grid {display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 10px 0;}
        .value-grid div {border-top: 1px solid #edf0f3; padding-top: 8px;}
        .value-grid span {display:block; color:#667085; font-size: 12px;}
        .value-grid strong {font-size: 14px; color:#1f2937;}
        .source-link {border: 1px solid #2563eb; border-radius: 8px; padding: 10px 12px; background:#eff6ff; margin-top: 10px; word-break: break-word;}
        .source-link a {color:#1d4ed8; font-weight: 700; text-decoration: none;}
        @media (max-width: 800px) {
            .metric-strip, .value-grid {grid-template-columns: 1fr 1fr;}
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
    st.markdown(
        f"""
        <div class="property-card">
          <img src="{image}" alt="Foto do imóvel">
          <div class="property-body">
            <div class="property-title">{row.get('city') or 'Cidade não informada'} · {row.get('neighborhood') or 'Bairro não informado'}</div>
            <div class="property-meta">{row.get('bank_or_auctioneer') or 'Origem não informada'} · Leilão: {date_fmt(row.get('auction_date'))}</div>
            <div class="tag-row">
              <span class="{tag_class(row.get('neighborhood_classification'))}">{row.get('neighborhood_classification') or 'Bairro Médio'}</span>
              <span class="{tag_class(row.get('auction_modality'))}">{row.get('auction_modality') or 'Não informado'}</span>
              <span class="{tag_class(row.get('has_debts'))}">{row.get('has_debts') or 'Não informado'}</span>
              <span class="score-pill" style="background:{score_color(score)}">{score:.0f}</span>
            </div>
            <div class="value-grid">
              <div><span>Avaliação</span><strong>{money(row.get('appraisal_value'))}</strong></div>
              <div><span>Lance inicial</span><strong>{money(row.get('minimum_value'))}</strong></div>
              <div><span>Desconto</span><strong>{pct(row.get('discount_percent'))}</strong></div>
            </div>
            <p>{row.get('automatic_summary') or 'Parecer ainda não disponível.'}</p>
            <div class="source-link">URL original: <a href="{row.get('source_url')}" target="_blank">Abrir anúncio original</a></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ver detalhes", key=f"detail_{row['id']}"):
        st.session_state["selected_property_id"] = int(row["id"])


def render_monitor(df: pd.DataFrame) -> None:
    render_metrics(df)
    if df.empty:
        st.info("Nenhum imóvel salvo ainda. Use 'Coletar agora' no topo ou rode o worker agendado.")
        return
    cols = st.columns(2)
    for index, (_, row) in enumerate(df.iterrows()):
        with cols[index % 2]:
            render_property_card(row)


def render_detail(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Nenhum imóvel disponível para detalhar.")
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
    if df.empty:
        st.info("Sem dados para ranking.")
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

    top_left, top_right = st.columns([0.7, 0.3])
    with top_left:
        st.title("Monitor de Leilões Imobiliários")
        st.caption("SP, MG, PR e SC · Caixa · BB · Santander · Itaú · Leiloeiros oficiais")
    with top_right:
        if st.button("Coletar agora", use_container_width=True):
            with st.spinner("Coletando fontes públicas..."):
                result = run_collection()
                st.cache_data.clear()
                st.success(f"Coleta concluída: {result['items_found']} encontrados, {result['items_saved']} salvos, {result['errors']} erros.")

    city = st.selectbox("Cidade", load_cities(), index=0)
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
