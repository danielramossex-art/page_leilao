# Seach page Leilão

Aplicação local existente em Python + Streamlit para encontrar imóveis de bancos e leiloeiros, comparar preço e avaliação e examinar uma análise simples. Não é uma recomendação financeira.

## Executar

~~~powershell
pip install -r requirements.txt
python -m leilao_app.cli init-db
.\scripts\start_current.ps1 -Port 8512
~~~

Abra http://localhost:8512. O script reinicia apenas o servidor deste projeto na porta informada. Alternativa: python -m streamlit run app.py.

A aplicação usa SQLite por padrão. Preserve seu .env; não copie o exemplo sobre uma configuração existente. DATABASE_URL pode apontar para outro banco compatível com SQLAlchemy. A revisão foi testada com SQLite.

## Uso

1. Selecione estado, cidade, tipo e preço máximo. Zero no filtro de preço significa sem limite.
2. Clique em **Buscar imóveis**. Valores mínimo, desconto, fonte, modalidade, ocupação e financiamento ficam em **Mais filtros**.
3. Ordene por interesse, desconto, preço ou data. Resultados usam cards e paginação de 12 itens.
4. **Ver detalhes** abre um endereço próprio (?imovel=...) com galeria, valores, localização, análise, edital e fonte.
5. Favoritos ficam no banco local, compartilhados por quem usa esta instalação. Não há sistema de contas.
6. O simulador usa estimativas editáveis separadas dos dados da fonte.

A interface não inicia coletas nem serviços pagos ao abrir a página. Administração reúne importação e diagnóstico. Para coleta agendada, execute separadamente:

~~~powershell
python -m leilao_app.scheduler_worker
~~~

## Dados e fontes

- CAIXA: parser de exportação CSV oficial com cabeçalhos; valida a estrutura e recusa páginas de bloqueio.
- Mega Leilões: parser validado de listagens e detalhes, fotos limitadas ao código do lote, preços por praça e avaliação identificada.
- Santander, Bradesco, Itaú, Zuk, Frazão, Biasi, Sodré Santoro e demais fontes do catálogo continuam aceitos por importação de campos nomeados. HTML estruturado é aceito quando a fonte publica JSON-LD do imóvel com URL correspondente, endereço e oferta em BRL. Isso **não significa coleta automática validada em todas as fontes**.
- Apify continua opcional, configurado por APIFY_TOKEN e APIFY_LEILAOIMOVEL_ACTOR_ID. Sua execução não foi validada nesta revisão.
- Nenhuma foto genérica é procurada. Falha ou ausência de imagem exibe **Imagem não disponível**.
- Uma coleta vazia, CAPTCHA, bloqueio ou erro de rede não retira imóveis. Encerramento é baseado em status explícito ou data final conhecida.
- Preços sem avaliação não recebem desconto calculado nem score. Preço acima da avaliação gera diferença negativa, não desconto zero inventado.
- Dados legados anteriores à revisão ficam preservados, identificados como legacy, fora dos resultados ativos até reimportação confiável. Estão acessíveis na administração/histórico.
- A migração é aditiva e cria backup SQLite em data/backups/ antes de adicionar colunas.

Importação:

~~~powershell
python -m leilao_app.cli import-csv --file caminho\imoveis.csv
python -m leilao_app.cli import-inbox
python -m leilao_app.cli collect --source caixa
python -m leilao_app.cli capture-url --url URL_OFICIAL --headless
~~~

A pasta data/inbox aceita CSV, TSV, XLSX, XLS (requer xlrd) e HTML reconhecido. Layout desconhecido vai para data/failed em vez de aparecer como sucesso. O CSV de samples/ é demonstrativo, não deve ser usado como oferta real.

Campos adicionais opcionais: institution, source_name, official_url, bedrooms, parking_spaces, accepts_financing, status, ends_at, source_updated_at. Use células vazias para dados desconhecidos, não zero. Imagens podem ser separadas por |.

## Análise Seach page Leilão

Score inteiro entre 0 e 100, baseado apenas nos dados disponíveis. Base 35 + desconto limitado entre −35 e +50 pontos; desocupação +8, ocupação −12; financiamento +4/−4; edital +4; venda direta +3, segunda praça −5 ou judicial −8; dívidas explicitamente informadas −10.

75–100: oportunidade interessante; 40–74: analisar com atenção; 0–39: alto risco/baixo atrativo. Ocupação desconhecida/confirmada, condições operacionais ausentes ou dívidas impedem classificação verde. Sem preço, avaliação, cidade, UF ou tipo: **Dados insuficientes**, sem pontuação.

Avaliação é a informada pela fonte, não preço de mercado. Não pontuamos qualidade do bairro, liquidez ou localização sem base confiável. Confira custos e condições no edital.

## Verificação

~~~powershell
python -m compileall -q app.py leilao_app
python -m unittest discover -s tests -v
python scripts/validate_browser.py
~~~

O teste de navegador exige servidor em 8512, Chrome e a base de validação de Jundiaí. Evidências locais ficam em data/validation/, ignoradas pelo Git. scripts/validate_review.py compara capturas oficiais salvas; com --import-verified-captures, importa os registros comparados.

Docker permanece opcional (docker compose up --build); imagens não incluem .env, banco ou capturas. O build Docker não substitui a compilação e os testes Python e não foi executado na revisão.

Consulte [diagnóstico inicial](docs/REVISAO_INICIAL.md), [fontes e limitações](docs/SOURCES.md) e [relatório final](docs/REVISAO_FINAL.md).

## Cobertura nacional

A busca aceita as 27 UFs (26 estados e DF), capitais e cidades do interior presentes na base. O conector CAIXA usa a lista oficial nacional. A disponibilidade depende das ofertas publicadas, sem fabricar resultados para preencher regiões.

Para atualizar: `python -m leilao_app.cli collect --source caixa`. Para importar uma lista nacional já baixada: `python scripts/import_national.py caminho/lista.csv`. A lista CSV não contém fotos; nesses registros aparece o placeholder até haver imagem oficial vinculada.
