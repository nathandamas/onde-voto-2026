/* As mudanças em números — estatísticas das seções que mudaram de local do 1º para o 2º turno de 2026.
   Dados: data/estatisticas.json, gerado por scripts/gerar_dados.py com a mesma classificação das outras páginas. */
"use strict";

const CONFIG = Object.assign({ pastaDados: "data/", repo: "" }, window.CONFIG_LOCAL || {});
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toLocaleString("pt-BR");
const plural = (n, um, varios) => `${fmt(n)} ${n === 1 ? um : varios}`;
// percentual com 2 casas abaixo de 1% (os números são pequenos) e 1 casa acima
const pct = (n, d) => {
  if (!d) return "—";
  const v = 100 * n / d;
  return v.toLocaleString("pt-BR", { minimumFractionDigits: v < 1 ? 2 : 1, maximumFractionDigits: v < 1 ? 2 : 1 }) + "%";
};
const milhoes = n => n >= 1e6 ? (n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões" : fmt(n);

let E = null, medida = "sec", cidadesTodas = false;

const MEDIDAS = {
  sec: { valor: x => x.mudou_sec, texto: x => plural(x.mudou_sec, "seção", "seções"),
         explica: "Número de seções que votam em outro local no 2º turno." },
  el:  { valor: x => x.mudou_el, texto: x => plural(x.mudou_el, "eleitor", "eleitores"),
         explica: "Eleitores aptos das seções que mudaram de local." },
  pct: { valor: x => x.secoes ? x.mudou_sec / x.secoes : 0, texto: x => pct(x.mudou_sec, x.secoes),
         explica: "Parte das seções de cada região ou estado que mudou de local. Assim, estados grandes e pequenos ficam comparáveis." }
};

async function iniciar() {
  try {
    E = window.ESTATISTICAS || await fetch(CONFIG.pastaDados + "estatisticas.json").then(r => { if (!r.ok) throw 0; return r.json(); });
  } catch {
    $("#destaques").innerHTML = "";
    const e = $("#erro"); e.textContent = "Não foi possível carregar os dados. Recarregue a página."; e.hidden = false;
    return;
  }
  $("#data-tse").textContent = (E.gerado_tse || []).join(", ");
  const repo = CONFIG.repo || (location.hostname.endsWith(".github.io") && location.pathname.split("/")[1]
    ? `https://github.com/${location.hostname.split(".")[0]}/${location.pathname.split("/")[1]}` : "");
  if (repo) { $("#link-repo").href = repo; $("#repo-txt").hidden = false; }

  destaques();
  document.querySelectorAll('input[name="medida"]').forEach(r => r.addEventListener("change", () => { medida = r.value; barrasRegiaoUF(); }));
  barrasRegiaoUF();
  tabelaUFs();

  const sel = $("#c-uf");
  [...E.ufs].filter(u => u.mudou_sec || u.confira_sec)
    .sort((a, b) => (a.uf === "ZZ") - (b.uf === "ZZ") || a.nome.localeCompare(b.nome, "pt-BR"))
    .forEach(u => { const o = document.createElement("option"); o.value = u.uf; o.textContent = u.uf === "ZZ" ? "Exterior" : `${u.nome} (${u.uf})`; sel.appendChild(o); });
  for (const id of ["#c-uf", "#c-ordem"]) $(id).addEventListener("change", () => { cidadesTodas = false; ranking(); });
  $("#mais-cidades").addEventListener("click", () => { cidadesTodas = !cidadesTodas; ranking(); });
  ranking();
  distancia();
}

function destaques() {
  const b = E.brasil, ex = E.regioes.find(r => r.regiao === "EX") || { municipios: 0 };
  const munBR = b.municipios - ex.municipios;
  const d = E.distancia;
  const cartoes = [
    [fmt(b.mudou_sec), `seç${b.mudou_sec === 1 ? "ão mudou" : "ões mudaram"} de local`, `${pct(b.mudou_sec, b.secoes)} das ${fmt(b.secoes)} seções do país e do exterior`],
    [fmt(b.mudou_el), "eleitores nessas seções", `${pct(b.mudou_el, b.eleitores)} dos ${milhoes(b.eleitores)} de eleitores aptos`],
    [fmt(b.locais), `loca${b.locais === 1 ? "l" : "is"} do 2º turno recebe${b.locais === 1 ? "" : "m"} essas seções`,
      `em ${plural(munBR, "município", "municípios")}${ex.municipios ? ` e ${plural(ex.municipios, "cidade", "cidades")} no exterior` : ""}`],
    [d.mediana_m == null ? "—" : distTexto(d.mediana_m), "é a distância típica (mediana) entre o local antigo e o novo",
      `em linha reta, nas ${fmt(d.com)} seções com coordenadas nos dois turnos`]
  ];
  $("#destaques").innerHTML = cartoes.map(([n, t, s]) => `<div class="destaque"><b>${n}</b><span>${t}</span><small>${s}</small></div>`).join("");
  const nc = $("#nota-confira");
  if (b.confira_sec) {
    nc.innerHTML = `Além disso, <b>${plural(b.confira_sec, "seção", "seções")}</b> (${plural(b.confira_el, "eleitor", "eleitores")}) aparece${b.confira_sec === 1 ? "" : "m"} com nome ou endereço diferente no cadastro e pode${b.confira_sec === 1 ? "" : "m"} estar no mesmo prédio. Elas não entram nos números de "mudou" e aparecem à parte nas tabelas.`;
    nc.hidden = false;
  }
}

function distTexto(m) {
  return m < 1000 ? `${fmt(Math.round(m))} m` : `${(m / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
}

function barras(alvo, itens, rotulo, sub) {
  const M = MEDIDAS[medida];
  const max = Math.max(...itens.map(M.valor), 0) || 1;
  $(alvo).innerHTML = itens.map(x => {
    const v = M.valor(x);
    return `<li><span class="b-rot">${rotulo(x)}</span><span class="b-trilho" aria-hidden="true"><span class="b-barra" style="width:${v ? Math.max(1, 100 * v / max) : 0}%"></span></span><span class="b-val">${M.texto(x)}${sub ? `<small>${sub(x)}</small>` : ""}</span></li>`;
  }).join("");
}

function barrasRegiaoUF() {
  const M = MEDIDAS[medida];
  $("#explica-medida").textContent = M.explica;
  const ordem = (a, b) => M.valor(b) - M.valor(a) || a.nome.localeCompare(b.nome, "pt-BR");
  const regioes = E.regioes.filter(r => r.regiao !== "EX").sort(ordem).concat(E.regioes.filter(r => r.regiao === "EX"));
  const sub = x => medida === "pct" ? `${fmt(x.mudou_sec)} de ${fmt(x.secoes)}` : "";
  barras("#b-regioes", regioes, r => esc(r.nome), sub);
  const ufs = E.ufs.filter(u => u.uf !== "ZZ").sort(ordem).concat(E.ufs.filter(u => u.uf === "ZZ"));
  barras("#b-ufs", ufs, u => u.uf === "ZZ" ? "Exterior" : `${esc(u.nome)} <span class="suave">${u.uf}</span>`, sub);
}

function tabelaUFs() {
  const linhas = E.ufs.filter(u => u.uf !== "ZZ").sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")).concat(E.ufs.filter(u => u.uf === "ZZ"));
  const linha = (nome, x, cls = "") => `<tr${cls}><th scope="row">${nome}</th><td>${fmt(x.mudou_sec)}</td><td>${fmt(x.mudou_el)}</td><td>${pct(x.mudou_sec, x.secoes)}</td><td>${fmt(x.secoes)}</td><td>${fmt(x.confira_sec)}</td></tr>`;
  $("#t-ufs").innerHTML = `<caption>Seções que mudaram de local, por estado</caption>
    <thead><tr><th scope="col">Estado</th><th scope="col">Seções que mudaram</th><th scope="col">Eleitores</th><th scope="col">% das seções</th><th scope="col">Total de seções</th><th scope="col">Confira o endereço</th></tr></thead>
    <tbody>${linhas.map(u => linha(u.uf === "ZZ" ? "Exterior" : `${esc(u.nome)} (${u.uf})`, u)).join("")}</tbody>
    <tfoot>${linha("Total", E.brasil, ' class="total"')}</tfoot>`;
}

const CHAVE = { sec: m => m.mudou_sec, el: m => m.mudou_el, pct: m => m.secoes ? m.mudou_sec / m.secoes : 0 };
function ranking() {
  const uf = $("#c-uf").value, ordem = $("#c-ordem").value, k = CHAVE[ordem];
  $("#explica-pct").hidden = ordem !== "pct";
  const lista = E.municipios.filter(m => !uf || m.uf === uf)
    .sort((a, b) => k(b) - k(a) || b.mudou_sec - a.mudou_sec || b.confira_sec - a.confira_sec || a.mun.localeCompare(b.mun, "pt-BR"));
  const LIM = 15, mostra = cidadesTodas ? lista : lista.slice(0, LIM);
  const box = $("#ranking");
  if (!lista.length) { box.innerHTML = `<li class="vazio">Nenhuma cidade com mudança neste estado.</li>`; }
  else box.innerHTML = mostra.map((m, i) => {
    const partes = [
      m.mudou_sec ? `<b>${plural(m.mudou_sec, "seção mudou", "seções mudaram")}</b>` : `<b>nenhuma seção mudou</b>`,
      m.mudou_sec ? plural(m.mudou_el, "eleitor", "eleitores") : "",
      m.mudou_sec ? `${pct(m.mudou_sec, m.secoes)} das ${fmt(m.secoes)} seções da cidade` : "",
      m.confira_sec ? `${fmt(m.confira_sec)} para conferir o endereço` : ""
    ].filter(Boolean);
    return `<li><span class="r-pos">${i + 1}</span><div><span class="r-nome">${esc(m.mun)} <span class="suave">${m.uf === "ZZ" ? "exterior" : m.uf}</span></span><span class="r-num">${partes.join(" · ")}</span></div></li>`;
  }).join("");
  const btn = $("#mais-cidades");
  btn.hidden = lista.length <= LIM;
  btn.textContent = cidadesTodas ? "Mostrar só as 15 primeiras" : `Mostrar todas as ${fmt(lista.length)} cidades`;
}

const NOMES_FAIXA = f => f.ate == null ? `mais de ${distTexto(f.de)}` : f.de === 0 ? `menos de ${distTexto(f.ate)}` : `${distTexto(f.de)} a ${distTexto(f.ate)}`;
function distancia() {
  const d = E.distancia;
  $("#explica-dist").innerHTML = `Em linha reta, nas <b>${fmt(d.com)}</b> seções que mudaram e têm coordenadas nos dois turnos. ` +
    (d.sem ? `Em ${plural(d.sem, "seção", "seções")} não dá para medir, porque falta a coordenada de um dos locais.` : "");
  const max = Math.max(...d.faixas.map(f => f.secoes), 1);
  $("#b-dist").innerHTML = d.faixas.map(f => `<li><span class="b-rot">${NOMES_FAIXA(f)}</span><span class="b-trilho" aria-hidden="true"><span class="b-barra" style="width:${f.secoes ? Math.max(1, 100 * f.secoes / max) : 0}%"></span></span><span class="b-val">${plural(f.secoes, "seção", "seções")}<small>${pct(f.secoes, d.com)} · ${plural(f.eleitores, "eleitor", "eleitores")}</small></span></li>`).join("");
  $("#maiores").innerHTML = d.maiores.map(p => `<li><b>${distTexto(p.km * 1000)}</b> em ${esc(p.mun)} (${p.uf === "ZZ" ? "exterior" : p.uf}), ${plural(p.secoes, "seção", "seções")}<br><span class="suave">De ${esc(p.de)} para ${esc(p.para)}</span></li>`).join("");
}

iniciar();
