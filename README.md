# Monitor Local de Leilões Imobiliários

Aplicação local em Python + Streamlit para monitorar, coletar, analisar e ranquear imóveis em leilão nos estados de SP, MG, PR e SC.

## Arquitetura

```text
Page_leilao/
  app.py                         # Interface Streamlit
  requirements.txt               # Dependências
  .env.example                   # Configuração local
  Dockerfile                     # Execução opcional em container
  docker-compose.yml
  data/
    leiloes.db                   # SQLite criado na primeira execução
    cache/                       # Cache HTTP
    logs/app.log                 # Logs rotativos
  docs/
    SOURCES.md                   # Fontes, limitações e manutenção
  leilao_app/
    config.py                    # Settings e paths
    db.py                        # SQLAlchemy engine/session
    models.py                    # Tabelas e históricos
    cli.py                       # init-db e collect
    scheduler_worker.py          # APScheduler a cada 1 hora
    connectors/
      connector_caixa.py         # Alias compatível
      connector_bb.py
      connector_santander.py
      connector_itau.py
      connector_leiloeiros.py
      base.py                    # Contrato comum
      caixa.py bb.py santander.py itau.py leiloeiros.py
    services/
      http_client.py             # cache, retry, rate limit, robots.txt
      collector.py               # orquestra coleta, upsert e histórico
      scoring.py                 # score financeiro/jurídico/liquidez/localização
      neighborhood.py            # classificação de bairro
      geocoding.py               # OpenStreetMap/Nominatim
      alerts.py                  # alertas
```

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m leilao_app.cli init-db
```

## Execução

```powershell
streamlit run app.py
```

Abra o endereço exibido pelo Streamlit, normalmente `http://localhost:8501`.

Para fechar instâncias antigas deste projeto e iniciar sempre a versão atual em uma porta fixa:

```powershell
.\scripts\start_current.ps1 -Port 8512
```

Para rodar a coleta agendada em processo separado:

```powershell
python -m leilao_app.scheduler_worker
```

Para coletar manualmente pelo terminal:

```powershell
python -m leilao_app.cli collect
python -m leilao_app.cli collect --source caixa
```

## Importação CSV quando uma fonte bloquear scraping

Algumas fontes usam CAPTCHA ou proteção anti-bot. Nesses casos, a aplicação não tenta contornar o bloqueio: ela registra a falha no Admin e você pode importar dados por CSV.

Modelo de arquivo: `samples/imoveis_importacao.csv`.

## Automação sem token: pasta monitorada

Na aplicação, abra a aba `Admin`, selecione o CSV em `Importar imóveis por CSV` e clique em `Importar CSV`.

Para um fluxo automático sem Apify, salve ou baixe arquivos em:

```text
data/inbox
```

Formatos aceitos:

- `.csv`
- `.xlsx`
- `.xls`
- `.html`

O sistema lê a pasta no botão `Coletar agora`, no scheduler de 1 hora e pelo comando abaixo. Arquivos importados vão para `data/processed`; arquivos com erro vão para `data/failed`.

```powershell
python -m leilao_app.cli import-inbox
```

Também é possível importar pelo terminal:

```powershell
python -m leilao_app.cli import-csv --file samples\imoveis_importacao.csv
```

## Coleta automática pela internet via API autorizada

Sites como `leilaoimovel.com.br`, Portal Zuk e endpoints internos da Caixa podem bloquear scraping direto por `robots.txt`, CAPTCHA ou proteção anti-bot. Para automatizar sem burlar essas regras, configure um provedor autorizado por API.

O projeto já suporta Apify para coletar páginas como Indaiatuba/SP e Salto/SP:

```env
APIFY_TOKEN=seu_token
APIFY_LEILAOIMOVEL_ACTOR_ID=gio21~leilaoimovel-scraper
APIFY_MAX_ITEMS=10000
```

Depois execute:

```powershell
python -m leilao_app.cli collect-apify --url https://www.leilaoimovel.com.br/leilao-de-imoveis/sp --url https://www.leilaoimovel.com.br/leilao-de-imoveis/mg --url https://www.leilaoimovel.com.br/leilao-de-imoveis/pr --url https://www.leilaoimovel.com.br/leilao-de-imoveis/sc
```

Ou use a aba `Admin > Coleta automática autorizada via API`.

## Banco de dados

O padrão é SQLite em `data/leiloes.db`.

Para migrar futuramente para PostgreSQL, altere no `.env`:

```env
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/leiloes
```

Será necessário instalar o driver PostgreSQL escolhido, por exemplo `psycopg`.

## O que é salvo

O banco armazena:

- imóvel e origem;
- URL oficial obrigatória;
- histórico de preços;
- histórico de status;
- histórico de score;
- histórico de imagens;
- histórico de alterações;
- erros e execuções de coleta;
- alertas.

Campos jurídicos obrigatórios:

- `auction_modality`: Judicial, Extrajudicial ou Não informado;
- `has_debts`: Com dívidas, Sem dívidas ou Não informado;
- `debt_value`;
- `debt_description`;
- `debt_information_source`.

## Coleta automática

O app inicia um scheduler em background quando está aberto. Para produção local mais estável, prefira deixar também o worker dedicado rodando:

```powershell
python -m leilao_app.scheduler_worker
```

O intervalo padrão é 60 minutos e pode ser alterado em `.env`:

```env
COLLECT_INTERVAL_MINUTES=60
```

## Respeito a fontes públicas

O coletor:

- verifica `robots.txt`;
- usa `User-Agent` configurável;
- aplica cache HTTP local;
- aplica retry com backoff;
- limita requisições por domínio;
- registra falhas sem interromper todo o sistema.

Se uma fonte bloquear scraping ou exigir autenticação/captcha, a falha aparece no painel Admin.

## Adicionando novo conector

1. Crie `leilao_app/connectors/minha_fonte.py`.
2. Herde de `BaseConnector`.
3. Implemente `fetch()` retornando lista de `dict`.
4. Use `RawProperty(...).as_dict()` para normalizar.
5. Registre o conector em `leilao_app/connectors/__init__.py`.
6. Documente a fonte em `docs/SOURCES.md`.

Exemplo mínimo:

```python
from .base import BaseConnector, RawProperty

class MinhaFonteConnector(BaseConnector):
    source = "minha_fonte"
    bank_or_auctioneer = "Minha Fonte"
    start_urls = ["https://exemplo.com/imoveis"]

    def fetch(self):
        soup = self.get_soup(self.start_urls[0])
        items = []
        for card in soup.select(".imovel"):
            raw = RawProperty(
                source=self.source,
                bank_or_auctioneer=self.bank_or_auctioneer,
                source_url=self.start_urls[0],
                state="SP",
                city="São Paulo",
            )
            items.append(raw.as_dict())
        return items
```

## Limitações

Não há garantia de disponibilidade contínua das fontes externas. Bancos e leiloeiros podem alterar HTML, impor bloqueios, exigir JavaScript, captcha ou remover informações. O sistema foi desenhado para registrar falhas e facilitar manutenção dos conectores sem quebrar o portal local.

As classificações de bairro e scores são heurísticos para triagem. Antes de qualquer investimento, confira edital, matrícula, ocupação, débitos de IPTU/condomínio, ações judiciais, regras do leiloeiro e liquidez real do mercado local.
