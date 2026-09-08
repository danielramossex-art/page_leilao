from __future__ import annotations

import html
import math
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, quote

import streamlit as st
import streamlit.components.v1 as components

from leilao_app.db import init_db
from leilao_app.logging_config import configure_logging
from leilao_app.services.catalog import load_catalog, load_detail, toggle_favorite, filter_properties, sort_properties
from leilao_app.services.quality import timestamp_label, safe_url, normalized_key
from leilao_app.utils import parse_money

BASE_DIR = Path(__file__).resolve().parent
DISCLAIMER = "O Seach page Leilão organiza informações provenientes de fontes públicas. Antes de qualquer decisão, confirme valores, disponibilidade, condições, ocupação e documentação no edital e na fonte oficial."
ORDERS = ["Mais interessantes", "Maior desconto", "Menor preço", "Maior preço", "Mais recentes"]
ADVANCED_DEFAULTS = {"min_price": 0.0, "discount": 0, "source": "Todas", "modality": "Todas", "occupancy": "Todas", "financing": "Todos"}

def h(value):
    return html.escape("" if value is None else str(value), quote=True)

def money(value):
    value = parse_money(value)
    if value is None:
        return "Não informado"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def value_label(value, unit=""):
    return "Não informado" if value is None else f"{value:g}{unit}" if isinstance(value, (float, int)) else str(value)

def percent_label(value):
    if value is None:
        return "Desconto não informado"
    if value < 0:
        return f"{abs(value):.1f}% acima da avaliação".replace(".", ",")
    return f"{value:.1f}% abaixo da avaliação".replace(".", ",")

def analysis_class(score):
    return "unknown" if score is None else "good" if score >= 75 else "attention" if score >= 40 else "risk"

def render_photo(url, title, height=220, gallery=False):
    source = safe_url(url)
    fit = "contain" if gallery else "cover"
    image = f'<img src="{h(source)}" alt="{h(title)}" onload="document.getElementById(&quot;fallback&quot;).hidden=true" onerror="this.hidden=true;document.getElementById(&quot;fallback&quot;).hidden=false;document.getElementById(&quot;fallback&quot;).textContent=&quot;Imagem não disponível&quot;">' if source else ""
    markup = f"""<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>html,body{{margin:0;height:100%;font-family:system-ui,sans-serif}}figure{{margin:0;height:100%;display:grid;place-items:center;background:#eaf0f2;color:#526574;border-radius:12px;overflow:hidden;position:relative}}img{{width:100%;height:100%;object-fit:{fit};position:absolute;inset:0}}[hidden]{{display:none!important}}span{{padding:20px;font-size:15px;text-align:center}}</style></head>
    <body><figure aria-label="{h(title)}"><span id="fallback" role="status">{"Carregando imagem…" if source else "Imagem não disponível"}</span>{image}</figure></body></html>"""
    components.html(markup, height=height, scrolling=False)

def search_url(property_id=None):
    filters = st.session_state.get("applied", {})
    params = {key: str(value) for key, value in filters.items() if value not in (None, "", "Todos", "Todas", 0, 0.0)}
    if property_id is not None:
        params["imovel"] = property_id
    if st.session_state.get("searched"):
        params["busca"] = "1"
    return "?" + urlencode(params)

def favorite_button(item, prefix):
    label = "★ Favorito" if item["is_favorite"] else "♡ Favoritar"
    if st.button(label, key=f"{prefix}_favorite_{item['id']}", use_container_width=True):
        toggle_favorite(item["id"])
        st.rerun()

