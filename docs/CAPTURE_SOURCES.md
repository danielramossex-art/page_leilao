# Catalogo operacional de captura

Data de referencia: 2026-06-08.

O catalogo executavel fica em `leilao_app/sources.py` e aceita filtros por:

- estado: `SP`, `MG`, `PR`, `SC`;
- categoria: `banco`, `agregador`, `cidade`, `leiloeiro`.

Exemplos:

```powershell
python -m leilao_app.cli capture-url --state SP --category agregador
python -m leilao_app.cli capture-url --state MG --state PR --category banco
python -m leilao_app.cli capture-url --url https://www.leilaoimovel.com.br/leilao-de-imovel/indaiatuba-sp
```

Fontes no catalogo:

- Caixa Economica Federal;
- Banco do Brasil;
- Santander Imoveis;
- Itau Imoveis;
- Bradesco Leiloes;
- Leilao Imovel;
- Portal Zuk;
- Lailo;
- Oportuno;
- Sold Leiloes;
- Superbid Exchange;
- Biasi Leiloes;
- Mega Leiloes;
- Frazao Leiloes;
- Freitas Leiloeiro;
- E-leiloeiro / Eleiloeiro;
- GL Leiloes;
- Nogari Leiloes;
- Gilson Leiloes;
- WMS Leiloes;
- Sodre Santoro;
- Milan Leiloes;
- Lance no Leilao.

O parser estruturado mais maduro hoje e o do `leilaoimovel.com.br`, que extrai imagens, endereco, cidade, estado, valores, desconto, modalidade/dividas por heuristica e link original. As demais fontes ficam prontas para captura por navegador e evolucao incremental de parser conforme os HTMLs reais forem capturados.

Sites com `robots.txt`, CAPTCHA ou bloqueio anti-bot nao sao burlados. Para esses casos, use API autorizada, exportacao oficial, Apify com token proprio ou captura assistida no navegador.
