from __future__ import annotations

from dataclasses import dataclass


TARGET_STATES = ("SP", "MG", "PR", "SC")


@dataclass(frozen=True)
class SourcePage:
    name: str
    url: str
    category: str
    states: tuple[str, ...] = TARGET_STATES
    automatic_level: str = "browser_capture"
    notes: str = ""


SOURCE_CATALOG: tuple[SourcePage, ...] = (
    # Agregadores com paginas estaduais.
    SourcePage("Leilao Imovel SP", "https://www.leilaoimovel.com.br/leilao-de-imoveis/sp", "agregador", ("SP",), "html_parser"),
    SourcePage("Leilao Imovel MG", "https://www.leilaoimovel.com.br/leilao-de-imoveis/mg", "agregador", ("MG",), "html_parser"),
    SourcePage("Leilao Imovel PR", "https://www.leilaoimovel.com.br/leilao-de-imoveis/pr", "agregador", ("PR",), "html_parser"),
    SourcePage("Leilao Imovel SC", "https://www.leilaoimovel.com.br/leilao-de-imoveis/sc", "agregador", ("SC",), "html_parser"),
    SourcePage("Leilao Imovel Indaiatuba", "https://www.leilaoimovel.com.br/leilao-de-imovel/indaiatuba-sp", "cidade", ("SP",), "html_parser"),
    SourcePage("Leilao Imovel Salto", "https://www.leilaoimovel.com.br/leilao-de-imovel/salto-sp", "cidade", ("SP",), "html_parser"),
    SourcePage("Portal Zuk SP", "https://www.portalzuk.com.br/leilao-de-imoveis/c/todos-imoveis/sp", "agregador", ("SP",)),
    SourcePage("Portal Zuk MG", "https://www.portalzuk.com.br/leilao-de-imoveis/c/todos-imoveis/mg", "agregador", ("MG",)),
    SourcePage("Portal Zuk PR", "https://www.portalzuk.com.br/leilao-de-imoveis/c/todos-imoveis/pr", "agregador", ("PR",)),
    SourcePage("Portal Zuk SC", "https://www.portalzuk.com.br/leilao-de-imoveis/c/todos-imoveis/sc", "agregador", ("SC",)),
    SourcePage("Lailo", "https://www.lailo.com.br/", "agregador"),
    SourcePage("Oportuno", "https://oportuno.com.br/", "agregador"),
    SourcePage("Sold Leiloes", "https://www.sold.com.br/", "agregador"),
    SourcePage("Superbid Exchange", "https://www.superbid.net/", "agregador"),
    # Bancos e paginas oficiais.
    SourcePage("Caixa busca", "https://venda-imoveis.caixa.gov.br/sistema/busca-imovel.asp?sltTipoBusca=imoveis", "banco"),
    SourcePage("Caixa lista", "https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp", "banco"),
    SourcePage("Banco do Brasil", "https://www.seuimovelbb.com.br/", "banco"),
    SourcePage("Santander Imoveis", "https://www.santanderimoveis.com.br/", "banco"),
    SourcePage("Itau Imoveis", "https://www.itau.com.br/imoveis-itau", "banco"),
    SourcePage("Bradesco Leiloes", "https://www.bradescocomercioeletronico.com.br/html/classic/produtos-servicos/leiloes/index.shtm", "banco"),
    # Leiloeiros/plataformas com imoveis recorrentes nos estados-alvo.
    SourcePage("Biasi Leiloes", "https://www.biasileiloes.com.br/", "leiloeiro", ("SP",)),
    SourcePage("Mega Leiloes", "https://www.megaleiloes.com.br/leiloes/imoveis", "leiloeiro"),
    SourcePage("Frazao Leiloes", "https://www.frazaoleiloes.com.br/leiloes/enforce", "leiloeiro"),
    SourcePage("Freitas Leiloeiro", "https://www.freitasleiloeiro.com.br/Home/Index", "leiloeiro"),
    SourcePage("E-leiloeiro", "https://www.e-leiloeiro.leilao.br/", "leiloeiro"),
    SourcePage("Eleiloeiro", "https://www.eleiloeiro.com.br/", "leiloeiro"),
    SourcePage("GL Leiloes", "https://glleiloes.com.br/", "leiloeiro"),
    SourcePage("Nogari Leiloes", "https://www.nogarileiloes.com.br/", "leiloeiro", ("PR", "SC")),
    SourcePage("Gilson Leiloes", "https://www.gilsonleiloes.com.br/", "leiloeiro", ("SC",)),
    SourcePage("WMS Leiloes", "https://www.wmsleiloes.com.br/", "leiloeiro", ("SC", "PR")),
    SourcePage("Sodre Santoro", "https://www.sodresantoro.com.br/leiloes/imoveis", "leiloeiro", ("SP",)),
    SourcePage("Milan Leiloes", "https://www.milanleiloes.com.br/", "leiloeiro", ("SP",)),
    SourcePage("Lance no Leilao", "https://www.lancenoleilao.com.br/", "leiloeiro"),
)


def get_capture_urls(states: list[str] | tuple[str, ...] | None = None, categories: list[str] | tuple[str, ...] | None = None) -> list[str]:
    selected_states = {state.upper() for state in states or TARGET_STATES}
    selected_categories = {category.lower() for category in categories or []}
    urls: list[str] = []
    for source in SOURCE_CATALOG:
        if selected_categories and source.category.lower() not in selected_categories:
            continue
        if not selected_states.intersection(source.states):
            continue
        urls.append(source.url)
    return list(dict.fromkeys(urls))


CAPTURE_SOURCE_URLS = get_capture_urls()
