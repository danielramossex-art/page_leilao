# Seach page Leilão — REVISÃO

Revisão de 08/09/2026. Aplicação disponível em http://localhost:8512.

## Resultado

O projeto existente foi mantido: Python, Streamlit, SQLAlchemy, SQLite, CLI, banco e históricos. A revisão concentrou a interface em busca, cards, detalhes e favoritos. Não houve reconstrução com outra stack, commit ou push.

- **Problemas encontrados:** 17 grupos registrados em REVISAO_INICIAL.md.
- **Problemas corrigidos/simplificados:** 16 grupos de interface, dados, score, persistência e operação.
- **Parcial:** integração automática das diversas fontes. A busca real foi validada com a Mega Leilões; CAIXA e Zuk apresentaram bloqueios externos. Não se afirma cobertura completa de bancos/leiloeiros.
- **Removido/simplificado:** sete abas públicas viraram busca, favoritos e administração; saíram mapa embutido, ranking duplicado, métricas de scores especulativos, controles decorativos e agendador por sessão. Parsers por posição monetária e restritos a Indaiatuba foram substituídos. Dependências Folium foram retiradas.
- **Melhorias:** filtros básicos e adicionais, paginação, ordenação, link individual, galeria com fallback real, favoritos persistentes, simulador separado, timestamps, fonte/instituição distintas, score anulável e backup de migração.

## Validação solicitada

O status abaixo se refere aos fluxos testados e à amostra real de Jundiaí, não à totalidade do mercado ou das fontes.

| Item | Resultado | Evidência / alcance |
|---|---|---|
| Busca | OK | 5 resultados reais em SP/Jundiaí; teste de busca sem resultados também passou. |
| Estado/Cidade | OK | Seleção dependente de UF/cidade no navegador; comparação sem distinção de acentos no serviço. |
| Imagens | OK | 5 fotos carregadas nos resultados; galerias de 3 imóveis; imagem de outro lote recusada; erro de imagem mostra placeholder. |
| Preço | OK | 3 valores comparados com os detalhes oficiais e com a interface local. |
| Avaliação | OK | 3 avaliações explicitamente identificadas na fonte; nos 2 registros só de listagem, permanece ausente. |
| Desconto | OK | Fórmula sobre preço e avaliação; 0% atual nos 3 exemplos, sem usar desconto futuro como vigente. |
| Localização | OK | Jundiaí/SP em todos; bairro e endereço dos 3 detalhes conferidos; sem inventar endereços. |
| Score | OK | 16 testes abrangem regressões; os 2 imóveis sem avaliação não recebem score. Nos 3 detalhes, indicador de baixo atrativo coerente com o desconto atual zero e informações operacionais ausentes. |
| Links oficiais | OK | Cada card contém link individual; 3 ofertas oficiais abertas e vinculadas aos detalhes locais. |
| Mobile | OK | Viewport real 375×900 e orientação 812×375, sem overflow horizontal; modal e cards testados. |
| Build | PASS | Compilação Python de app, módulos, scripts e testes. Build Docker não executado. |
| Tests | PASS | 16 testes unitários/regressão, comparação de fontes e teste Selenium de busca, fotos, detalhes, favoritos, filtros e estado vazio. |

## Comparação com a fonte

