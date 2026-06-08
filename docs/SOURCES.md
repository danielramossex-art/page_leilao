# Fontes de Dados

Data de referência deste projeto: 2026-06-08.

## Caixa Econômica Federal

- URL inicial: `https://venda-imoveis.caixa.gov.br/sistema/busca-imovel.asp`
- Método: scraping defensivo de HTML público.
- API pública documentada: não identificada para consulta ampla de imóveis.
- Manutenção futura: alta. O portal usa ASP e pode mudar parâmetros, sessão, cookies e marcação.
- Observação: em leilão/licitação, a Caixa direciona o usuário para leiloeiros oficiais indicados no edital.

## Banco do Brasil

- URL inicial: `https://www.seuimovelbb.com.br/`
- Método: scraping defensivo de HTML público.
- API pública documentada: não identificada.
- Manutenção futura: média/alta. O portal pode usar conteúdo dinâmico.

## Santander

- URLs iniciais:
  - `https://www.santanderimoveis.com.br/`
  - `https://www.santander.com.br/hotsite/santanderimoveis/`
- Método: scraping defensivo de HTML público.
- API pública documentada: não identificada.
- Manutenção futura: alta. Parte dos leilões pode ocorrer em leiloeiros parceiros.

## Itaú

- URL inicial: `https://www.itau.com.br/imoveis-itau`
- Método: scraping defensivo de HTML público.
- API pública documentada: não identificada.
- Manutenção futura: média/alta. A página pode direcionar para leiloeiros parceiros e editais em PDF.

## Leiloeiros oficiais

- URLs iniciais:
  - `https://www.megaleiloes.com.br/leiloes/imoveis`
  - `https://www.zuk.com.br/imoveis`
  - `https://www.leilaovip.com.br/`
  - `https://www.freitasleiloeiro.com.br/leiloes/imoveis`
- Método: scraping defensivo de HTML público.
- API pública documentada: varia por leiloeiro; não presumida.
- Manutenção futura: alta, pois cada leiloeiro tem regras, termos, marcação e proteção próprios.

## Leilão Imóvel via Apify

- URLs iniciais:
  - `https://www.leilaoimovel.com.br/leilao-de-imoveis/sp`
  - `https://www.leilaoimovel.com.br/leilao-de-imoveis/mg`
  - `https://www.leilaoimovel.com.br/leilao-de-imoveis/pr`
  - `https://www.leilaoimovel.com.br/leilao-de-imoveis/sc`
- Método: API autorizada via Apify, configurada por `APIFY_TOKEN`.
- Motivo: o site direto bloqueia coleta local por `robots.txt`; o projeto não tenta contornar esse bloqueio.
- Manutenção futura: média. O schema de retorno do ator Apify pode mudar e o normalizador aceita múltiplos nomes de campos.

## OpenStreetMap / Nominatim

- Uso: geocoding de endereços quando disponível.
- Método: API pública Nominatim.
- Restrições: respeitar política de uso, baixa frequência e cache local. O projeto aplica pausa entre chamadas e cache HTTP.

## Regras implementadas

- `robots.txt` é consultado antes da requisição.
- páginas de CAPTCHA/bloqueio anti-bot, como Radware Bot Manager, são detectadas e não são gravadas como imóveis;
- Cache local reduz acessos repetidos.
- Retry com backoff reduz falhas transitórias.
- Limite por domínio evita rajadas.
- Campos ausentes são salvos como `Não informado` ou `NULL`.
- Débitos e modalidade são inferidos por texto do anúncio/edital quando disponível:
  - texto com débitos, IPTU, condomínio, ônus ou laudêmio: `Com dívidas`;
  - texto indicando ausência de débitos/ônus: `Sem dívidas`;
  - ausência de evidência: `Não informado`;
  - texto judicial/processo/vara: `Judicial`;
  - texto extrajudicial/alienação fiduciária: `Extrajudicial`.
