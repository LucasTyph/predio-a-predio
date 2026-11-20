# Prédio a Prédio

Histórico de vendas residenciais da cidade de São Paulo, edifício por edifício. Busque um endereço ou clique no mapa para ver cada venda registrada no ITBI desde 2005, quanto foi pago e como o R$/m² mudou.

Fontes: guias de ITBI pagas (Secretaria Municipal da Fazenda), lotes, quadras, ruas, distritos e metrô do GeoSampa, e IPCA do Banco Central.

## Atualização automática

O workflow [`.github/workflows/atualizar.yml`](.github/workflows/atualizar.yml) roda todo dia 10 (e a cada push que mexe no site ou no pipeline). Ele baixa tudo de novo, processa e publica no GitHub Pages. Para rodar na hora: aba **Actions** → **Atualizar dados e publicar** → **Run workflow**.

Nenhum dado fica no repositório: as fontes somam uns 900 MB e o site gerado uns 100 MB, então o Actions recria tudo a cada execução (cerca de 15 minutos).

## Rodar localmente

```bash
pip install -r requirements.txt
python -I pipeline/atualizar.py --pages   # baixa as fontes e monta site/data e dist/
python -I pipeline/serve.py                # http://localhost:8765
```

Passos do pipeline, na ordem (`atualizar.py` chama todos):

| Script | O que faz |
|---|---|
| `download_itbi.py` | Lê a página de transparência da Fazenda e baixa todas as planilhas de ITBI |
| `download_ipca.py` | Série mensal do IPCA (BCB/SGS 433) |
| `download_lotes.py` | Lotes fiscais do GeoSampa, um CSV por setor fiscal (WFS) |
| `download_base.py` | Quadras, ruas, distritos e metrô do GeoSampa |
| `parse_itbi.py` | Junta as planilhas numa tabela só (`data/interim/itbi.parquet`) |
| `build_site_data.py` | Agrupa as vendas por edifício e gera `site/data/` |
| `pack_site.py` | Empacota os arquivos comprimidos como base64 `.txt` |
| `build_pages.py` | Monta `dist/` para o GitHub Pages |

`site/index.html` é a página inteira (mapa em MapLibre, sem servidor). Ela também pode ser publicada como Artifact do Claude, por isso não tem `<head>` próprio; `build_pages.py` acrescenta o esqueleto HTML.

## Como as vendas viram "edifícios"

- Cada linha do ITBI tem o SQL do imóvel (setor, quadra, lote, dígito). As unidades de um condomínio têm SQLs diferentes, mas compartilham o endereço.
- O edifício é o par logradouro + número dentro da quadra fiscal. Isso também agrupa as vendas na planta, feitas no SQL do terreno antes da individualização.
- A posição vem do lote do GeoSampa com o mesmo número na mesma quadra (preferindo o lote de condomínio). Casas sem número casado usam o próprio SQL. O que sobra fica no centro da quadra e aparece como "posição aproximada" (cerca de 4%).

## Filtros de preço

Gráficos e medianas usam só compra e venda do imóvel inteiro (proporção ≥ 99%), com área construída de pelo menos 15 m², valor de pelo menos R$ 5 mil e R$/m² entre 200 e 80 mil. A área é a do IPTU, que em apartamentos inclui a fração das áreas comuns, então o R$/m² fica abaixo do de anúncios.