| Código oficial | Preço atual na fonte e no Seach page Leilão | Avaliação na fonte e no Seach page Leilão | Desconto atual | Fotos de detalhe |
|---|---:|---:|---:|---:|
| [J127385](https://www.megaleiloes.com.br/imoveis/casas/sp/jundiai/casas-em-terreno-de-506-m2-vila-santana-ll-jundiai-sp-j127385) | R$ 596.025,74 | R$ 596.025,74 | 0% | 5 |
| [J128502](https://www.megaleiloes.com.br/imoveis/apartamentos/sp/jundiai/apartamento-95-m2-02-vagas-vila-das-hortencias-jundiai-sp-j128502) | R$ 648.396,00 | R$ 648.396,00 | 0% | 6 |
| [J128529](https://www.megaleiloes.com.br/imoveis/apartamentos/sp/jundiai/apartamento-77-m2-01-vaga-jardim-messina-jundiai-sp-j128529) | R$ 538.051,41 | R$ 538.051,41 | 0% | 10 |

Os descontos anunciados de 30%, 40% e 50% são de segunda praça futura. As datas e condições futuras aparecem nas observações. A avaliação não foi deduzida do primeiro preço: foi extraída do campo “Valor de Avaliação” dos detalhes oficiais.

O imóvel J128529 apresenta divergência entre título e descrição sobre vagas; o campo foi mantido desconhecido. Banco citado em hipoteca/processo não é assumido como vendedor. Financiamento e ocupação não foram preenchidos por suposição.

## Arquivos alterados ou adicionados

| Arquivo | Alteração |
|---|---|
| app.py | Home com quatro campos, busca, filtros em modal, cards, paginação/ordenação, detalhes por URL, favoritos, galeria, simulador e disclaimer. |
| leilao_app/ui.css | Hierarquia visual, contraste, cards, botões e layout responsivo. |
| leilao_app/admin.py | Administração existente extraída da Home; diagnóstico e registros legados acessíveis. |
| leilao_app/services/catalog.py | Consulta sem N+1 de imagens, filtros, ordenação, favoritos e adaptação dos dados para a interface. |
| leilao_app/services/quality.py | Normalização de cidade/UF, números desconhecidos, ocupação, financiamento, URLs, timestamps e disponibilidade. |
| leilao_app/services/scoring.py | Indicador inteiro e anulável, motivos, dados pendentes e limites de classificação. |
| leilao_app/services/neighborhood.py | Removida classificação especulativa pelo nome do bairro; compatibilidade mantida. |
| leilao_app/services/collector.py | Atualização de score, campos explicitamente desconhecidos, imagens preservadas quando omitidas, identidade sem preço e histórico de status. |
| leilao_app/services/importer.py | Campos nomeados, CSV CAIXA, UTF-8/CP1252, TSV, imagens, booleans e falhas explícitas de importação. |
| leilao_app/services/parsing.py | Parser validado Mega, lista oficial CAIXA e JSON-LD estritamente vinculado à URL do imóvel. |
| leilao_app/connectors/base.py | Coleta limitada a links de detalhe e parsers validados, sem transformar menu/preços soltos em imóvel. |
| leilao_app/connectors/caixa.py | Uso da exportação oficial em vez de heurística HTML de valores. |
| leilao_app/services/apify_importer.py | Campos adicionais e token enviado no cabeçalho, não na URL. Integração externa não executada. |
| leilao_app/services/browser_capture.py | Validação contra páginas de bloqueio e preservação da URL da captura. |
| leilao_app/services/alerts.py | Compatibilidade com score anulável; lógica anterior de segunda praça preservada. |
| leilao_app/models.py | Novos campos anuláveis de instituição, fonte, características, financiamento, score, qualidade e atualização; favorito. |
| leilao_app/db.py | Migração aditiva e idempotente com backup SQLite e fechamento correto dos arquivos. |
| leilao_app/utils.py | Dinheiro finito, milhar brasileiro, desconto negativo, data ISO com horário e inferências conservadoras. |
| requirements.txt | Removidas dependências do mapa embutido. |
| scripts/start_current.ps1 | Reinício restrito ao caminho deste projeto e porta indicada; verificação de saúde e logs. |
| scripts/inspect_browser.py | Captura de evidências públicas da listagem durante a auditoria. |
| scripts/inspect_markup.py | Captura dos três detalhes oficiais usados na comparação. |
| scripts/validate_review.py | Comparação repetível das capturas e importação explícita da amostra validada. |
| scripts/validate_browser.py | Teste real de navegador, incluindo 375 px, fotos quebradas e persistência de favoritos. |
| scripts/review_git.py | Revisão de arquivos e padrões de secrets, sem mostrar valores sensíveis ou alterar o Git. |
| tests/test_core.py | Regressões de valores, score, persistência, filtros e bloqueios. |
| tests/test_parsing_regressions.py | Fotos de outro lote, praça futura, identidade JSON-LD e backup/migração. |
| .gitignore | Exclusão de backups e evidências locais. |
| .dockerignore | Exclusão de banco, capturas, credenciais e diretórios locais no contexto Docker. |
| README.md | Instruções e comportamento atualizados. |
| docs/SOURCES.md | Matriz honesta de suporte/validação e links comparados. |
| docs/CAPTURE_SOURCES.md | Catálogo preservado e instruções de parser corrigidas. |
| docs/REVISAO_INICIAL.md | Auditoria registrada antes da alteração de código. |
| docs/REVISAO_FINAL.md | Este relatório. |
| docs/COMMIT_MESSAGE.txt | Mensagem de commit preparada, ainda não utilizada. |

Também aparecem no Git alterações **preexistentes**, preservadas sem nova edição nesta revisão: leilao_app/sources.py e leilao_app/connectors/leiloeiros.py. Os demais arquivos que já tinham alterações locais foram integrados às correções; não houve reset.

## Banco e evidências

- Banco e históricos preservados; backup em data/backups/.
- Registros antigos potencialmente incorretos permanecem identificados como legados, fora da busca ativa até revisão/importação confiável.
- Amostra real adicionada à base local: cinco imóveis da Mega Leilões em Jundiaí, três com detalhes verificados.
- Comparações e testes de navegador: data/validation/source_comparison.json e browser_report.json.
- Capturas desktop/mobile e HTML da fonte: data/validation/. Não serão enviados ao Git.
- O novo opportunity_score é anulável e é o indicador usado pela interface. Colunas antigas de subscore permanecem por compatibilidade com o histórico; não são exibidas como avaliação válida.

## Limitações que permanecem explícitas

1. Coleta automática completa de CAIXA, Zuk, Santander, Bradesco, Itaú, Frazão, Biasi e Sodré não foi validada. Suporte por catálogo/importação foi mantido; detalhes em SOURCES.md.
2. Ausência numa coleta parcial ou bloqueada não permite declarar uma oferta retirada. A aplicação usa status explícito e prazo final conhecido; a fonte oficial ainda deve ser consultada.
3. A base de outras cidades/estados precisa de reimportação confiável; a revisão não promoveu os registros antigos a “dados corretos”.
4. Apify e PostgreSQL não foram testados; o build Docker não foi executado. XLS antigo depende de xlrd; CSV/HTML foram os caminhos exercitados.
5. Busca salva, comparador e estimativa de mercado não foram implementados; os dois primeiros não eram prioridade e não existe base confiável para a última.

## Git

Revisados status, diff, formatação e padrões de secrets. .env não rastreado; banco, backups e evidências fora do Git. Nenhuma credencial detectada nas alterações. Essa verificação não equivale a uma auditoria de segurança completa.

Mensagem de commit preparada em COMMIT_MESSAGE.txt. Envio ao Git autorizado pelo usuário após a revisão, com o nome da aplicação alterado para **Seach page Leilão**.
