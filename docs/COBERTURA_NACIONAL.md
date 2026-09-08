# Seach page Leilão — cobertura nacional

Revisão em 08/09/2026. A restrição a SP/MG/PR/SC foi removida dos filtros, normalização, conectores e seleção das fontes. Jundiaí permanece somente como amostra de regressão, filtrada pela Mega Leilões.

A lista oficial nacional da CAIXA (Lista_imoveis_Geral.csv), obtida por HTTP 200, contém 25.050 ofertas e informa geração em 04/09/2026. Todas foram importadas, preservando históricos. Com as cinco ofertas anteriores, o catálogo possui 25.055 registros publicados, nas 27 UFs, com resultados nas 27 capitais.

Validação: 25.050 registros comparados com o CSV oficial quanto a preço, avaliação, cidade, UF e link. 18 testes automatizados aprovados. Compilação Python aprovada. Navegador aprovado para Manaus (183), Salvador (315), Brasília (62), Rio de Janeiro (3.588) e Porto Alegre (267), mais verificação de largura mobile de 375 px.

O CSV não fornece imagens. Esses registros exibem placeholder; nenhuma foto foi inventada. A conferência nacional foi feita contra a lista oficial, não contra 25.050 páginas individuais. Não há promessa de disponibilidade em tempo real. Os registros locais não são enviados ao Git; uma instalação nova precisa executar a coleta/importação.

Alterações: geography.py centraliza as 27 UFs/capitais; app.py inclui todas as UFs e texto nacional; utils.py e quality.py reconhecem nomes nacionais e acentos das capitais; sources.py acrescenta rotas estaduais oficiais; conectores/base.py aceita todas as siglas; conectores/caixa.py usa lista Geral; Apify e CLI recebem abrangência nacional. Scripts de importação e validação nacional adicionados; testes antigos limitam sua amostra pela fonte. README e SOURCES atualizados. .gitignore exclui arquivos transitórios do SQLite.

Commit e envio ao Git autorizados pelo usuário após a validação. Mensagem: fix: amplia busca e coleta para todo o Brasil
