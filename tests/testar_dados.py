#!/usr/bin/env python3
"""
Confere data/<UF>.json contra os CSVs originais do TSE, recalculando tudo de forma independente.

Uso:
    python tests/testar_dados.py pasta_com_os_csv/
    python tests/testar_dados.py eleitorado_local_votacao_2026_PR.csv

Sai com código 1 se algum teste falhar. Avisos não fazem falhar.
"""
import csv, json, math, re, sys, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from gerar_dados import chave_mun, dentro, distancia_borda_m, LIMITE_M  # noqa: E402


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper())


# Segunda implementação, escrita à parte, da regra de situação (deve concordar com scripts/gerar_dados.py):
# sem 1º turno -> 4; código diferente -> 2 se mesmo endereço com número, senão 1;
# mesmo código: mesmo nome e endereço -> 0; só o nome mudou -> 3; endereço mudou -> 2 se coordenadas a < 200 m, senão 1.
_VIAS = set("RUA R AV AVENIDA AVN PRACA PCA PC RODOVIA ROD ESTRADA EST TRAVESSA TV TRAV ALAMEDA AL LARGO LGO N NO NUM "
            "NUMERO SN S QD QUADRA LT LOTE DE DA DO DAS DOS E ZONA URBANA RURAL CENTRO SNO KM".split())


def _end(e):
    e = unicodedata.normalize("NFKD", e or "").encode("ascii", "ignore").decode().upper()
    e = re.split(r"\s-\s|;", e)[0]
    return "".join(w for w in re.findall(r"[A-Z0-9]+", e) if w not in _VIAS)


def _coord(v):
    try:
        x = float(v.replace(",", "."))
        return None if x == -1 else x
    except ValueError:
        return None


def situacao_esperada(a, b):
    if a is None:
        return 4
    ea, eb = _end(a["e"]), _end(b["e"])
    if a["c"] != b["c"]:
        return 2 if ea == eb and re.search(r"\d", eb) else 1
    if ea == eb:
        return 0 if norm(a["n"]) == norm(b["n"]) else 3
    if None in (a["lat"], b["lat"], a["lon"], b["lon"]):
        return 1
    dy = (b["lat"] - a["lat"]) * 110540
    dx = (b["lon"] - a["lon"]) * 111320 * math.cos(math.radians(a["lat"]))
    return 2 if math.hypot(dx, dy) < 200 else 1