def render_property_card(item, prefix="result"):
    score = item["analysis"].overall
    score_text = f"{score}/100 · " if score is not None else ""
    facts = []
    for field, label in [("bedrooms", "quartos"), ("parking_spaces", "vagas"), ("built_area_m2", "m²")]:
        if item.get(field) is not None:
            facts.append(f"{value_label(item[field])} {label}")
    if not facts and item.get("land_area_m2"):
        facts.append(f"{value_label(item['land_area_m2'])} m² de terreno")
    image = item["images"][0] if item["images"] else None
    official = safe_url(item.get("official_url"))
    official_link = f'<a class="pl-official" href="{h(official)}" target="_blank" rel="noopener noreferrer">Ver oferta oficial ↗</a>' if official else ""
    markup = f"""
    <article class="pl-card">
      <div class="pl-body">
        <div class="pl-kind">{h(item.get('property_type') or 'Tipo não informado')}</div>
        <div class="pl-location">{h(item.get('city') or 'Cidade não informada')} / {h(item.get('state') or 'UF não informada')}</div>
        <div class="pl-muted">{h(item.get('neighborhood') or 'Bairro não informado')}</div>
        <div class="pl-price">{money(item.get('minimum_value'))}</div>
        <div class="pl-muted">Venda / lance inicial da etapa informada</div>
        <div class="pl-muted">Avaliação: {money(item.get('appraisal_value'))}</div>
        <div class="pl-discount">{percent_label(item.get('discount_percent'))}</div>
        <div class="pl-facts">{h(' • '.join(facts))}</div>
        <div class="pl-source">{h(item['source_label'])}</div>
        <div class="pl-muted">{h(item.get('auction_modality') or 'Modalidade não informada')} · {h(item.get('occupancy') or 'Ocupação não informada')}</div>
        <div class="pl-muted">Situação: {h(item.get('status') or 'Não informada')}</div>
        <div class="pl-analysis {analysis_class(score)}">{h(score_text + item['analysis'].classification)}</div>
        <a class="pl-link" href="{h(search_url(item['id']))}" target="_self">Ver detalhes</a>
        {official_link}
        <div class="pl-muted" style="margin-top:12px;font-size:12px">Atualizado em {timestamp_label(item.get('collected_at'))}</div>
      </div>
    </article>
    """
    with st.container(border=True):
        render_photo(image, "Foto do imóvel: " + (item.get("property_type") or "Imóvel") + " em " + (item.get("city") or "local não informado"))
        st.markdown(markup, unsafe_allow_html=True)
        favorite_button(item, prefix)

def render_cards(items, prefix):
    for offset in range(0, len(items), 3):
        columns = st.columns(3)
        for column, item in zip(columns, items[offset:offset + 3]):
            with column:
                render_property_card(item, prefix)

def empty_state():
    st.info("Nenhum imóvel encontrado com esses filtros. Tente outra cidade, aumente o preço máximo ou limpe os filtros adicionais.")
    if st.button("Limpar filtros"):
        st.query_params.clear()
        for key in ("applied", "advanced", "searched", "state_input", "city_input", "kind_input", "max_price_input"):
            st.session_state.pop(key, None)
        st.rerun()

@st.experimental_dialog("Mais filtros")
def advanced_filters(items):
    previous = st.session_state.get("advanced", ADVANCED_DEFAULTS)
    with st.form("advanced_form"):
        minimum = st.number_input("Valor mínimo (R$)", min_value=0.0, value=float(previous["min_price"]), step=10000.0)
        discount = st.slider("Desconto mínimo (%)", 0, 100, int(previous["discount"]))
        values = {}
        for key, label, field in [("source", "Fonte", "source_name"), ("modality", "Modalidade", "auction_modality"), ("occupancy", "Ocupação", "occupancy")]:
            options = ["Todas"] + sorted({item[field] for item in items if item.get(field)})
            selected = previous[key] if previous[key] in options else "Todas"
            values[key] = st.selectbox(label, options, index=options.index(selected), key="advanced_" + key)
        finances = ["Todos", "Sim", "Não"]
        finance = st.selectbox("Aceita financiamento", finances, index=finances.index(previous["financing"]))
        apply = st.form_submit_button("Aplicar filtros", use_container_width=True)
        if apply:
            maximum = st.session_state.get("max_price_input", 0)
            if maximum and minimum > maximum:
                st.error("O valor mínimo não pode ser maior que o preço máximo.")
            else:
                st.session_state["advanced"] = dict(min_price=minimum, discount=discount, financing=finance, **values)
                if st.session_state.get("searched"):
                    st.session_state["applied"].update(st.session_state["advanced"])
                st.session_state["results_page"] = 1
                st.rerun()
    st.caption("Preço máximo em zero significa sem limite. Campos desconhecidos não passam por filtros que exigem essa informação.")

