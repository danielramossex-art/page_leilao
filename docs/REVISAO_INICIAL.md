# Page Leilão — diagnóstico antes das alterações

Auditoria em 08/09/2026. Código e banco existentes inspecionados antes de modificar a aplicação.

## Estrutura e o que preservar

- Frontend: `app.py`, Streamlit 1.35, CSS/HTML próprios. Sete abas, sem rotas HTTP próprias; detalhes dependem de session_state e outra aba.
- Backend: serviços Python, CLI, conectores HTML, importação CSV/Excel/HTML e API Apify. Não há API REST separada.
- Banco: SQLite local com SQLAlchemy, 566 imóveis, 746 imagens, históricos de preços/status/score, alertas e execuções. 12 imóveis demonstrativos. Preservar registros e históricos.
- Fontes: CAIXA, BB, Santander, Itaú e leiloeiros via conectores; Bradesco, Zuk, Mega, Frazão, Biasi e Sodré constam também do catálogo de captura.
- Funcionam: servidor local, ORM, persistência, importação tabular básica, seleção UF/cidade com dados existentes, cards, CLI, cache HTTP, favoritos ainda inexistentes.
- Parciais: captura assistida, parsers HTML, coleta por fontes dinâmicas, imagens, data/status, filtros limitados, detalhes com navegação indireta. Apify exige configuração externa; não foi executado na auditoria.

## Problemas identificados

1. Parsers oficiais e detalhe do agregador limitados a Indaiatuba; deixam outras cidades sem importação.
2. Valores monetários interpretados por posição; avaliação pode ser confundida com lance de primeira praça, e preço repetido como avaliação.
3. Desconto armazenado pode divergir dos preços e valores negativos são truncados para zero.
4. Extração de todas as imagens da página mistura logos, recomendações e galeria; falta fallback da imagem principal para a primeira foto.
5. Score penaliza “Desocupado” como “Ocupado”, pontua dados insuficientes e inventa liquidez/localização pela palavra “Jardim” ou “Centro”.
6. Atualização de imóvel existente não persiste o novo score. Importação sem imagens apaga fotos anteriores.
7. Fingerprint inclui preço; imóvel sem código pode duplicar após alteração de preço.
8. Ocupação, financiamento, quartos, vagas e instituição não têm representação completa e separada.
9. Datas ISO perdem horário; datas de primeira praça e termos soltos nas observações encerram anúncios indevidamente.
10. Coletas vazias e exceções ignoradas podem aparecer como sucesso.
11. Home sobrecarregada com métricas, sete abas, mapas/rankings duplicados, botões decorativos e engenharia da coleta.
12. Não há busca explícita, preço máximo, ordenação acessível, paginação ou favoritos.
13. Diagnóstico Admin está após return, portanto inacessível.
14. Scheduler iniciado por sessão do navegador pode duplicar trabalhos.
15. Registros antigos não indicam confiabilidade/frescor; exemplos podem aparecer como ofertas.
16. Débitos são inferidos da mera menção de IPTU/condomínio e recebem o primeiro preço da página como dívida.
17. Não há suíte de testes; container copia arquivos locais potencialmente sensíveis por ausência de .dockerignore.

## Verificação inicial dos dados

16 registros de Jundiaí/SP no banco, provenientes do agregador. Preços não conferidos não serão tratados como verificados. Consulta web de dois códigos CAIXA (8787712435100 e 1555531415532) informa indisponibilidade; consulta HTTP local de detalhe recebeu bloqueio, o que não equivale a indisponibilidade.

Lista pública CAIXA SP acessível por HTTP 200, geração 04/09/2026, com colunas identificadas de preço, avaliação, financiamento e link. Será priorizada para corrigir dados. Não se inferirá retirada de uma oferta a partir de erro de rede, CAPTCHA, captura parcial ou mera ausência em busca.

## Decisão de implementação

Manter Streamlit, SQLAlchemy, banco, CLI, históricos e caminhos de importação. Simplificar a navegação para busca, favoritos e administração; detalhes por link direto. Substituir o score especulativo por indicador transparente e anulável. Migração aditiva com backup; dados legados sem validação ficam identificados para revisão, preservados no histórico. Validar regras por testes e fluxo real SP/Jundiaí, inclusive mobile. Sem commit/push automático.

Alterações locais preexistentes em app.py, docs/CAPTURE_SOURCES.md, conectores/leiloeiros, db, alerts, browser_capture, collector, importer, sources e utils serão preservadas ou integradas às correções, sem reset.
