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


def volta_esperada(a, b):
    """Escrito à parte: local provisório no 1º turno (usado ≠ original) e, no 2º, o local original, sem provisório."""
    if a is None:
        return False
    ok_ = lambda x: x not in ("", "-1", None)
    return ok_(a["o"]) and a["c"] != a["o"] and b["c"] == a["o"] and (not ok_(b["o"]) or b["o"] == b["c"])


def testar_uf(caminho_csv):
    falhas, avisos = [], []
    ok = lambda cond, msg: cond or falhas.append(msg)
    # guarda só os campos necessários, por turno: (zona, seção) -> tupla
    t = {"1": {}, "2": {}}
    uf, geracao, eleitores = None, set(), {}
    with open(caminho_csv, encoding="latin-1", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            uf = r["SG_UF"]; geracao.add(r["DT_GERACAO"])
            k = (int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            if k in t[r["NR_TURNO"]]:
                falhas.append(f"seção duplicada no CSV, turno {r['NR_TURNO']}: {k}")
            if r["NR_TURNO"] == "2":
                eleitores[k] = int(r["QT_ELEITOR_SECAO"])
            ag = int(r["NR_SECAO_PRINCIPAL"]) if r["DS_TIPO_SECAO_AGREGADA"] == "Agregada" else -1
            t[r["NR_TURNO"]][k] = (r["NR_LOCAL_VOTACAO"], norm(r["NM_LOCAL_VOTACAO"]), norm(r["NM_MUNICIPIO"]), r["CD_MUNICIPIO"], ag,
                                   {"c": r["NR_LOCAL_VOTACAO"], "o": r["NR_LOCAL_VOTACAO_ORIGINAL"], "n": r["NM_LOCAL_VOTACAO"], "e": r["DS_ENDERECO"],
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
    # números para conferir data/estatisticas.json, calculados só com o CSV e com a regra recalculada
    est = {"uf": uf, "secoes": len(t["2"]), "eleitores": sum(eleitores.values()), "mun": {}}
    for k, l in js.items():
        a, b = ef("1", k), ef("2", k)
        esp = situacao_esperada(a[5] if a else None, b[5])
        if esp in (1, 2) and volta_esperada(a[5] if a else None, b[5]):
            esp = 5
        cont[esp] = cont.get(esp, 0) + 1
        nm = t["2"][k][2]
        m = est["mun"].setdefault(nm, [0, 0, 0, 0, 0, 0, 0, 0])   # seções, eleitores, mudou, confira, volta (seç./el.)
        m[0] += 1; m[1] += eleitores[k]
        if esp in (1, 2, 5):
            i = {1: 2, 2: 4, 5: 6}[esp]
            m[i] += 1; m[i + 1] += eleitores[k]
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
    avisos.append("situações: " + ", ".join(f"{['igual','mudou','confira','nome','sem 1º turno','volta do provisório'][k]} {v}" for k, v in sorted(cont.items())))
    return uf, len(js), len(esperado), falhas, avisos, est


def testar_mudancas():
    """data/mudancas.json deve listar exatamente as seções MUDOU (1), CONFIRA (2) e VOLTA (5) de todas as UFs."""
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
            if l[6] in (1, 2, 5):
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
    if (t.get("mudou") != sum(1 for v in esperado.values() if v[0] == 1) or t.get("confira") != sum(1 for v in esperado.values() if v[0] == 2)
            or t.get("volta") != sum(1 for v in esperado.values() if v[0] == 5)):
        falhas.append(f"totais de mudancas.json não conferem: {t}")
    print(f"mudancas.json: {len(M['locais'])} locais, {t.get('mudou')} mudaram, {t.get('confira')} para conferir, {t.get('volta')} voltam do provisório — {'OK' if not falhas else 'FALHOU'}")
    return falhas


# regiões escritas de novo aqui, de propósito, para não depender do script que gera os dados
_REGIAO = {**dict.fromkeys(["AC", "AM", "AP", "PA", "RO", "RR", "TO"], "N"),
           **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "NE"),
           **dict.fromkeys(["DF", "GO", "MS", "MT"], "CO"), **dict.fromkeys(["ES", "MG", "RJ", "SP"], "SE"),
           **dict.fromkeys(["PR", "RS", "SC"], "S"), "ZZ": "EX"}


def testar_estatisticas(ests, completo):
    """data/estatisticas.json contra os números recalculados do CSV (seções, eleitores, situações)
    e contra uma conta própria das distâncias, feita com as coordenadas de data/<UF>.json."""
    falhas = []
    caminho = RAIZ / "data" / "estatisticas.json"
    if not caminho.exists():
        return ["data/estatisticas.json não existe"]
    E = json.load(open(caminho, encoding="utf-8"))
    campos = lambda m: [m["secoes"], m["eleitores"], m["mudou_sec"], m["mudou_el"], m["confira_sec"], m["confira_el"], m["volta_sec"], m["volta_el"]]
    soma = lambda vs: [sum(x) for x in zip(*vs)] if vs else [0] * 8
    por_uf_json = {u["uf"]: u for u in E["ufs"]}
    reg_esp = {}
    for est in ests:
        uf = est["uf"]; u = por_uf_json.get(uf)
        if u is None:
            falhas.append(f"{uf} não está em estatisticas.json"); continue
        esp = soma(list(est["mun"].values()))
        if campos(u) != esp:
            falhas.append(f"{uf}: {campos(u)} em estatisticas.json, {esp} pelo CSV")
        if u["regiao"] != _REGIAO[uf]:
            falhas.append(f"{uf}: região {u['regiao']}, esperado {_REGIAO[uf]}")
        reg_esp.setdefault(_REGIAO[uf], []).append(esp)
        # municípios com alguma mudança
        obt = {norm(m["mun"]): campos(m) for m in E["municipios"] if m["uf"] == uf}
        espm = {nm: v for nm, v in est["mun"].items() if v[2] or v[4] or v[6]}
        if obt != espm:
            dif = [nm for nm in set(obt) | set(espm) if obt.get(nm) != espm.get(nm)]
            falhas.append(f"{uf}: {len(dif)} municípios com números diferentes, ex.: {dif[:3]}")
    if completo:
        for r in E["regioes"]:
            esp = soma(reg_esp.get(r["regiao"], []))
            if campos(r) != esp:
                falhas.append(f"região {r['regiao']}: {campos(r)} em estatisticas.json, {esp} pelo CSV")
        if campos(E["brasil"]) != soma([soma(v) for v in reg_esp.values()]):
            falhas.append("total do Brasil não confere com a soma das UFs")
        if len(E["ufs"]) != len(ests):
            falhas.append(f"estatisticas.json tem {len(E['ufs'])} UFs; foram testadas {len(ests)}")
    # distâncias: conta própria (fórmula equiretangular, que difere da usada no script por centímetros nesta escala)
    ds, ds_reg, sem_reg, pares_t = [], {}, {}, {}
    for u in E["ufs"]:
        D = json.load(open(RAIZ / "data" / f"{u['uf']}.json", encoding="utf-8"))
        por = {(l[0], l[1]): l for l in D["secoes"]}
        for l in D["secoes"]:
            if l[6] != 1:
                continue
            e = por.get((l[0], l[5]), l) if l[5] > 0 else l
            a, b = D["locais"][e[4]], D["locais"][e[3]]
            if None in (a["lat"], b["lat"]):
                sem_reg[_REGIAO[u["uf"]]] = sem_reg.get(_REGIAO[u["uf"]], 0) + 1
                continue
            dy = (b["lat"] - a["lat"]) * 111195
            dx = (b["lon"] - a["lon"]) * 111195 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
            ds.append(math.hypot(dx, dy))
            ds_reg.setdefault(_REGIAO[u["uf"]], []).append(ds[-1])
            pares_t.setdefault(_REGIAO[u["uf"]], {})[(u["uf"], e[4], e[3])] = ds[-1]
    dist = E["distancia"]
    if dist["com"] != len(ds) or dist["com"] + dist["sem"] != E["brasil"]["mudou_sec"]:
        falhas.append(f"distância: {dist['com']} com e {dist['sem']} sem; recontado {len(ds)} com")
    if sum(f["secoes"] for f in dist["faixas"]) != dist["com"]:
        falhas.append("faixas de distância não somam o total")
    for f in dist["faixas"]:
        n = sum(1 for d in ds if d >= f["de"] and (f["ate"] is None or d < f["ate"]))
        perto_borda = sum(1 for d in ds if any(lim is not None and abs(d - lim) < 1 for lim in (f["de"], f["ate"])))
        if abs(n - f["secoes"]) > perto_borda:
            falhas.append(f"faixa {f['de']}–{f['ate']} m: {f['secoes']} seções, recontado {n}")
    if ds:
        ds.sort(); med = ds[len(ds) // 2] if len(ds) % 2 else (ds[len(ds) // 2 - 1] + ds[len(ds) // 2]) / 2
        if abs(med - dist["mediana_m"]) > 2:
            falhas.append(f"mediana {dist['mediana_m']} m, recontado {med:.0f} m")
    # distância típica por região: recontada e em ordem da maior para a menor
    pr = dist.get("por_regiao", [])
    if {x["regiao"] for x in pr} != set(_REGIAO.values()):
        falhas.append(f"por_regiao com regiões {[x['regiao'] for x in pr]}")
    for x in pr:
        v = sorted(ds_reg.get(x["regiao"], []))
        if x["com"] != len(v) or x["sem"] != sem_reg.get(x["regiao"], 0):
            falhas.append(f"região {x['regiao']}: {x['com']} com e {x['sem']} sem; recontado {len(v)} e {sem_reg.get(x['regiao'], 0)}")
        med = (v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2) if v else None
        if (med is None) != (x["mediana_m"] is None) or (med is not None and abs(med - x["mediana_m"]) > 2):
            falhas.append(f"região {x['regiao']}: mediana {x['mediana_m']} m, recontado {med}")
        # maior distância e mudanças acima de 2 km
        mx = x.get("maior")
        if bool(v) != bool(mx) or (v and abs(v[-1] - mx["m"]) > max(2, 0.005 * v[-1])):
            falhas.append(f"região {x['regiao']}: maior {mx and mx['m']} m, recontado {v[-1] if v else None}")
        if mx and _REGIAO[mx["uf"]] != x["regiao"]:
            falhas.append(f"região {x['regiao']}: maior distância em {mx['uf']}, de outra região")
        n2 = sum(1 for d in v if d > 2000); borda = sum(1 for d in v if abs(d - 2000) < 1)
        pt = pares_t.get(x["regiao"], {})
        if x.get("mudancas") != len(pt) or abs(sum(1 for d in pt.values() if d > 2000) - x.get("mudancas_acima_2km", -99)) > borda:
            falhas.append(f"região {x['regiao']}: {x.get('mudancas')} mudanças de local ({x.get('mudancas_acima_2km')} acima de 2 km), "
                          f"recontado {len(pt)} ({sum(1 for d in pt.values() if d > 2000)})")
        if abs(n2 - x.get("acima_2km", -99)) > borda:
            falhas.append(f"região {x['regiao']}: {x.get('acima_2km')} acima de 2 km, recontado {n2}")
    maiores = [x["maior"]["m"] for x in pr if x.get("maior")]
    if maiores != sorted(maiores, reverse=True) or any(x.get("maior") for x in pr[len(maiores):]):
        falhas.append("por_regiao fora da ordem da maior para a menor distância")
    b = E["brasil"]
    print(f"estatisticas.json: {b['mudou_sec']} seções e {b['mudou_el']} eleitores mudaram, "
          f"{len(E['municipios'])} municípios, mediana {dist['mediana_m']} m — {'OK' if not falhas else 'FALHOU'}")
    return falhas


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    arqs = []
    for e in map(Path, sys.argv[1:]):
        arqs += sorted(e.glob("eleitorado_local_votacao_*_*.csv")) if e.is_dir() else [e]
    arqs = [a for a in arqs if not a.stem.upper().endswith("_BRASIL")]
    total_f, total_s, total_m, ests = 0, 0, 0, []
    for a in arqs:
        uf, n, mud, falhas, avisos, est = testar_uf(a)
        ests.append(est)
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
    ufs_json = {u["uf"] for u in json.load(open(RAIZ / "data" / "ufs.json", encoding="utf-8"))["ufs"]}
    falhas_e = testar_estatisticas(ests, completo={e["uf"] for e in ests} == ufs_json)
    total_f += len(falhas_e)
    for x in falhas_e:
        print(f"   FALHOU (estatisticas.json): {x}")
    if total_f:
        sys.exit(1)
    print("Todos os testes passaram.")


if __name__ == "__main__":
    main()
