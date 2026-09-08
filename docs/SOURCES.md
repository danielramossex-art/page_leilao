# Fontes e qualidade dos dados

Revisão: 08/09/2026.

| Fonte | Caminho mantido | Validação nesta revisão |
|---|---|---|
| CAIXA | CSV oficial e importação de campos nomeados | Lista nacional Geral respondeu HTTP 200 em 08/09/2026 com 25.050 registros nas 27 UFs. CSV sem fotos; detalhes continuam sujeitos à disponibilidade e a bloqueios da fonte. |
| Mega Leilões | HTML de listagem e detalhe / CSV | 5 ofertas reais em Jundiaí, 3 detalhes comparados, fotos vinculadas ao lote e carregadas no navegador. |
| Santander | Conector/catálogo, CSV, JSON-LD compatível | Automação externa não validada. |
| Bradesco | Catálogo, CSV, JSON-LD compatível | Automação externa não validada. |
| Itaú | Conector/catálogo, CSV, JSON-LD compatível | Automação externa não validada. |
| Portal Zuk | Catálogo, CSV, JSON-LD compatível | Listagem acessível pela ferramenta web; navegador local bloqueado. Nenhum resultado inventado. |
| Frazão, Biasi, Sodré Santoro | Catálogo, CSV, JSON-LD compatível | Automação externa não validada. |
| Banco do Brasil e demais leiloeiros | Catálogo/conectores existentes, CSV | Layouts desconhecidos são recusados, sem fallback monetário por posição. |
| Leilão Imóvel / Apify | CSV e normalizador da API opcional | API exige configuração do usuário. HTML antigo por heurística foi retirado da importação automática. |

## Critérios

Uma URL no catálogo não garante cobertura automática. Cada fonte pode exigir atualização do parser, acesso assistido, exportação oficial ou configuração externa.

Fotos devem vir do registro específico. Mega usa somente imagens cujo caminho contém o código do lote, com prioridade para a imagem principal oficial. Os outros caminhos aceitam apenas URLs fornecidas no próprio registro importado ou no JSON-LD correspondente à URL do imóvel.

Preço de primeira praça não é automaticamente avaliação. Desconto de segunda praça futura não é desconto vigente. Ocupação, financiamento e dívidas precisam de informação explícita; menção genérica a IPTU ou condomínio não prova dívida.

Instituição e fonte são campos separados: a mera menção a um banco numa hipoteca ou processo não transforma o banco em vendedor da oferta.

Falhas HTTP, CAPTCHA, robots.txt e listas vazias não indicam retirada de imóveis. Status explícito e data final conhecida são preservados; não há varredura completa e garantida de disponibilidade em todas as fontes.

## Casos comparados

- [J127385 — Vila Santana II](https://www.megaleiloes.com.br/imoveis/casas/sp/jundiai/casas-em-terreno-de-506-m2-vila-santana-ll-jundiai-sp-j127385): preço/avaliação R$ 596.025,74; primeira praça 01/10/2026, segunda 22/10/2026.
- [J128502 — Vila das Hortências](https://www.megaleiloes.com.br/imoveis/apartamentos/sp/jundiai/apartamento-95-m2-02-vagas-vila-das-hortencias-jundiai-sp-j128502): preço/avaliação R$ 648.396,00; primeira praça 26/10/2026, segunda 16/11/2026.
- [J128529 — Jardim Messina](https://www.megaleiloes.com.br/imoveis/apartamentos/sp/jundiai/apartamento-77-m2-01-vaga-jardim-messina-jundiai-sp-j128529): preço/avaliação R$ 538.051,41; primeira praça 29/10/2026, segunda 18/11/2026. A descrição diverge do título sobre vagas; o campo fica desconhecido.

Os três têm desconto atual calculado de 0%, e não os 30%, 40% e 50% anunciados para a segunda praça. Avaliação e oferta foram comparadas como campos distintos, apesar de seus valores atuais coincidirem.

Evidências completas e capturas permanecem localmente em data/validation/, fora do Git.