def testar_uf(caminho_csv):
    falhas, avisos = [], []
    ok = lambda cond, msg: cond or falhas.append(msg)
    # guarda só os campos necessários, por turno: (zona, seção) -> tupla
    t = {"1": {}, "2": {}}
    uf, geracao = None, set()
    with open(caminho_csv, encoding="latin-1", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            uf = r["SG_UF"]; geracao.add(r["DT_GERACAO"])
            k = (int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            if k in t[r["NR_TURNO"]]:
                falhas.append(f"seção duplicada no CSV, turno {r['NR_TURNO']}: {k}")
            ag = int(r["NR_SECAO_PRINCIPAL"]) if r["DS_TIPO_SECAO_AGREGADA"] == "Agregada" else -1
            t[r["NR_TURNO"]][k] = (r["NR_LOCAL_VOTACAO"], norm(r["NM_LOCAL_VOTACAO"]), norm(r["NM_MUNICIPIO"]), r["CD_MUNICIPIO"], ag,
                                   {"c": r["NR_LOCAL_VOTACAO"], "n": r["NM_LOCAL_VOTACAO"], "e": r["DS_ENDERECO"],
                                    "lat": _coord(r["NR_LATITUDE"]), "lon": _coord(r["NR_LONGITUDE"])})
    D = json.load(open(RAIZ / "data" / f"{uf}.json", encoding="utf-8"))

    # 1. estrutura
    ok(D.get("uf") == uf, f"UF do JSON ({D.get('uf')}) diferente do CSV ({uf})")
    ok(all(len(l) == 7 for l in D["secoes"]), "linha de seção com tamanho diferente de 7")
    ok(set(D["gerado_tse"]) == geracao, "data de geração do TSE não confere")

    # 2. cobertura
    js = {}
    for l in D["secoes"]:
        k = (l[0], l[1]); ok(k not in js, f"seção duplicada no JSON: {k}"); js[k] = l
    ok(set(js) == set(t["2"]), f"seções do JSON ({len(js)}) diferentes das do CSV no 2º turno ({len(t['2'])})")

    # 3. linha a linha
    erros = 0
    for k, l in js.items():
        r2, r1 = t["2"].get(k), t["1"].get(k)
        L2 = D["locais"][l[3]]
        erros += not (L2["c"] == r2[0] and norm(L2["n"]) == r2[1] and norm(D["municipios"][l[2]]) == r2[2])
        if r1 is None:
            erros += l[4] != -1
        else:
            L1 = D["locais"][l[4]]
            erros += not (L1["c"] == r1[0] and norm(L1["n"]) == r1[1])
        erros += l[5] != r2[4]
        if r2[4] > 0:
            p = t["2"].get((k[0], r2[4]))
            erros += p is None or p[3] != r2[3]
    ok(erros == 0, f"{erros} divergências entre JSON e CSV na conferência linha a linha")

    # 4. situação de cada seção recalculada só com o CSV, pela segunda implementação da regra
    def ef(turno, k):
        r = t[turno].get(k)
        if r is None:
            return None
        return t[turno].get((k[0], r[4]), r) if r[4] > 0 else r
    por = {(l[0], l[1]): l for l in D["secoes"]}
    efj = lambda l: por.get((l[0], l[5]), l) if l[5] > 0 else l
    difs, cont = [], {}
    for k, l in js.items():
        a, b = ef("1", k), ef("2", k)
        esp = situacao_esperada(a[5] if a else None, b[5])
        cont[esp] = cont.get(esp, 0) + 1
        if esp != l[6]:
            difs.append((k, esp, l[6]))
    ok(not difs, f"{len(difs)} seções com situação diferente da recalculada, ex.: {difs[:3]}")
    esperado = {k for k, l in js.items() if l[6] == 1}

    # 5. coordenadas mantidas: no Brasil e a no máximo LIMITE_M do próprio município
    usados = {efj(l)[3]: l[2] for l in D["secoes"]}
    lim = RAIZ / "scripts" / "limites" / f"limites_{uf}.geojson"
    geoms = {}
    if uf != "ZZ" and lim.exists():
        geoms = {chave_mun(f["properties"]["nome"]): f["geometry"] for f in json.load(open(lim, encoding="utf-8"))["features"]}
    perto = 0
    for i, m in usados.items():
        L = D["locais"][i]
        if L["lat"] is None:
            continue
        if uf != "ZZ":
            ok(-35 < L["lat"] < 6 and -75 < L["lon"] < -28, f"coordenada fora do Brasil: {L['n']}")
        g = geoms.get(chave_mun(D["municipios"][m]))
        if g and not dentro(L["lon"], L["lat"], g):
            d = distancia_borda_m(L["lon"], L["lat"], g)
            ok(d <= LIMITE_M, f"ponto a {d / 1000:.1f} km fora do município foi mantido: {D['municipios'][m]}: {L['n']}")
            perto += 1
    if perto:
        avisos.append(f"{perto} pontos até {LIMITE_M} m fora do próprio município (diferença normal entre bases)")
    sem = sum(1 for i in usados if D["locais"][i]["lat"] is None)
    if sem:
        avisos.append(f"{sem} locais do 2º turno sem ponto no mapa (sem coordenada ou coordenada removida)")
    avisos.append("situações: " + ", ".join(f"{['igual','mudou','confira','nome','sem 1º turno'][k]} {v}" for k, v in sorted(cont.items())))
    return uf, len(js), len(esperado), falhas, avisos


def testar_mudancas():
    """data/mudancas.json deve listar exatamente as seções MUDOU (1) e CONFIRA (2) de todas as UFs."""
    falhas = []
    caminho = RAIZ / "data" / "mudancas.json"
    if not caminho.exists():
        return ["data/mudancas.json não existe"]
    M = json.load(open(caminho, encoding="utf-8"))
    esperado = {}
    for u in json.load(open(RAIZ / "data" / "ufs.json", encoding="utf-8"))["ufs"]:
        D = json.load(open(RAIZ / "data" / f"{u['uf']}.json", encoding="utf-8"))
        por = {(l[0], l[1]): l for l in D["secoes"]}
        for l in D["secoes"]:
            if l[6] in (1, 2):
                e = por.get((l[0], l[5]), l) if l[5] > 0 else l
                esperado[(u["uf"], l[0], l[1])] = (l[6], D["locais"][e[3]]["n"], D["locais"][e[4]]["n"], D["municipios"][l[2]])
    obtido = {}
    for L in M["locais"]:
        for z, s_, st, n1, _e1 in L["s"]:
            k = (L["uf"], z, s_)
            if k in obtido:
                falhas.append(f"seção repetida em mudancas.json: {k}")
            obtido[k] = (st, L["n"], n1, L["mun"])
    if set(obtido) != set(esperado):
        falhas.append(f"seções diferentes: {len(obtido)} em mudancas.json, {len(esperado)} nas UFs")
    difs = [k for k in esperado if k in obtido and obtido[k] != esperado[k]]
    if difs:
        falhas.append(f"{len(difs)} seções com situação, local ou município diferente, ex.: {difs[:3]}")
    t = M.get("total", {})
    if t.get("mudou") != sum(1 for v in esperado.values() if v[0] == 1) or t.get("confira") != sum(1 for v in esperado.values() if v[0] == 2):
        falhas.append(f"totais de mudancas.json não conferem: {t}")
    print(f"mudancas.json: {len(M['locais'])} locais, {t.get('mudou')} mudaram, {t.get('confira')} para conferir — {'OK' if not falhas else 'FALHOU'}")
    return falhas


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arqs = []
    for e in map(Path, sys.argv[1:]):
        arqs += sorted(e.glob("eleitorado_local_votacao_*_*.csv")) if e.is_dir() else [e]
    arqs = [a for a in arqs if not a.stem.upper().endswith("_BRASIL")]
    total_f, total_s, total_m = 0, 0, 0
    for a in arqs:
        uf, n, mud, falhas, avisos = testar_uf(a)
        total_s += n; total_m += mud; total_f += len(falhas)
        print(f"{uf}: {n} seções, {mud} mudam de local — {'OK' if not falhas else 'FALHOU'}")
        for x in avisos:
            print(f"   aviso: {x}")
        for x in falhas:
            print(f"   FALHOU: {x}")
    print(f"TOTAL: {len(arqs)} arquivos, {total_s} seções, {total_m} mudam de local do 1º para o 2º turno")
    falhas_m = testar_mudancas()
    total_f += len(falhas_m)
    for x in falhas_m:
        print(f"   FALHOU (mudancas.json): {x}")
    if total_f:
        sys.exit(1)
    print("Todos os testes passaram.")


if __name__ == "__main__":
    main()