def initialize_filters():
    if "advanced" in st.session_state:
        return
    params = st.query_params
    advanced = dict(ADVANCED_DEFAULTS)
    for key in ("source", "modality", "occupancy", "financing"):
        if key in params:
            advanced[key] = params[key]
    for key in ("min_price", "discount"):
        advanced[key] = max(0, parse_money(params.get(key)) or 0)
    advanced["discount"] = min(100, advanced["discount"])
    if advanced["financing"] not in ("Todos", "Sim", "Não"):
        advanced["financing"] = "Todos"
    st.session_state["advanced"] = advanced
    st.session_state["searched"] = params.get("busca") == "1"
    st.session_state["applied"] = {**advanced, "state": params.get("state", "Todos"), "city": params.get("city", "Todas"),
                                   "kind": params.get("kind", "Todos"), "max_price": max(0, parse_money(params.get("max_price")) or 0)}

def render_search(items):
    st.title("Encontre oportunidades em imóveis")
    st.write("Busque por localização, compare os dados e confira as condições na fonte oficial.")
    applied = st.session_state.get("applied", {})
    with st.container(border=True):
        columns = st.columns([1, 1.4, 1.2, 1.2])
        states = ["Todos", "SP", "MG", "PR", "SC"] + sorted({i["state"] for i in items if i.get("state")} - {"SP", "MG", "PR", "SC"})
        with columns[0]:
            state = st.selectbox("Estado", states, index=states.index(applied.get("state")) if applied.get("state") in states else 0, key="state_input")
        cities = ["Todas"] + sorted({i["city"] for i in items if i.get("city") and (state == "Todos" or i["state"] == state)})
        if st.session_state.get("city_input") not in cities:
            st.session_state["city_input"] = applied.get("city") if applied.get("city") in cities else "Todas"
        with columns[1]:
            city = st.selectbox("Cidade", cities, key="city_input")
        kinds = ["Todos"] + sorted({i["property_type"] for i in items if i.get("property_type")})
        with columns[2]:
            kind = st.selectbox("Tipo de imóvel", kinds, index=kinds.index(applied.get("kind")) if applied.get("kind") in kinds else 0, key="kind_input")
        with columns[3]:
            maximum = st.number_input("Preço máximo (R$)", min_value=0.0, value=float(applied.get("max_price", 0)), step=10000.0,
                                      help="Zero significa sem limite de preço.", key="max_price_input")
        actions = st.columns([1, 1, 2])
        with actions[0]:
            search = st.button("Buscar imóveis", type="primary", use_container_width=True)
        with actions[1]:
            if st.button("Mais filtros", use_container_width=True):
                advanced_filters(items)
        if search:
            filters = dict(state=state, city=city, kind=kind, max_price=maximum, **st.session_state["advanced"])
            try:
                filter_properties(items, filters)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["applied"] = filters
                st.session_state["searched"] = True
                st.session_state["results_page"] = 1
                st.query_params.clear()
                for key, value in filters.items():
                    st.query_params[key] = str(value)
                st.query_params["busca"] = "1"
    if st.session_state.get("searched"):
        try:
            results = filter_properties(items, st.session_state["applied"])
        except ValueError as exc:
            st.error(str(exc))
            return
        st.subheader(f"{len(results)} imóveis encontrados")
        st.caption("Resultados da base disponível. Não representa a totalidade dos imóveis da cidade.")
        order = st.selectbox("Ordenar por", ORDERS)
        results = sort_properties(results, order)
        if not results:
            empty_state()
            return
        pages = list(range(1, math.ceil(len(results) / 12) + 1))
        if st.session_state.get("results_page", 1) not in pages:
            st.session_state["results_page"] = 1
        page = st.selectbox("Página", pages, key="results_page") if len(pages) > 1 else 1
        render_cards(results[(page - 1) * 12:page * 12], "result")
    else:
        for title, selected, key in [
            ("Maiores descontos", sort_properties([i for i in items if (i.get("discount_percent") or 0) > 0], "Maior desconto")[:3], "discount"),
            ("Oportunidades interessantes", sort_properties([i for i in items if (i.get("opportunity_score") or 0) >= 75])[:3], "opportunity"),
            ("Imóveis recentes", sort_properties(items, "Mais recentes")[:3], "recent"),
        ]:
            st.subheader(title)
            if selected:
                render_cards(selected, key)
            else:
                st.caption("Ainda não há imóveis com dados suficientes para este destaque.")

