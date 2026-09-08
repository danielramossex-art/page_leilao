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
- Spy Leiloes;
- Gold Leiloes;
- Cravo Leiloes;
- Valero Leiloes;
- Gustavo Moretto Leiloeiro;
- Kwara Leiloes;
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

Na revisão de 08/09/2026, o parser HTML validado é o da Mega Leilões. Outros portais são aceitos por CSV ou JSON-LD do imóvel, quando houver campos e URL correspondentes. Os parsers antigos que dependiam da posição dos preços e de Indaiatuba foram substituídos para evitar dados incorretos.

Fontes com bloqueio não são contornadas. Uma captura sem imóveis reconhecidos é tratada como falha, não como importação bem-sucedida. Consulte SOURCES.md para a matriz de validação.
