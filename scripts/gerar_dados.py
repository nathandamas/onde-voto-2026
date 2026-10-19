#!/usr/bin/env python3
"""
Gera data/<UF>.json, data/ufs.json, data/mudancas.json e data/estatisticas.json a partir dos arquivos de Dados Abertos do TSE
"Eleitorado por local de votação 2026" (eleitorado_local_votacao_2026_<UF>.csv).

Fonte única: cadastro do TSE. Para cada seção, o site mostra o local do 2º turno
e se ele é diferente do local do 1º turno de 2026.

Uso:
    python scripts/gerar_dados.py pasta_com_os_csv/                 # todas as UFs da pasta
    python scripts/gerar_dados.py eleitorado_local_votacao_2026_PR.csv eleitorado_local_votacao_2026_SC.csv

O arquivo ..._BRASIL.csv (consolidado) é ignorado. ..._ZZ.csv é o voto no exterior.
Requer só a biblioteca padrão do Python 3.9+. Layout conforme o leiame do TSE:
Latin-1, campos entre aspas separados por ";", -1 = sem informação.
"""
import argparse, csv, json, math, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_M = 1000   # ponto a mais disso fora do próprio município é tratado como coordenada errada

UF_NOMES = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
            "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
            "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
            "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
            "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
            "SE": "Sergipe", "TO": "Tocantins", "ZZ": "Exterior"}

COLUNAS = ["DT_GERACAO", "AA_ELEICAO", "NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
           "DS_TIPO_SECAO_AGREGADA", "NR_SECAO_PRINCIPAL", "NR_LOCAL_VOTACAO", "NM_LOCAL_VOTACAO", "DS_ENDERECO",
           "NM_BAIRRO", "NR_LATITUDE", "NR_LONGITUDE", "QT_ELEITOR_SECAO", "NR_LOCAL_VOTACAO_ORIGINAL"]

# grandes regiões do IBGE; o exterior fica à parte
REGIOES = {"N": ("Norte", "AC AM AP PA RO RR TO"), "NE": ("Nordeste", "AL BA CE MA PB PE PI RN SE"),
           "CO": ("Centro-Oeste", "DF GO MS MT"), "SE": ("Sudeste", "ES MG RJ SP"), "S": ("Sul", "PR RS SC"),
           "EX": ("Exterior", "ZZ")}
REGIAO_DA_UF = {uf: r for r, (_, lista) in REGIOES.items() for uf in lista.split()}
# faixas de distância em linha reta entre o local do 1º e o do 2º turno (limite superior, em metros)
FAIXAS_M = [200, 500, 1000, 2000, 5000, None]

SIGLAS = {"CMEI", "CEI", "CRAS", "CREAS", "APAE", "UTFPR", "UFPR", "CEEBJA", "CEIEBJA", "CAIC", "CAIAC", "UBS", "CEEP",
          "UNICENTRO", "UNESPAR", "UNIOESTE", "UEL", "UEM", "UEPG", "FECOP", "CERBI", "SESC", "SESI", "SENAI", "SENAC", "CSU",
          "KM", "BR", "CMAEE", "UEI", "EJA", "EF", "EFM", "CTG", "AABB", "ACM", "IFPR", "PUC", "PUCPR", "S/N", "EE",
          "EMEF", "EMEI", "CEU", "ETEC", "FATEC", "USP", "UNESP", "UNICAMP", "UFMG", "UFRJ", "UERJ", "UFBA", "UFPE", "UFC",
          "UFRGS", "UFSC", "UNB", "IFSP", "IFBA", "IFCE", "IFMG", "IFRS", "IFSC", "CIEP", "CIEPS", "CAPS", "CMAE",
          "PROFIS", "KVALAS", "ISULPAR", "CEFET", "UNIPAR", "MEEC", "CEP", "CEMEI", "EMEB", "CAIS", "CEAI", "SENAR",
          "USA", "EUA", "UK", "NY", "NJ", "DC", "CEE", "CEEF"}
PEQUENAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no"}
APELIDOS = {"MUNHOZDEMELLO": "MUNHOZDEMELO"}   # grafia TSE -> grafia IBGE, quando diferem


def titulo(s):
    """'ESCOLA MUNICIPAL DR. JOAO' -> 'Escola Municipal Dr. Joao'; mantém siglas e números romanos."""
    out = []
    for i, p in enumerate(s.strip().split()):
        lp = p.lower()
        if i and lp in PEQUENAS:
            out.append(lp)
        elif p.strip(".,-()") in SIGLAS or re.fullmatch(r"[IVX]{1,4}[.,]?", p):
            out.append(p)
        elif "'" in p or "/" in p:   # D'OESTE -> D'Oeste; LAPA/SAPEZAL -> Lapa/Sapezal
            sep = "'" if "'" in p else "/"
            out.append(sep.join(titulo(x) if sep == "/" and x else x[:1].upper() + x[1:].lower() for x in p.split(sep)))
        else:
            out.append(p[:1].upper() + p[1:].lower())
    return " ".join(out)


def coord(v):
    try:
        x = float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return None if x == -1 else round(x, 6)


def chave_mun(s):
    k = re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper())
    return APELIDOS.get(k, k)


TIPOS_VIA = {"RUA", "R", "AV", "AVENIDA", "AVN", "PRACA", "PCA", "PC", "RODOVIA", "ROD", "ESTRADA", "EST", "TRAVESSA",
             "TV", "TRAV", "ALAMEDA", "AL", "LARGO", "LGO", "N", "NO", "NUM", "NUMERO", "SN", "S", "QD", "QUADRA", "LT", "LOTE",
             "DE", "DA", "DO", "DAS", "DOS", "E", "ZONA", "URBANA", "RURAL", "CENTRO", "SNO", "KM"}

# situação de cada seção (fonte única da regra; o site só exibe)
IGUAL, MUDOU, CONFIRA, NOME, SEM1T, VOLTA = 0, 1, 2, 3, 4, 5
# VOLTA: no 1º turno a seção votou em local provisório (NR_LOCAL_VOTACAO diferente de NR_LOCAL_VOTACAO_ORIGINAL)
# e no 2º turno o cadastro a devolve ao local original. Segundo nota do TSE de 19/10/2026, isso pode ser só
# registro pendente: a zona eleitoral ainda pode "importar" a alocação provisória e manter o local do 1º turno.


def chave_endereco(e):
    """Endereço reduzido a nome da via + números, para comparar grafias diferentes do mesmo endereço."""
    e = unicodedata.normalize("NFKD", e or "").encode("ascii", "ignore").decode().upper()
    e = re.split(r"\s-\s|;", e)[0]
    return "".join(t for t in re.findall(r"[A-Z0-9]+", e) if t not in TIPOS_VIA)


def chave_nome(n):
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().upper())


def distancia_m(a, b):
    if a["lat"] is None or b["lat"] is None:
        return None
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def situacao(L1, L2):
    """Compara o local do 1º turno (L1) com o do 2º turno (L2), ambos com coordenadas originais do TSE."""
    if L1 is None:
        return SEM1T
    mesmo_end = chave_endereco(L1["e"]) == chave_endereco(L2["e"]) and any(ch.isdigit() for ch in chave_endereco(L2["e"]))
    mesmo_nome = chave_nome(L1["n"]) == chave_nome(L2["n"])
    d = distancia_m(L1, L2)
    perto = d is not None and d < 200
    if L1["c"] != L2["c"]:
        # outro local no cadastro; se o endereço é o mesmo, pode ser o mesmo prédio com outro nome
        return CONFIRA if mesmo_end else MUDOU
    if mesmo_nome and (mesmo_end or chave_endereco(L1["e"]) == chave_endereco(L2["e"])):
        return IGUAL
    if not mesmo_nome and chave_endereco(L1["e"]) == chave_endereco(L2["e"]):
        return NOME
    # mesmo código, mas endereço diferente: mudança real se as coordenadas não ajudam a confirmar o mesmo lugar
    return CONFIRA if perto else MUDOU