def render_detail(property_id):
    item = load_detail(property_id)
    st.markdown(f'<a href="{h(search_url())}" target="_self">← Voltar aos resultados</a>', unsafe_allow_html=True)
    if not item:
        st.error("Imóvel não encontrado.")
        return
    if item["inactive"]:
        st.warning("Oferta não está mais disponível na fonte ou o prazo informado foi encerrado.")
    if item["data_quality"] == "legacy":
        st.warning("Registro antigo, pendente de revisão. Os dados abaixo não foram validados; confirme na fonte antes de usá-los.")
    images = item["images"] if item["data_quality"] != "legacy" else []
    selected_image = images[0] if images else None
    if len(images) > 1:
        index = st.selectbox("Fotos do imóvel", range(len(images)), format_func=lambda n: f"Foto {n + 1} de {len(images)}")
        selected_image = images[index]
    render_photo(selected_image, "Foto do imóvel em " + (item.get("city") or "local não informado"), height=400, gallery=True)
    st.title(item.get("property_type") or "Imóvel")
    st.subheader(f"{item.get('neighborhood') or 'Bairro não informado'} — {item.get('city') or 'Cidade não informada'}/{item.get('state') or '--'}")
    if item.get("address"):
        st.write(item["address"])
    st.caption("Atualizado em " + timestamp_label(item.get("collected_at")))
    if item.get("source_updated_at"):
        st.caption("Data da base informada pela fonte: " + item["source_updated_at"].strftime("%d/%m/%Y"))
    if item.get("collected_at") and item["collected_at"] < datetime.utcnow() - timedelta(days=7):
        st.info("Esta coleta tem mais de 7 dias. Confira a disponibilidade e os valores na fonte.")
    favorite_button(item, "detail")
    st.subheader("Preços")
    st.caption("Informação oficial da fonte" if item.get("data_quality", "").startswith("official") else "Informação importada; confirme na fonte.")
    columns = st.columns(3)
    columns[0].metric("Valor de venda / lance inicial", money(item.get("minimum_value")))
    columns[1].metric("Valor de avaliação informado pela fonte", money(item.get("appraisal_value")))
    difference = item["appraisal_value"] - item["minimum_value"] if item.get("appraisal_value") and item.get("minimum_value") else None
    columns[2].metric("Economia sobre avaliação", money(difference))
    st.write("**" + percent_label(item.get("discount_percent")) + "**")
    st.caption("Avaliação não é uma estimativa de preço de mercado.")
    st.subheader("Características")
    left, right = st.columns(2)
    with left:
        st.write("**Área construída / privativa:** " + value_label(item.get("built_area_m2"), " m²"))
        st.write("**Área do terreno:** " + value_label(item.get("land_area_m2"), " m²"))
        st.write("**Quartos:** " + value_label(item.get("bedrooms")))
        st.write("**Vagas:** " + value_label(item.get("parking_spaces")))
    with right:
        st.write("**Ocupação:** " + (item.get("occupancy") or "Não informado"))
        st.write("**Financiamento:** " + ("Aceita" if item.get("accepts_financing") is True else "Não aceita" if item.get("accepts_financing") is False else "Não informado"))
        st.write("**Situação:** " + (item.get("status") or "Não informado"))
        st.write("**Código:** " + str(item.get("source_internal_id") or "Não informado"))
    st.subheader("Modalidade e fonte")
    st.write(item.get("auction_modality") or "Não informado")
    st.write(item["source_label"])
    if item.get("auction_date"):
        st.write("**Data da etapa informada:** " + item["auction_date"].strftime("%d/%m/%Y às %H:%M"))
    if item.get("notes"):
        with st.expander("Condições e observações da oferta"):
            st.text(item["notes"])
    st.subheader("Análise Seach page Leilão")
    analysis = item["analysis"]
    score_text = f"{analysis.overall}/100 · " if analysis.overall is not None else ""
    st.markdown(f'<div class="pl-analysis {analysis_class(analysis.overall)}">{h(score_text + analysis.classification)}</div>', unsafe_allow_html=True)
    st.write(analysis.summary)
    for reason in analysis.reasons:
        st.write("• " + reason)
    if analysis.missing:
        st.caption("Informações pendentes: " + "; ".join(analysis.missing) + ".")
    st.caption("Indicador gerencial baseado nos dados disponíveis, não uma previsão de lucro. Não usamos estimativas de mercado ou qualidade presumida do bairro.")
    st.write("Verifique custos adicionais no edital.")
    st.caption("Podem existir ITBI, registro, condomínio, IPTU, desocupação, reforma, comissão, taxas e custos jurídicos.")
    with st.expander("Como o score é calculado"):
        st.write("Base de 35 pontos + desconto (limitado entre −35 e +50). Desocupado: +8; ocupado: −12; financiamento: +4 se aceita, −4 se não aceita; edital: +4; venda direta: +3; segunda praça: −5; judicial: −8; dívidas informadas: −10.")
        st.write("De 75 a 100: oportunidade interessante; de 40 a 74: analisar com atenção; abaixo de 40: alto risco / baixo atrativo. Informações operacionais ausentes, ocupação confirmada ou dívidas limitam a pontuação a 74. Sem preço, avaliação, cidade, UF ou tipo, não há score.")
    with st.expander("Simular custo total"):
        st.caption("Estimativa editável. Não altera os valores oficiais do imóvel. Custos em zero ainda não foram estimados.")
        estimates = []
        for label in ["Valor do imóvel", "ITBI estimado", "Registro", "Reforma", "Dívidas assumidas", "Comissão", "Outros"]:
            estimates.append(st.number_input(label + " (R$)", min_value=0.0, value=float(item.get("minimum_value") or 0) if label == "Valor do imóvel" else 0.0,
                                              step=500.0, key=f"estimate_{property_id}_{label}"))
        total = sum(estimates)
        st.metric("Custo estimado total", money(total))
        if item.get("appraisal_value"):
            st.metric("Diferença estimada para a avaliação", money(item["appraisal_value"] - total))
    st.subheader("Links")
    if safe_url(item.get("official_url")):
        st.link_button("Ver na fonte oficial", item["official_url"], use_container_width=True)
    elif safe_url(item.get("source_url")):
        st.link_button("Ver anúncio na fonte de coleta", item["source_url"], use_container_width=True)
    if safe_url(item.get("notice_url")):
        st.link_button("Ver edital", item["notice_url"], use_container_width=True)
    address = item.get("address")
    if address and item.get("city") and any(char.isdigit() for char in address) and item["data_quality"] != "legacy":
        query = ", ".join([address, item["city"], item.get("state") or ""])
        st.link_button("Ver localização", "https://www.google.com/maps/search/?api=1&query=" + quote(query))
    elif item.get("latitude") is not None and item.get("longitude") is not None and item["data_quality"] != "legacy":
        st.link_button("Ver localização", f"https://www.google.com/maps/search/?api=1&query={item['latitude']},{item['longitude']}")

