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

Para rodar a coleta agendada em processo separado:

```powershell
python -m leilao_app.scheduler_worker
```

Para coletar manualmente pelo terminal:

```powershell
python -m leilao_app.cli collect
python -m leilao_app.cli collect --source caixa
```

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