def aneis(g):
    """Todos os anéis de todos os polígonos. Algumas bases gravam partes de um município como
    anéis extras de um mesmo polígono; por isso nunca se usa só o primeiro anel."""
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [anel for poly in polys for anel in poly]


def dentro(lon, lat, g):
    """Regra par-ímpar sobre todos os anéis: funciona para furos e para partes gravadas como anéis."""
    c = False
    for a in aneis(g):
        for i in range(len(a)):
            x1, y1 = a[i - 1][:2]; x2, y2 = a[i][:2]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                c = not c
    return c


def distancia_borda_m(lon, lat, g):
    kx, ky, melhor = 111320 * math.cos(math.radians(lat)), 110540, float("inf")
    for a in aneis(g):
        for i in range(len(a)):
            x1, y1 = a[i - 1][:2]; x2, y2 = a[i][:2]
            ax, ay, bx, by = (x1 - lon) * kx, (y1 - lat) * ky, (x2 - lon) * kx, (y2 - lat) * ky
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1)))
            melhor = min(melhor, math.hypot(ax + t * dx, ay + t * dy))
    return melhor


def gerar(caminho_csv, pasta_dados, pasta_limites):
    locais, idx = [], {}           # (zona, município, código) -> posição; o código só é único dentro de zona + município
    municipios, midx = [], {}
    sec, ufs, anos, geracao = {}, set(), set(), set()

    with open(caminho_csv, encoding="latin-1", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
        if faltando:
            sys.exit(f"{caminho_csv}: faltam as colunas {', '.join(faltando)}. É o 'Eleitorado por local de votação' do TSE?")
        for r in leitor:   # leitura em fluxo: não guarda o CSV inteiro na memória
            ufs.add(r["SG_UF"]); anos.add(r["AA_ELEICAO"]); geracao.add(r["DT_GERACAO"])
            m = r["CD_MUNICIPIO"]
            if m not in midx:
                midx[m] = len(municipios)
                municipios.append(titulo(r["NM_MUNICIPIO"]))
            # o mesmo código pode ter nome/endereço diferentes em cada turno: cada versão é um registro
            k = (r["NR_ZONA"], m, r["NR_LOCAL_VOTACAO"], chave_nome(r["NM_LOCAL_VOTACAO"]), chave_endereco(r["DS_ENDERECO"]),
                 r["NR_LATITUDE"], r["NR_LONGITUDE"])
            if k not in idx:
                idx[k] = len(locais)
                bairro = "" if r["SG_UF"] == "ZZ" else titulo(r["NM_BAIRRO"])   # no exterior o TSE preenche "CENTRO"
                locais.append({"n": titulo(r["NM_LOCAL_VOTACAO"]), "e": titulo(re.sub(r"\s+", " ", r["DS_ENDERECO"])),
                               "b": bairro, "lat": coord(r["NR_LATITUDE"]), "lon": coord(r["NR_LONGITUDE"]),
                               "c": r["NR_LOCAL_VOTACAO"]})
            chave = (int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            d = sec.setdefault(chave, {"m": midx[m]})
            if d["m"] != midx[m]:
                sys.exit(f"{caminho_csv}: seção {chave} aparece em dois municípios.")
            d["t" + r["NR_TURNO"]] = idx[k]
            d["c" + r["NR_TURNO"]] = r["NR_LOCAL_VOTACAO"]                  # código do local usado no turno
            d["o" + r["NR_TURNO"]] = r["NR_LOCAL_VOTACAO_ORIGINAL"]         # código do local original
            if r["NR_TURNO"] == "2":
                # eleitores vinculados originalmente à seção (leiame do TSE); é o mesmo número nos dois turnos
                d["el"] = max(0, int(r["QT_ELEITOR_SECAO"] or 0))
            if r["DS_TIPO_SECAO_AGREGADA"] == "Agregada" and r["NR_SECAO_PRINCIPAL"] not in ("", "-1"):
                d["ag"] = int(r["NR_SECAO_PRINCIPAL"])

    if len(ufs) != 1:
        sys.exit(f"{caminho_csv}: o arquivo deve ter uma só UF; encontrei {sorted(ufs)}.")
    uf = ufs.pop()

    # situação calculada com as coordenadas originais, antes da remoção das suspeitas
    coord_orig = [(L["lat"], L["lon"]) for L in locais]

    # coordenadas suspeitas: ponto a mais de LIMITE_M fora do próprio município é removido (o site usa o endereço)
    suspeitas, sem_limite = [], set()
    lim = Path(pasta_limites) / f"limites_{uf}.geojson"
    if uf != "ZZ" and lim.exists():
        geoms = {chave_mun(f["properties"].get("nome") or f["properties"].get("name")): f["geometry"]
                 for f in json.load(open(lim, encoding="utf-8"))["features"]}
        mun_do_local = {}
        for d in sec.values():
            for t in ("t1", "t2"):
                if t in d:
                    mun_do_local[d[t]] = d["m"]
        for i, m in mun_do_local.items():
            L, g = locais[i], geoms.get(chave_mun(municipios[m]))
            if g is None:
                sem_limite.add(municipios[m]); continue
            if L["lat"] is None or dentro(L["lon"], L["lat"], g):
                continue
            dist = distancia_borda_m(L["lon"], L["lat"], g)
            if dist > LIMITE_M:
                suspeitas.append(f"{municipios[m]}: {L['n']} a {dist / 1000:.1f} km do município")
                L["lat"] = L["lon"] = None
                L["coord_suspeita"] = True
    elif uf != "ZZ":
        print(f"aviso: {lim} não encontrado; coordenadas de {uf} não foram conferidas", file=sys.stderr)

    # [zona, seção, município, local 2º turno, local 1º turno (-1), seção principal se agregada (-1), situação]
    saida, sem_2t, el_secao = [], 0, {}
    for (z, s), d in sorted(sec.items()):
        if "t2" not in d:
            sem_2t += 1; continue
        saida.append([z, s, d["m"], d["t2"], d.get("t1", -1), d.get("ag", -1), None])
        el_secao[(z, s)] = d.get("el", 0)
    por = {(l[0], l[1]): l for l in saida}
    efetiva = lambda l: por.get((l[0], l[5]), l) if l[5] > 0 else l
    orig = lambda i: dict(locais[i], lat=coord_orig[i][0], lon=coord_orig[i][1])
    def volta_do_provisorio(z, s_):
        d = sec.get((z, s_), {})
        o1, c1, o2, c2 = d.get("o1"), d.get("c1"), d.get("o2"), d.get("c2")
        valido = lambda x: x not in (None, "", "-1")
        return (valido(o1) and valido(c1) and c1 != o1          # provisório no 1º turno
                and c2 == o1 and (not valido(o2) or c2 == o2))  # no 2º turno, no local original (não provisório)
    for l in saida:
        e = efetiva(l)
        l[6] = situacao(orig(e[4]) if e[4] != -1 else None, orig(e[3]))
        if l[6] in (MUDOU, CONFIRA) and volta_do_provisorio(e[0], e[1]):
            l[6] = VOLTA
    mudaram = sum(1 for l in saida if l[6] == MUDOU)
    confira = sum(1 for l in saida if l[6] == CONFIRA)
    volta = sum(1 for l in saida if l[6] == VOLTA)

    # eleitores: total por município e, para as seções que mudaram ou que pedem conferência, por seção
    el_mun = [0] * len(municipios)
    for l in saida:
        el_mun[l[2]] += el_secao[(l[0], l[1])]
    el_sec = {f"{l[0]}-{l[1]}": el_secao[(l[0], l[1])] for l in saida if l[6] in (MUDOU, CONFIRA, VOLTA)}

    usados = {efetiva(l)[3] for l in saida}
    pts = [(locais[i]["lon"], locais[i]["lat"]) for i in usados if locais[i]["lat"] is not None]
    bbox = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)] if pts else None

    Path(pasta_dados).mkdir(parents=True, exist_ok=True)
    with open(Path(pasta_dados) / f"{uf}.json", "w", encoding="utf-8") as f:
        json.dump({"fonte": "TSE - Dados Abertos - Eleitorado por local de votação", "uf": uf, "eleicao": sorted(anos),
                   "gerado_tse": sorted(geracao), "municipios": municipios, "locais": locais, "secoes": saida,
                   "eleitores": {"mun": el_mun, "sec": el_sec}},
                  f, ensure_ascii=False, separators=(",", ":"))

    print(f"{uf}: {len(saida)} seções, {mudaram} mudam de local, {confira} para conferir, {volta} voltam do provisório, {len(locais)} locais, "
          f"{len(suspeitas)} coordenadas removidas, {len(sem_limite)} municípios sem limite para conferir", file=sys.stderr)
    for x in suspeitas:
        print(f"   coordenada removida: {x}", file=sys.stderr)
    if sem_limite:
        print(f"   sem limite municipal para conferir: {', '.join(sorted(sem_limite))}", file=sys.stderr)
    if sem_2t:
        print(f"   atenção: {sem_2t} seções sem linha de 2º turno foram ignoradas", file=sys.stderr)
    return {"uf": uf, "nome": UF_NOMES.get(uf, uf), "secoes": len(saida), "eleitores": sum(el_mun),
            "mudaram": mudaram, "confira": confira, "volta": volta,
            "municipios": len(municipios), "gerado_tse": sorted(geracao), "bbox": bbox,
            "coord_removidas": len(suspeitas), "sem_limite": sorted(sem_limite)}