def main():
    st.set_page_config(page_title="Seach page Leilão — Imóveis", page_icon="🏠", layout="wide")
    configure_logging()
    init_db()
    st.markdown("<style>" + (BASE_DIR / "leilao_app" / "ui.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
    st.markdown('<div class="pl-brand">Seach page Leilão</div>', unsafe_allow_html=True)
    initialize_filters()
    selected = st.query_params.get("imovel")
    if selected:
        try:
            property_id = int(selected)
        except ValueError:
            st.error("Código de imóvel inválido.")
        else:
            render_detail(property_id)
    else:
        page = st.radio("Navegação", ["Buscar imóveis", "Favoritos", "Administração"], horizontal=True, label_visibility="collapsed")
        if page == "Administração":
            from leilao_app.admin import render_admin, render_diagnostics
            st.title("Administração")
            render_diagnostics()
            with st.expander("Importar e atualizar fontes"):
                render_admin()
        elif page == "Favoritos":
            st.title("Seus favoritos")
            st.caption("Salvos neste projeto local.")
            favorites = [item for item in load_catalog(include_history=True) if item["is_favorite"]]
            if not favorites:
                st.info("Use Favoritar em um imóvel para encontrá-lo aqui.")
            render_cards(favorites, "favorite")
        else:
            render_search(load_catalog())
    st.markdown(f'<footer class="pl-disclaimer">{h(DISCLAIMER)}</footer>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
