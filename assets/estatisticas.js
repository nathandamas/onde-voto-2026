/* As mudanças em números — estatísticas das seções que mudaram de local do 1º para o 2º turno de 2026.
   Dados: data/estatisticas.json, gerado por scripts/gerar_dados.py com a mesma classificação das outras páginas.
   O HTML gerado aqui continua legível mesmo sem a folha de estilo (blocos em linhas próprias, numeração única). */
"use strict";

const CONFIG = Object.assign({ pastaDados: "data/", repo: "" }, window.CONFIG_LOCAL || {});
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toLocaleString("pt-BR");
const plural = (n, um, varios) => `${fmt(n)} ${n === 1 ? um : varios}`;
const nomeLista = xs => xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " e " + xs[xs.length - 1];
// percentual com 2 casas abaixo de 1% (os números são pequenos) e 1 casa acima
const pct = (n, d) => {
  if (!d) return "—";
  const v = 100 * n / d;
  return v.toLocaleString("pt-BR", { minimumFractionDigits: v < 1 ? 2 : 1, maximumFractionDigits: v < 1 ? 2 : 1 }) + "%";
};
// "cerca de 2 em cada 1.000": mais fácil de ler que 0,20%
function emCada(n, d) {
  if (!d || !n) return "";
  for (const base of [100, 1000, 10000, 100000]) {
    const v = n / d * base;
    if (v >= 0.95) return `${Number.isInteger(v) ? "" : "cerca de "}${fmt(Math.round(v))} em cada ${fmt(base)}`;
  }
  return "menos de 1 em cada 100.000";
}
const milhoes = n => n >= 1e6 ? (n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões" : fmt(n);
const distTexto = m => m < 1000 ? `${fmt(Math.round(m))} m` : `${(m / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
const nomeUF = u => u.uf === "ZZ" ? "Exterior" : u.nome;

let E = null, medida = "sec", cidadesTodas = false;

const MEDIDAS = {
  sec: { valor: x => x.mudou_sec, texto: x => `<b>${fmt(x.mudou_sec)}</b> ${x.mudou_sec === 1 ? "seção" : "seções"}`, sub: () => "",
         explica: "Quantas seções vão votar em outro local no 2º turno." },
  el:  { valor: x => x.mudou_el, texto: x => `<b>${fmt(x.mudou_el)}</b> ${x.mudou_el === 1 ? "eleitor" : "eleitores"}`, sub: () => "",
         explica: "Quantos eleitores estão nas seções que mudaram de local." },
  pct: { valor: x => x.secoes ? x.mudou_sec / x.secoes : 0, texto: x => `<b>${pct(x.mudou_sec, x.secoes)}</b>`,
         sub: x => `${fmt(x.mudou_sec)} de ${fmt(x.secoes)} seções`,
         explica: "Das seções de cada lugar, quantas em cada 100 mudaram de local. Assim dá para comparar lugares grandes e pequenos." }
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
  const munBR = b.municipios - ex.municipios, d = E.distancia;
  const cartoes = [
    [fmt(b.mudou_sec), `seç${b.mudou_sec === 1 ? "ão vai" : "ões vão"} votar em outro local`,
      `${emCada(b.mudou_sec, b.secoes)} seções do país e do exterior (${pct(b.mudou_sec, b.secoes)} de ${fmt(b.secoes)})`],
    [fmt(b.mudou_el), `eleitor${b.mudou_el === 1 ? "" : "es"} nessas seções`,
      `${emCada(b.mudou_el, b.eleitores)} dos ${milhoes(b.eleitores)} de eleitores aptos`],
    [fmt(b.locais), `loca${b.locais === 1 ? "l de votação recebe" : "is de votação recebem"} essas seções`,
      `em ${plural(munBR, "cidade do Brasil", "cidades do Brasil")}${ex.municipios ? ` e ${fmt(ex.municipios)} no exterior` : ""}`],
    [d.mediana_m == null ? "—" : distTexto(d.mediana_m), "é a distância típica até o novo local",
      d.mediana_m == null ? "" : `na metade dos casos, o novo local fica a até ${distTexto(d.mediana_m)} do antigo, em linha reta`]
  ];
  $("#destaques").innerHTML = cartoes.map(([n, t, s]) =>
    `<div class="destaque"><div class="d-num">${n}</div><div class="d-txt">${t}</div>${s ? `<div class="d-sub">${s}</div>` : ""}</div>`).join("");
  const nc = $("#nota-confira");
  if (b.confira_sec) {
    nc.innerHTML = `<b>Fora dessa conta:</b> ${plural(b.confira_sec, "seção", "seções")} (${plural(b.confira_el, "eleitor", "eleitores")}) ` +
      `aparece${b.confira_sec === 1 ? "" : "m"} no cadastro com nome ou endereço diferente, mas pode${b.confira_sec === 1 ? "" : "m"} estar no mesmo prédio. ` +
      `Esses casos ficam na coluna "Confira o endereço" da tabela.`;
    nc.hidden = false;
  }
}

function linhaBarra(rotulo, x, valor, max, M, cls = "") {
  const largura = valor ? Math.max(1.5, 100 * valor / max) : 0;
  const sub = M.sub(x);
  return `<li${cls ? ` class="${cls}"` : ""}><span class="b-rot">${rotulo}</span> <span class="b-val">${M.texto(x)}</span> ` +
    `<span class="b-trilho" aria-hidden="true"><span class="b-barra" style="width:${largura}%"></span></span>` +
    (sub ? ` <span class="b-sub">${sub}</span>` : "") + `</li>`;
}

function barrasRegiaoUF() {
  const M = MEDIDAS[medida];
  $("#explica-medida").textContent = M.explica;
  const ordem = (a, b) => M.valor(b) - M.valor(a) || a.nome.localeCompare(b.nome, "pt-BR");
  // a escala é comum a regiões e exterior; o exterior fica sempre por último
  const regioes = E.regioes.filter(r => r.regiao !== "EX").sort(ordem).concat(E.regioes.filter(r => r.regiao === "EX"));
  const maxR = Math.max(...regioes.map(M.valor), 0) || 1;
  $("#b-regioes").innerHTML = regioes.map(r => linhaBarra(esc(r.nome), r, M.valor(r), maxR, M, r.regiao === "EX" ? "fora" : "")).join("");

  const com = E.ufs.filter(u => u.uf !== "ZZ" && u.mudou_sec).sort(ordem).concat(E.ufs.filter(u => u.uf === "ZZ" && u.mudou_sec));
  const maxU = Math.max(...com.map(M.valor), 0) || 1;
  $("#b-ufs").innerHTML = com.map(u => linhaBarra(u.uf === "ZZ" ? "Exterior (voto fora do país)" : `${esc(u.nome)} <span class="sigla">${u.uf}</span>`, u, M.valor(u), maxU, M, u.uf === "ZZ" ? "fora" : "")).join("");
  const zero = E.ufs.filter(u => !u.mudou_sec).map(nomeUF).sort((a, b) => a.localeCompare(b, "pt-BR"));
  const z = $("#ufs-zero");
  z.hidden = !zero.length;
  z.innerHTML = zero.length ? `<b>Nenhuma seção mudou de local em:</b> ${esc(nomeLista(zero))}.` : "";
}

function tabelaUFs() {
  const linhas = E.ufs.filter(u => u.uf !== "ZZ").sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")).concat(E.ufs.filter(u => u.uf === "ZZ"));
  const linha = (nome, x, cls = "") => `<tr${cls}><th scope="row">${nome}</th><td>${fmt(x.mudou_sec)}</td><td>${fmt(x.mudou_el)}</td><td>${pct(x.mudou_sec, x.secoes)}</td><td>${fmt(x.secoes)}</td><td>${fmt(x.confira_sec)}</td></tr>`;
  $("#t-ufs").innerHTML = `<caption>Seções que mudaram de local, por estado. Role a tabela para os lados no celular.</caption>
    <thead><tr><th scope="col">Estado</th><th scope="col">Seções que mudaram</th><th scope="col">Eleitores nessas seções</th><th scope="col">Proporção</th><th scope="col">Total de seções</th><th scope="col">Confira o endereço (à parte)</th></tr></thead>
    <tbody>${linhas.map(u => linha(u.uf === "ZZ" ? "Exterior" : `${esc(u.nome)} (${u.uf})`, u)).join("")}</tbody>
    <tfoot>${linha("Total", E.brasil, ' class="total"')}</tfoot>`;
}

const CHAVE = { sec: m => m.mudou_sec, el: m => m.mudou_el, pct: m => m.secoes ? m.mudou_sec / m.secoes : 0 };
function ranking() {
  const uf = $("#c-uf").value, ordem = $("#c-ordem").value, k = CHAVE[ordem];
  $("#explica-pct").hidden = ordem !== "pct";
  const doFiltro = E.municipios.filter(m => !uf || m.uf === uf);
  const lista = doFiltro.filter(m => m.mudou_sec)
    .sort((a, b) => k(b) - k(a) || b.mudou_sec - a.mudou_sec || a.mun.localeCompare(b.mun, "pt-BR"));
  const soConfira = doFiltro.filter(m => !m.mudou_sec);
  const LIM = 10, mostra = cidadesTodas ? lista : lista.slice(0, LIM);
  // empates dividem a posição (1, 2, 3, 3, 5...)
  const posicao = m => 1 + lista.filter(o => k(o) > k(m) + 1e-12).length;
  const box = $("#ranking");
  box.innerHTML = mostra.map(m => {
    const p = posicao(m), uf_ = m.uf === "ZZ" ? "Exterior" : m.uf;
    const conf = m.confira_sec ? ` · mais ${fmt(m.confira_sec)} para conferir o endereço` : "";
    let val, det;
    if (ordem === "el") { val = `<b>${fmt(m.mudou_el)}</b> eleitores`; det = `${plural(m.mudou_sec, "seção", "seções")} · ${pct(m.mudou_sec, m.secoes)} das seções da cidade`; }
    else if (ordem === "pct") { val = `<b>${pct(m.mudou_sec, m.secoes)}</b> das seções`; det = `${fmt(m.mudou_sec)} de ${fmt(m.secoes)} seções · ${plural(m.mudou_el, "eleitor", "eleitores")}`; }
    else { val = `<b>${fmt(m.mudou_sec)}</b> ${m.mudou_sec === 1 ? "seção" : "seções"}`; det = `${plural(m.mudou_el, "eleitor", "eleitores")} · ${pct(m.mudou_sec, m.secoes)} das seções da cidade`; }
    return `<li value="${p}" data-pos="${p}"><div class="r-corpo"><div class="r-nome">${esc(m.mun)} <span class="sigla">${uf_}</span></div>` +
      `<div class="r-det">${det}${conf}</div></div> <div class="r-val">${val}</div></li>`;
  }).join("");
  const vazio = $("#ranking-vazio") || box.insertAdjacentElement("afterend", Object.assign(document.createElement("p"), { id: "ranking-vazio", className: "explica" }));
  const notas = [];
  if (!lista.length) notas.push("<b>Nenhuma seção mudou de local aqui.</b>");
  if (soConfira.length) {
    notas.push(soConfira.length <= 8
      ? `Só com casos de "confira o endereço": ${esc(nomeLista(soConfira.map(m => `${m.mun} (${m.uf === "ZZ" ? "exterior" : m.uf})`)))}.`
      : `Outras ${fmt(soConfira.length)} cidades têm só casos de "confira o endereço".`);
  }
  vazio.innerHTML = notas.join(" ");
  vazio.hidden = !notas.length;
  const btn = $("#mais-cidades");
  btn.hidden = lista.length <= LIM;
  btn.textContent = cidadesTodas ? `Mostrar só as ${LIM} primeiras` : `Mostrar todas as ${fmt(lista.length)} cidades`;
}

const NOME_FAIXA = f => f.ate == null ? `Mais de ${distTexto(f.de)}` : f.de === 0 ? `Menos de ${distTexto(f.ate)}` : `De ${distTexto(f.de)} a ${distTexto(f.ate)}`;
function distancia() {
  const d = E.distancia;
  $("#frase-dist").innerHTML = d.mediana_m == null ? "" :
    `Na metade dos casos, o novo local fica a até <b>${distTexto(d.mediana_m)}</b> do antigo, em linha reta.`;
  const M = { texto: f => `<b>${fmt(f.secoes)}</b> ${f.secoes === 1 ? "seção" : "seções"}`, sub: f => `${pct(f.secoes, d.com)} dos casos medidos` };
  const max = Math.max(...d.faixas.map(f => f.secoes), 1);
  $("#b-dist").innerHTML = d.faixas.map(f => linhaBarra(NOME_FAIXA(f), f, f.secoes, max, M)).join("");
  $("#explica-dist").innerHTML = `Medido em ${fmt(d.com)} das ${fmt(d.com + d.sem)} seções que mudaram. ` +
    (d.sem ? `Nas outras ${fmt(d.sem)}, falta a coordenada de um dos locais no cadastro. ` : "") +
    `Distância curta não quer dizer o mesmo lugar: pode ser outro prédio na mesma quadra ou uma coordenada imprecisa.`;
  // distância típica (mediana) por região, já em ordem da maior para a menor no JSON
  const regs = (d.por_regiao || []).filter(r => r.mediana_m != null);
  const MR = { texto: r => `<b>${distTexto(r.mediana_m)}</b>`,
               sub: r => `medida em ${fmt(r.com)} de ${plural(r.com + r.sem, "seção que mudou", "seções que mudaram")}` };
  const maxR = Math.max(...regs.map(r => r.mediana_m), 1);
  $("#b-dist-reg").innerHTML = regs.map(r => linhaBarra(esc(r.nome), r, r.mediana_m, maxR, MR)).join("");
  const exR = (d.por_regiao || []).find(r => r.regiao === "EX" && r.mediana_m == null && r.sem);
  $("#explica-dist-reg").innerHTML = (exR ? `O exterior não aparece porque o TSE não publica as coordenadas dos locais fora do país (${plural(exR.sem, "seção mudou", "seções mudaram")} lá). ` : "") +
    `Com poucas seções medidas, a distância típica de uma região pode mudar bastante se o cadastro for corrigido.`;
  $("#maiores").innerHTML = d.maiores.map(p => `<li><div class="m-cab"><b>${distTexto(p.km * 1000)}</b> · ${esc(p.mun)} (${p.uf === "ZZ" ? "exterior" : p.uf}) · ${plural(p.secoes, "seção", "seções")}</div>` +
    `<div class="m-local"><span class="m-rot">Antes:</span> ${esc(p.de)}</div><div class="m-local"><span class="m-rot">Agora:</span> ${esc(p.para)}</div></li>`).join("");
}

iniciar();