def gerar_mudancas(pasta_dados, ufs):
    """data/mudancas.json: cada local do 2º turno que recebe seções com situação MUDOU, CONFIRA ou VOLTA, em todo o país.
    Lido de data/<UF>.json, para usar exatamente a mesma classificação da página de consulta."""
    locais_saida, total = [], {"mudou": 0, "confira": 0, "volta": 0}
    for u in ufs:
        D = json.load(open(Path(pasta_dados) / f"{u['uf']}.json", encoding="utf-8"))
        por = {(l[0], l[1]): l for l in D["secoes"]}
        grupos = {}
        for l in D["secoes"]:
            if l[6] not in (MUDOU, CONFIRA, VOLTA):
                continue
            e = por.get((l[0], l[5]), l) if l[5] > 0 else l
            A = D["locais"][e[4]]
            grupos.setdefault(e[3], {"m": l[2], "s": []})["s"].append([l[0], l[1], l[6], A["n"], A["e"]])
            total[{MUDOU: "mudou", CONFIRA: "confira", VOLTA: "volta"}[l[6]]] += 1
        for i, g in grupos.items():
            L = D["locais"][i]
            g["s"].sort(key=lambda x: (x[0], x[1]))
            locais_saida.append({"uf": u["uf"], "mun": D["municipios"][g["m"]], "n": L["n"], "e": L["e"], "b": L["b"],
                                 "lat": L["lat"], "lon": L["lon"], "s": g["s"]})
    locais_saida.sort(key=lambda x: (x["uf"] == "ZZ", x["uf"], x["mun"], x["n"]))
    with open(Path(pasta_dados) / "mudancas.json", "w", encoding="utf-8") as f:
        json.dump({"gerado_tse": sorted({d for u in ufs for d in u["gerado_tse"]}), "total": total, "locais": locais_saida},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"mudanças: {total['mudou']} seções mudaram, {total['confira']} para conferir, {total['volta']} voltam do provisório, em {len(locais_saida)} locais "
          f"-> {Path(pasta_dados) / 'mudancas.json'}", file=sys.stderr)


