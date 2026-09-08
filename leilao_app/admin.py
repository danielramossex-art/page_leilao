from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import select, func, or_
from leilao_app.db import session_scope
from leilao_app.models import Property, CollectionRun, CollectionError
from leilao_app.services.importer import import_inbox, import_properties_csv
from leilao_app.services.apify_importer import DEFAULT_URLS, import_from_apify
from leilao_app.services.browser_capture import DEFAULT_CAPTURE_URLS, capture_and_import
from leilao_app.services.collector import run_collection
from leilao_app.sources import SOURCE_CATALOG, TARGET_STATES, get_capture_urls
BASE_DIR = Path(__file__).resolve().parents[1]

def render_admin() -> None:
    st.write("**Importação por pasta**")
    st.caption("Coloque arquivos .csv, .xlsx ou .html em data/inbox. O botão abaixo ou o worker separado importa, pontua e move para data/processed.")
    if st.button("Importar pasta inbox agora", use_container_width=True):
        result = import_inbox()
        st.cache_data.clear()
        st.success(f"Inbox processado: {result['files']} arquivo(s), {result['saved']} imóvel(is) salvos, {result['failed']} falha(s).")
        st.rerun()

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

    st.write("**Coleta automática autorizada via API**")
    st.caption("Configure APIFY_TOKEN no .env para coletar leilaoimovel.com.br com seu provedor contratado.")
    apify_urls = st.text_area("URLs para coleta Apify", value="\n".join(DEFAULT_URLS), height=90)
    if st.button("Coletar via Apify", use_container_width=True):
        try:
            urls = [line.strip() for line in apify_urls.splitlines() if line.strip()]
            result = import_from_apify(urls)
            st.cache_data.clear()
            st.success(f"Coleta Apify concluída: {result['saved']} registros salvos de {result['rows']} retornados.")
            st.rerun()
        except Exception as exc:
            st.error(f"Falha na coleta Apify: {exc}")

    st.write("**Capturar página aberta no navegador**")
    st.caption("Abre a URL no Chrome, salva o HTML em data/inbox e importa os imóveis encontrados.")
    capture_states = st.multiselect("Estados para captura", list(TARGET_STATES), default=list(TARGET_STATES))
    capture_categories = st.multiselect(
        "Tipos de fonte",
        sorted({source.category for source in SOURCE_CATALOG}),
        default=["agregador", "banco", "cidade", "leiloeiro"],
    )
    selected_capture_urls = get_capture_urls(capture_states, capture_categories) or DEFAULT_CAPTURE_URLS
    browser_urls = st.text_area(
        "URLs para captura por navegador",
        value="\n".join(selected_capture_urls),
        height=180,
    )
    if st.button("Capturar páginas e importar", use_container_width=True):
        try:
            urls = [line.strip() for line in browser_urls.splitlines() if line.strip()]
            result = capture_and_import(urls, headless=False)
            st.cache_data.clear()
            st.success(
                f"Captura concluída: {result['captured']} página(s), "
                f"{result['saved']} imóvel(is) salvos, {result['failed']} falha(s)."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Falha ao capturar/importar páginas: {exc}")



def render_diagnostics():
    with session_scope() as session:
        legacy = session.scalar(select(func.count(Property.id)).where(or_(Property.data_quality == "legacy", Property.data_quality.is_(None)))) or 0
        runs = session.scalars(select(CollectionRun).order_by(CollectionRun.id.desc()).limit(30)).all()
        rows = [{"Fonte": r.source, "Sucesso": r.success, "Encontrados": r.items_found,
                 "Salvos": r.items_saved, "Data": r.finished_at} for r in runs]
    st.info(f"{legacy} registros legados preservados para revisão, fora da busca pública. Reimporte dados confirmados para atualizá-los.")
    with st.expander("Registros legados / histórico"):
        with session_scope() as session:
            props = session.scalars(select(Property).where(or_(Property.data_quality == "legacy", Property.data_quality.is_(None))).order_by(Property.city, Property.id)).all()
            st.dataframe(pd.DataFrame([{"Código": p.id, "Cidade": p.city, "Fonte": p.source,
                                       "Detalhes": f"?imovel={p.id}"} for p in props]), hide_index=True, use_container_width=True)
    st.caption("CAIXA: lista CSV oficial; Mega Leilões: HTML validado; demais fontes: CSV ou dados estruturados compatíveis. Bloqueios externos não são contornados.")
    st.subheader("Últimas coletas")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with st.expander("Falhas recentes de coleta"):
        import re
        with session_scope() as session:
            errors = session.scalars(select(CollectionError).order_by(CollectionError.id.desc()).limit(30)).all()
            sanitized = []
            for error in errors:
                message = re.sub(r"(token|api_key|password)=([^&\s]+)", r"\1=[oculto]", error.error_message, flags=re.I)
                sanitized.append({"Data": error.occurred_at, "Fonte": error.source, "Falha": message})
        st.dataframe(pd.DataFrame(sanitized), hide_index=True, use_container_width=True)
    if st.button("Executar conectores configurados"):
        with st.spinner("Atualizando fontes..."):
            result = run_collection()
        st.cache_data.clear()
        if result["errors"]:
            st.warning(f"{result['items_saved']} imóveis salvos; {result['errors']} fontes com falha. A disponibilidade das fontes que falharam não foi alterada.")
        else:
            st.success(f"{result['items_saved']} imóveis salvos.")
