# Onde voto 2026?

**Onde voto no 2º turno? — Eleições 2026, todo o Brasil e exterior**

Site estático para o eleitor consultar, pelo estado, pela cidade e pelo número da seção, **onde vota no 2º turno (25/10/2026)** e se o local **mudou desde o 1º turno (04/10/2026)**.

**Este site não é oficial.** A consulta oficial é o aplicativo e-Título e o Autoatendimento do TSE.

## Fonte dos dados

Uma única fonte: o cadastro de locais de votação do **Tribunal Superior Eleitoral**, conjunto
[Eleitorado por local de votação 2026](https://dadosabertos.tse.jus.br/dataset/eleitorado-2026)
(`eleitorado_local_votacao_2026.zip`, um CSV por UF, mais `ZZ` para o exterior). A data de geração aparece no rodapé.

O arquivo tem uma linha por seção para cada turno, com o local de votação e as coordenadas.

### Como o site classifica cada seção

A regra fica em `scripts/gerar_dados.py` e é conferida por uma segunda implementação em `tests/testar_dados.py`.

| Situação no site | Quando |
|---|---|
| **Seu local mudou** | O código do local é diferente nos dois turnos e o endereço também; ou o código é o mesmo, mas o endereço mudou e as coordenadas não confirmam o mesmo lugar (ou não existem). |
| **Confira o endereço** | O código mudou, mas o endereço é o mesmo; ou o código é o mesmo, o endereço mudou e as coordenadas ficam a menos de 200 m. Pode ser o mesmo prédio. |
| **Mesmo local, só o nome mudou** | Mesmo código e mesmo endereço, nome diferente (por exemplo, "E. E." e "Escola Estadual"). |
| **Mesmo local do 1º turno** | Mesmo código, nome e endereço. |

Seções agregadas são mostradas no local da seção principal, onde fica a urna.

### Limitações

- O mesmo código de local pode aparecer com nome e endereço diferentes em cada turno. Por isso o site não compara só o código.
- Coordenadas a mais de 1 km fora do próprio município são escondidas do mapa (o endereço continua). A base de limites é a do IBGE via [geodata-br](https://github.com/tbrugz/geodata-br), que não tem alguns municípios criados recentemente; nesses, a coordenada não é conferida. O log de `gerar_dados.py` lista quais.
- No exterior o TSE não informa coordenadas, então não há mapa. O "município" do exterior é, em geral, a cidade da repartição consular, que pode ser diferente da cidade onde fica a seção.
- Em cerca de 35% das buscas a mesma seção existe em mais de uma zona da cidade; o site pergunta a zona e mostra o bairro para ajudar.
- O cadastro pode mudar até o dia da eleição. Atualize os dados perto de 25/10.

## Publicar no GitHub Pages

1. Crie um repositório público e envie todos os arquivos desta pasta (incluindo `.nojekyll`).
2. Em **Settings → Pages**, escolha **Deploy from a branch**, branch `main`, pasta `/ (root)`.
3. O site fica em `https://<seu-usuario>.github.io/<repositorio>/`. O link para o repositório no rodapé é preenchido sozinho nesse endereço.
4. Link direto para um estado: acrescente `#SP`, `#PR`, `#ZZ` etc. ao endereço.

O site precisa ser servido por HTTP. Abrindo o `index.html` direto do disco, o navegador bloqueia a leitura dos dados. Para testar localmente: `python -m http.server` e abra `http://localhost:8000`.

## Atualizar os dados

1. Baixe `eleitorado_local_votacao_2026.zip` no portal de dados abertos do TSE e extraia numa pasta.
2. Rode (Python 3.9+, sem dependências):

   ```bash
   python scripts/gerar_dados.py pasta_extraida/
   python tests/testar_dados.py pasta_extraida/
   ```

   O primeiro gera `data/<UF>.json` e `data/ufs.json`; o segundo confere tudo contra os CSVs e falha se houver divergência.
3. Faça commit da pasta `data/`.

## Mapa base

Positron vetorial da [CARTO](https://carto.com/basemaps), carregado com [MapLibre GL JS](https://maplibre.org/) 4.7.1 (incluído em `lib/`).

- Hoje o estilo vetorial carrega sem chave. Desde 25/09/2026 a CARTO exige chave para os tiles **raster** e avisa que pode estender a exigência ao vetorial. Se isso acontecer, crie uma chave gratuita em <https://carto.com/basemaps/apikey/> e preencha `chaveCarto` em `assets/app.js`.
- Uso não comercial gratuito até 5 milhões de requisições por mês, segundo a CARTO. Confira os termos atuais.
- Se o mapa base não carregar, o site mostra os limites municipais do estado sobre fundo liso e continua funcionando.

## Arquivos

```
index.html                 página
assets/app.js              busca, resultado e mapa
assets/estilo.css          estilos (mobile first, tema claro e escuro)
data/ufs.json              índice dos estados (totais, data, enquadramento do mapa)
data/<UF>.json             seções e locais de cada estado (ZZ = exterior)
data/contornos/<UF>.geojson limites municipais simplificados (só usados sem mapa base)
lib/                       MapLibre GL JS 4.7.1 (BSD-3, ver LICENSE-maplibre.txt)
scripts/gerar_dados.py     gera data/ a partir dos CSVs do TSE
scripts/limites/           limites municipais (erro máximo de 50 m) para conferir coordenadas
tests/testar_dados.py      confere data/ contra os CSVs do TSE
```

## Licenças e créditos

- Dados de locais de votação: TSE, Portal de Dados Abertos. Verifique os termos de uso do portal.
- Limites municipais: projeto geodata-br, a partir de dados do IBGE. Verifique a licença do projeto.
- Mapa base: © colaboradores do OpenStreetMap, © CARTO.
- MapLibre GL JS: licença BSD-3-Clause.
- Código deste site: licença MIT (veja `LICENSE`). A licença cobre o código; os dados do TSE, os limites municipais, o mapa base e o MapLibre seguem as licenças e os termos das respectivas fontes, listados acima.
