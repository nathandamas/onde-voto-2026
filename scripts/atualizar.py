#!/usr/bin/env python3
"""
Atualização automática dos dados: baixa o cadastro do TSE, confere se mudou, regenera data/ e roda os testes.
Usado pelo GitHub Actions (.github/workflows/atualizar-dados.yml); também roda à mão.

Uso:
    python scripts/atualizar.py                        # baixa do TSE
    python scripts/atualizar.py --zip arquivo.zip      # usa um zip já baixado
    python scripts/atualizar.py --forcar               # regenera mesmo se o arquivo for igual ao anterior

Código de saída: 0 = dados atualizados ou nada a fazer; 1 = falha (data/ volta ao que era e nada deve ser publicado).
No GitHub Actions, escreve em $GITHUB_OUTPUT: mudou=sim|nao e resumo=<texto curto>.
Requer só a biblioteca padrão do Python 3.9+.
"""
import argparse, csv, hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"
VERSAO = DADOS / "versao.json"
URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/eleitorado_locais_votacao/eleitorado_local_votacao_2026.zip"
UFS = set("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split())
NOME_CSV = re.compile(r"^eleitorado_local_votacao_2026_([A-Z]{2})\.csv$")
VARIACAO_MAX = 0.02   # o total de seções do país não pode variar mais que 2% entre uma versão e outra


def saida(**kw):
    """Repassa valores para os próximos passos do GitHub Actions (ou só mostra, fora dele)."""
    destino = os.environ.get("GITHUB_OUTPUT")
    for k, v in kw.items():
        print(f"{k}={v}")
        if destino:
            with open(destino, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")


def resumo_md(texto):
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def falhar(msg):
    print(f"ERRO: {msg}", file=sys.stderr)
    resumo_md(f"### Falhou\n{msg}\n\nNada foi publicado.")
    sys.exit(1)


def baixar(url, destino, tentativas=4):
    pedido = urllib.request.Request(url, headers={"User-Agent": "onde-voto-2026 (github.com/nathandamas/onde-voto-2026)"})
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=300) as r, open(destino, "wb") as f:
                shutil.copyfileobj(r, f, length=1 << 20)
            return
        except Exception as e:   # rede instável ou servidor ocupado: tenta de novo com espera crescente
            print(f"tentativa {n} de {tentativas} falhou: {e}", file=sys.stderr)
            if n == tentativas:
                falhar(f"não foi possível baixar {url}: {e}")
            time.sleep(30 * n)


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def extrair(zip_path, pasta):
    """Extrai só os CSVs por UF (sem o consolidado BRASIL), checando nomes para não escrever fora da pasta."""
    if not zipfile.is_zipfile(zip_path):
        falhar("o arquivo baixado não é um zip válido (o TSE pode ter devolvido uma página de erro).")
    achados = set()
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            nome = Path(info.filename).name
            m = NOME_CSV.match(nome)
            if not m or m.group(1) not in UFS:
                continue
            with z.open(info) as src, open(Path(pasta) / nome, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            achados.add(m.group(1))
    faltando = sorted(UFS - achados)
    if faltando:
        falhar(f"o zip não tem os arquivos de: {', '.join(faltando)}.")


def data_geracao(pasta):
    """Data e hora de geração do TSE (a mesma em todos os arquivos)."""
    datas = set()
    for p in sorted(Path(pasta).glob("*.csv")):
        with open(p, encoding="latin-1", newline="") as f:
            r = next(csv.DictReader(f, delimiter=";"), None)
            if r:
                datas.add(f"{r['DT_GERACAO']} {r['HH_GERACAO']}")
    if len(datas) != 1:
        falhar(f"arquivos com datas de geração diferentes: {sorted(datas)}")
    return datas.pop()


def quando(txt):
    return datetime.strptime(txt, "%d/%m/%Y %H:%M:%S")


def totais():
    caminho = DADOS / "ufs.json"
    if not caminho.exists():
        return None
    ufs = json.load(open(caminho, encoding="utf-8"))["ufs"]
    return {k: sum(u.get(k, 0) for u in ufs) for k in ("secoes", "mudaram", "confira", "volta")} | {"ufs": len(ufs)}


def rodar(*args):
    print("$", " ".join(map(str, args)), flush=True)
    return subprocess.run([sys.executable, *map(str, args)], cwd=RAIZ).returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", help="usar este zip em vez de baixar")
    ap.add_argument("--url", default=os.environ.get("TSE_URL") or URL)
    ap.add_argument("--forcar", action="store_true", help="regenerar mesmo se o arquivo não mudou")
    a = ap.parse_args()

    anterior = json.load(open(VERSAO, encoding="utf-8")) if VERSAO.exists() else {}
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(a.zip) if a.zip else Path(tmp) / "tse.zip"
        if not a.zip:
            print(f"baixando {a.url}", flush=True)
            baixar(a.url, zip_path)
        tamanho = zip_path.stat().st_size
        hash_novo = sha256(zip_path)
        if hash_novo == anterior.get("sha256") and not a.forcar:
            print("O arquivo do TSE é o mesmo da última atualização. Nada a fazer.")
            resumo_md(f"Arquivo do TSE igual ao da última atualização ({anterior.get('gerado_tse')}). Nada publicado.")
            saida(mudou="nao", resumo="sem mudança")
            return

        csvs = Path(tmp) / "csv"; csvs.mkdir()
        extrair(zip_path, csvs)
        gerado = data_geracao(csvs)
        print(f"arquivo do TSE gerado em {gerado} ({tamanho / 1e6:.1f} MB)")
        if anterior.get("gerado_tse") and quando(gerado) < quando(anterior["gerado_tse"]) and not a.forcar:
            falhar(f"o arquivo baixado ({gerado}) é mais antigo que o publicado ({anterior['gerado_tse']}).")

        antes = totais()
        copia = Path(tmp) / "data_antes"
        shutil.copytree(DADOS, copia)

        def desfazer(msg):
            shutil.rmtree(DADOS); shutil.copytree(copia, DADOS)
            falhar(msg + " Os dados publicados ficaram como estavam.")

        if not rodar(RAIZ / "scripts" / "gerar_dados.py", csvs):
            desfazer("gerar_dados.py falhou.")
        if not rodar(RAIZ / "tests" / "testar_dados.py", csvs):
            desfazer("testar_dados.py encontrou divergências entre os dados gerados e o CSV do TSE.")
        depois = totais()
        if depois["ufs"] != len(UFS):
            desfazer(f"ufs.json tem {depois['ufs']} UFs; esperado {len(UFS)}.")
        if antes and abs(depois["secoes"] - antes["secoes"]) > VARIACAO_MAX * antes["secoes"]:
            desfazer(f"o total de seções foi de {antes['secoes']} para {depois['secoes']}, variação acima de {VARIACAO_MAX:.0%}.")

        with open(VERSAO, "w", encoding="utf-8") as f:
            json.dump({"fonte": a.zip and "arquivo local" or a.url, "gerado_tse": gerado, "sha256": hash_novo, "bytes": tamanho,
                       "atualizado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, f, ensure_ascii=False, indent=1)

    linha = lambda t: f"{t['mudaram']} mudaram, {t['volta']} voltam do provisório, {t['confira']} para conferir"
    texto = f"TSE {gerado}: {linha(depois)}" + (f" (antes: {linha(antes)})" if antes else "")
    print(texto)
    resumo_md(f"### Dados atualizados\n{texto}")
    saida(mudou="sim", resumo=texto.replace("\n", " "))


if __name__ == "__main__":
    main()