def gerar_estatisticas(pasta_dados, ufs):
    """data/estatisticas.json: números das mudanças por região, estado e município, e distância das mudanças.
    "Mudou", "confira" e "volta do provisório" são contados à parte; distâncias só de "mudou". Lido de data/<UF>.json, com a mesma classificação do site."""
    vazio = lambda: {"secoes": 0, "eleitores": 0, "mudou_sec": 0, "mudou_el": 0, "confira_sec": 0, "confira_el": 0,
                     "volta_sec": 0, "volta_el": 0, "locais": 0, "municipios": 0}
    brasil, regioes, por_uf, municipios = vazio(), {r: vazio() for r in REGIOES}, [], []
    distancias, sem_dist, pares = [], 0, {}
    dist_reg, sem_reg = {r: [] for r in REGIOES}, {r: 0 for r in REGIOES}   # distâncias por região
    maior_reg = {}   # região -> (distância, par de locais) da mudança mais distante
    pares_reg = {r: {} for r in REGIOES}   # região -> {par (local antigo, local novo): distância}; várias seções mudam juntas
    for u in ufs:
        D = json.load(open(Path(pasta_dados) / f"{u['uf']}.json", encoding="utf-8"))
        if "eleitores" not in D:
            sys.exit(f"data/{u['uf']}.json foi gerado por uma versão antiga deste script. Rode de novo com todos os CSVs.")
        E, por = D["eleitores"], {(l[0], l[1]): l for l in D["secoes"]}
        x = vazio(); x["secoes"] = len(D["secoes"]); x["eleitores"] = sum(E["mun"])
        mun = {}
        locais_mudou = set()
        r = REGIAO_DA_UF.get(u["uf"])
        if r is None:
            sys.exit(f"UF sem região definida: {u['uf']}")
        for l in D["secoes"]:
            m = mun.setdefault(l[2], {"secoes": 0, "mudou_sec": 0, "mudou_el": 0, "confira_sec": 0, "confira_el": 0,
                                      "volta_sec": 0, "volta_el": 0})
            m["secoes"] += 1
            if l[6] not in (MUDOU, CONFIRA, VOLTA):
                continue
            el = E["sec"][f"{l[0]}-{l[1]}"]
            tipo = {MUDOU: "mudou", CONFIRA: "confira", VOLTA: "volta"}[l[6]]
            for alvo in (x, m):
                alvo[tipo + "_sec"] += 1; alvo[tipo + "_el"] += el
            e = por.get((l[0], l[5]), l) if l[5] > 0 else l
            if l[6] == MUDOU:
                locais_mudou.add(e[3])
                dist = distancia_m(D["locais"][e[4]], D["locais"][e[3]])   # coordenadas já sem as suspeitas
                if dist is None:
                    sem_dist += 1; sem_reg[r] += 1
                else:
                    distancias.append((dist, el)); dist_reg[r].append(dist)
                    pr = pares.setdefault((u["uf"], e[4], e[3]), {"uf": u["uf"], "mun": D["municipios"][l[2]],
                                                                    "km": round(dist / 1000, 1), "de": D["locais"][e[4]]["n"],
                                                                    "para": D["locais"][e[3]]["n"], "secoes": 0})
                    pr["secoes"] += 1
                    pares_reg[r][(u["uf"], e[4], e[3])] = dist
                    if r not in maior_reg or dist > maior_reg[r][0]:
                        maior_reg[r] = (dist, (u["uf"], e[4], e[3]))
        x["locais"] = len(locais_mudou)
        for i, m in mun.items():
            if m["mudou_sec"] or m["confira_sec"] or m["volta_sec"]:
                municipios.append(dict(uf=u["uf"], mun=D["municipios"][i], eleitores=E["mun"][i], **m))
        x["municipios"] = sum(1 for m in mun.values() if m["mudou_sec"])
        for alvo in (brasil, regioes[r]):
            for k in alvo:
                alvo[k] += x[k]
        por_uf.append(dict(uf=u["uf"], nome=u["nome"], regiao=r, **x))
    faixas, ini = [], 0
    for fim in FAIXAS_M:
        sel = [el for d, el in distancias if d >= ini and (fim is None or d < fim)]
        faixas.append({"de": ini, "ate": fim, "secoes": len(sel), "eleitores": sum(sel)})
        ini = fim
    def mediana_de(valores):
        ds = sorted(valores)
        if not ds:
            return None
        meio = len(ds) // 2
        return round(ds[meio] if len(ds) % 2 else (ds[meio - 1] + ds[meio]) / 2)
    ds = [d for d, _ in distancias]
    mediana = mediana_de(ds)
    # por região: maior distância (o caso, com cidade e seções) e quantas mudanças passaram de 2 km;
    # ordenado da maior para a menor distância; o exterior não tem coordenadas e fica sem esses números
    def maior(r):
        if r not in maior_reg:
            return None
        d, par = maior_reg[r]; pr = pares[par]
        return {"m": round(d), "uf": pr["uf"], "mun": pr["mun"], "secoes": pr["secoes"], "de": pr["de"], "para": pr["para"]}
    por_regiao = sorted(({"regiao": r, "nome": REGIOES[r][0], "com": len(dist_reg[r]), "sem": sem_reg[r],
                          "mediana_m": mediana_de(dist_reg[r]), "maior": maior(r),
                          "acima_2km": sum(1 for d in dist_reg[r] if d > 2000),
                          "mudancas": len(pares_reg[r]),
                          "mudancas_acima_2km": sum(1 for d in pares_reg[r].values() if d > 2000)} for r in REGIOES),
                        key=lambda x: (x["maior"] is None, -(x["maior"] or {"m": 0})["m"], x["nome"]))
    municipios.sort(key=lambda m: (-m["mudou_sec"], -m["volta_sec"], -m["confira_sec"], m["uf"], m["mun"]))
    saida = {"gerado_tse": sorted({d for u in ufs for d in u["gerado_tse"]}),
             "brasil": brasil,
             "regioes": [dict(regiao=r, nome=REGIOES[r][0], **regioes[r]) for r in REGIOES],
             "ufs": por_uf,
             "municipios": municipios,
             "distancia": {"com": len(ds), "sem": sem_dist, "mediana_m": mediana, "faixas": faixas,
                           "maiores": sorted(pares.values(), key=lambda p: -p["km"])[:5],
                           "por_regiao": por_regiao}}
    with open(Path(pasta_dados) / "estatisticas.json", "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
    print(f"estatísticas: {brasil['mudou_sec']} seções e {brasil['mudou_el']} eleitores mudaram de local, "
          f"{len(municipios)} municípios -> {Path(pasta_dados) / 'estatisticas.json'}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entradas", nargs="+", help="CSVs do TSE ou uma pasta com eles")
    ap.add_argument("--dados", default=str(RAIZ / "data"), help="pasta de saída (padrão: data/)")
    ap.add_argument("--limites", default=str(RAIZ / "scripts" / "limites"), help="pasta com limites_<UF>.geojson")
    a = ap.parse_args()

    arquivos = []
    for e in map(Path, a.entradas):
        arquivos += sorted(e.glob("eleitorado_local_votacao_*_*.csv")) if e.is_dir() else [e]
    arquivos = [p for p in arquivos if not p.stem.upper().endswith("_BRASIL")]
    if not arquivos:
        sys.exit("Nenhum CSV encontrado.")

    indice_path = Path(a.dados) / "ufs.json"
    indice = {u["uf"]: u for u in json.load(open(indice_path, encoding="utf-8"))["ufs"]} if indice_path.exists() else {}
    for p in arquivos:
        r = gerar(p, a.dados, a.limites)
        indice[r["uf"]] = r
    ufs = sorted(indice.values(), key=lambda u: (u["uf"] == "ZZ", u["nome"]))
    with open(indice_path, "w", encoding="utf-8") as f:
        json.dump({"ufs": ufs}, f, ensure_ascii=False, indent=0)
    total = sum(u["secoes"] for u in ufs); mud = sum(u["mudaram"] for u in ufs); conf = sum(u.get("confira", 0) for u in ufs)
    print(f"TOTAL: {len(ufs)} UFs, {total} seções, {mud} mudam de local, {conf} para conferir -> {indice_path}", file=sys.stderr)
    gerar_mudancas(a.dados, ufs)
    gerar_estatisticas(a.dados, ufs)


if __name__ == "__main__":
    main()
