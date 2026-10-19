/* Onde voto no 2º turno? — Eleições 2026
   Fonte única: cadastro de locais de votação do TSE (Dados Abertos).
   A situação de cada seção (mudou, confira, igual...) vem pronta de scripts/gerar_dados.py. */
"use strict";

const CONFIG = Object.assign({
  // Mapa base Positron vetorial da CARTO. Hoje carrega sem chave; se a CARTO passar a exigir,
  // crie uma chave gratuita em https://carto.com/basemaps/apikey/ e coloque em chaveCarto.
  estilo: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  chaveCarto: "",
  pastaDados: "data/",
  repo: "",   // vazio = descobre sozinho quando publicado em <usuario>.github.io/<repositorio>
  brasil: [[-74.0, -33.8], [-34.7, 5.3]]
}, window.CONFIG_LOCAL || {});

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sem = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const guarda = { ler(k) { try { return localStorage.getItem(k); } catch { return null; } }, gravar(k, v) { try { localStorage.setItem(k, v); } catch { /* sem armazenamento */ } } };

// linha: [zona, seção, município, local 2º turno, local 1º turno (-1), seção principal se agregada (-1), situação]
const Z = 0, S = 1, M = 2, L2 = 3, L1 = 4, AG = 5, ST = 6;
const IGUAL = 0, MUDOU = 1, CONFIRA = 2, NOME = 3, SEM1T = 4;

let UFS = [], UF = null, D = null, mapa = null, popup = null, comBase = false, cidadeSel = null, nomes = [], pedido = 0;
let porMun = new Map(), porZS = new Map(), secoesDoLocal = new Map();
const cache = new Map();

function efetiva(l) {
  // seção agregada vota onde está a seção principal
  if (l[AG] > 0) { const p = porZS.get(l[Z] + "-" + l[AG]); if (p) return p; }
  return l;
}
function situacao(l) {
  const e = efetiva(l);
  const st = l[ST];
  return { e, local2: e[L2], local1: e[L1], st, mudou: st === MUDOU, atencao: st === MUDOU || st === CONFIRA };
}

/* ---------- início ---------- */
async function iniciar() {
  try {
    UFS = (window.UFS || await (await fetch(CONFIG.pastaDados + "ufs.json")).json()).ufs;
  } catch {
    mostrarErro("Não foi possível carregar a lista de estados. Recarregue a página."); return;
  }
  const sel = $("#uf");
  for (const u of UFS) {
    const o = document.createElement("option");
    o.value = u.uf; o.textContent = u.uf === "ZZ" ? "Exterior (fora do Brasil)" : `${u.nome} (${u.uf})`;
    sel.appendChild(o);
  }
  $("#data-tse").textContent = [...new Set(UFS.flatMap(u => u.gerado_tse || []))].join(", ");
  const repo = CONFIG.repo || (location.hostname.endsWith(".github.io") && location.pathname.split("/")[1]
    ? `https://github.com/${location.hostname.split(".")[0]}/${location.pathname.split("/")[1]}` : "");
  if (repo) { $("#link-repo").href = repo; $("#repo-txt").hidden = false; }
  sel.addEventListener("change", () => selecionarUF(sel.value));
  montarBusca();
  montarMapa();
  const inicial = (location.hash.slice(1) || guarda.ler("uf") || "").toUpperCase();
  if (UFS.some(u => u.uf === inicial)) { sel.value = inicial; selecionarUF(inicial); }
}

function mostrarErro(t) { const e = $("#erro"); e.textContent = t; e.hidden = false; }

async function selecionarUF(uf) {
  const meu = ++pedido;
  UF = null; D = null; cidadeSel = null;
  $("#cidade").value = ""; $("#cidade").disabled = true; $("#resultado").hidden = true; $("#cidade-lista").hidden = true; $("#erro").hidden = true;
  if (!uf) { $("#cidade").placeholder = "Escolha o estado primeiro"; $("#carregando").hidden = true; atualizarMapa(); return; }
  const info = UFS.find(u => u.uf === uf);
  const aviso = $("#carregando");
  aviso.textContent = `Carregando os locais de ${info.uf === "ZZ" ? "votação no exterior" : info.nome}…`; aviso.hidden = false;
  let dados = cache.get(uf);
  if (!dados) {
    try {
      const r = await fetch(CONFIG.pastaDados + uf + ".json");
      if (!r.ok) throw new Error(r.status);
      dados = await r.json(); cache.set(uf, dados);
    } catch { if (meu === pedido) { aviso.hidden = true; mostrarErro("Não foi possível carregar os dados deste estado. Tente de novo."); } return; }
  }
  if (meu !== pedido) return;  // o usuário trocou de estado enquanto carregava
  UF = uf; D = dados;
  porMun = new Map(); porZS = new Map(); secoesDoLocal = new Map();
  for (const l of D.secoes) {
    porZS.set(l[Z] + "-" + l[S], l);
    if (!porMun.has(l[M])) porMun.set(l[M], new Map());
    const m = porMun.get(l[M]);
    if (!m.has(l[S])) m.set(l[S], []);
    m.get(l[S]).push(l);
  }
  for (const l of D.secoes) {
    const { local2 } = situacao(l);
    if (!secoesDoLocal.has(local2)) secoesDoLocal.set(local2, []);
    secoesDoLocal.get(local2).push(l);
  }
  nomes = D.municipios.map((n, i) => ({ n, i, k: sem(n) })).sort((a, b) => a.n.localeCompare(b.n, "pt-BR"));
  aviso.hidden = true;
  const ext = uf === "ZZ";
  $("#rotulo-cidade").textContent = ext ? "Sua cidade no exterior" : "Sua cidade";
  $("#cidade").placeholder = ext ? "Comece a digitar, ex.: Lisboa" : "Comece a digitar o nome";
  $("#cidade").disabled = false;
  $("#tre-txt").hidden = ext;
  $("#dica-exterior").hidden = !ext;
  if (!ext) { $("#tre-link").href = `https://www.tre-${uf.toLowerCase()}.jus.br`; $("#tre-link").textContent = `TRE-${uf}`; }
  guarda.gravar("uf", uf);
  try { history.replaceState(null, "", "#" + uf); } catch { /* ignora */ }
  atualizarMapa();
}

/* ---------- busca de cidade ---------- */
function montarBusca() {
  const inp = $("#cidade"), ul = $("#sugestoes");
  let ativos = [], pos = -1;
  const fechar = () => { ul.hidden = true; inp.setAttribute("aria-expanded", "false"); pos = -1; };
  const desenhar = () => {
    ul.innerHTML = ativos.map((c, j) => `<li role="option" id="op${j}" aria-selected="${j === pos}" data-i="${c.i}">${esc(c.n)}</li>`).join("");
    ul.hidden = !ativos.length; inp.setAttribute("aria-expanded", String(!!ativos.length));
    if (pos >= 0) inp.setAttribute("aria-activedescendant", "op" + pos); else inp.removeAttribute("aria-activedescendant");
  };
  const escolher = i => { cidadeSel = i; inp.value = D.municipios[i]; fechar(); $("#erro").hidden = true; mostrarCidade(i); $("#secao").focus(); };
  inp.addEventListener("input", () => {
    cidadeSel = null; const q = sem(inp.value);
    if (!q || !D) { ativos = []; fechar(); return; }
    ativos = nomes.filter(c => c.k.startsWith(q)).concat(nomes.filter(c => !c.k.startsWith(q) && c.k.includes(q))).slice(0, 8);
    pos = -1; desenhar();
  });
  inp.addEventListener("keydown", e => {
    if (ul.hidden) return;
    if (e.key === "ArrowDown") { pos = Math.min(pos + 1, ativos.length - 1); desenhar(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { pos = Math.max(pos - 1, 0); desenhar(); e.preventDefault(); }
    else if (e.key === "Enter" && ativos.length) { escolher(ativos[Math.max(pos, 0)].i); e.preventDefault(); }
    else if (e.key === "Escape") fechar();
  });
  ul.addEventListener("pointerdown", e => { const li = e.target.closest("li"); if (li) { e.preventDefault(); escolher(+li.dataset.i); } });
  inp.addEventListener("blur", () => setTimeout(() => {
    fechar();
    if (cidadeSel == null && D) { const exata = nomes.find(c => c.k === sem(inp.value)); if (exata) escolher(exata.i); }
  }, 120));
  $("#busca").addEventListener("submit", e => { e.preventDefault(); procurar(); });
}

function procurar(zonaEscolhida) {
  $("#erro").hidden = true;
  if (!D) {
    if (!$("#uf").value) { mostrarErro("Escolha seu estado."); $("#uf").focus(); }
    else mostrarErro("Aguarde: os dados do estado ainda estão carregando.");
    return;
  }
  if (cidadeSel == null) {
    const q = sem($("#cidade").value), i = D.municipios.findIndex(n => sem(n) === q);
    if (q && i >= 0) { cidadeSel = i; $("#cidade").value = D.municipios[i]; mostrarCidade(i); }
  }
  if (cidadeSel == null) { mostrarErro("Escolha sua cidade na lista que aparece ao digitar."); $("#cidade").focus(); return; }
  const s = parseInt($("#secao").value.replace(/\D/g, ""), 10);
  if (!s) { mostrarErro("Digite o número da sua seção."); $("#secao").focus(); return; }
  const linhas = (porMun.get(cidadeSel)?.get(s) || []).filter(l => zonaEscolhida == null || l[Z] === zonaEscolhida);
  const res = $("#resultado"); res.hidden = false;
  if (!linhas.length) {
    res.innerHTML = `<div class="res-cab mudou"><b>Seção ${s} não encontrada em ${esc(D.municipios[cidadeSel])}</b></div>
      <div class="res-corpo"><p style="margin:0">Confira o número no título de eleitor ou no e-Título. Se a seção estiver certa, ela pode ter sido extinta ou unida a outra; nesse caso, consulte o e-Título.</p></div>`;
    rolar(res); return;
  }
  if (linhas.length > 1) {
    linhas.sort((a, b) => a[Z] - b[Z]);
    res.innerHTML = `<div class="res-cab igual"><b>Qual é a sua zona?</b><small>A seção ${s} existe em mais de uma zona em ${esc(D.municipios[cidadeSel])}. A zona está no título e no e-Título, ao lado da seção. Se não souber, o bairro pode ajudar.</small></div>
      <div class="res-corpo"><div class="zonas">${linhas.map(l => { const L = D.locais[situacao(l).local2];
        return `<button type="button" data-z="${l[Z]}"><span>Zona ${l[Z]}</span><small>${esc(L.b || L.n)}</small></button>`; }).join("")}</div></div>`;
    res.querySelectorAll("[data-z]").forEach(b => b.addEventListener("click", () => procurar(+b.dataset.z)));
    rolar(res); return;
  }
  mostrarResultado(linhas[0]);
}

function enderecoTexto(L, cidade) { return [L.e, L.b, cidade, UF !== "ZZ" ? UF : ""].filter(Boolean).join(", "); }
function linkGoogle(L, cidade) {
  return L.lat != null ? `https://www.google.com/maps/dir/?api=1&destination=${L.lat},${L.lon}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(L.n + ", " + enderecoTexto(L, cidade))}`;
}
function linkOSM(L) { return L.lat != null ? `https://www.openstreetmap.org/?mlat=${L.lat}&mlon=${L.lon}#map=18/${L.lat}/${L.lon}` : null; }

const CABECALHOS = {
  [MUDOU]: ["mudou", "Atenção: seu local mudou", "É diferente do local onde você votou no 1º turno."],
  [CONFIRA]: ["mudou", "Confira o endereço", "O cadastro do TSE mostra para o seu local um nome ou endereço diferente do 1º turno. Pode ser o mesmo prédio, mas confira antes de sair."],
  [NOME]: ["igual", "Mesmo local do 1º turno", "Segundo o cadastro do TSE, sua seção vota no mesmo lugar. Só o nome do local foi atualizado."],
  [IGUAL]: ["igual", "Mesmo local do 1º turno", "Segundo o cadastro do TSE, sua seção vota no mesmo lugar."],
  [SEM1T]: ["igual", "Seu local no 2º turno", "O cadastro do TSE não traz o local desta seção no 1º turno."]
};

function mostrarResultado(l) {
  const st = situacao(l), L = D.locais[st.local2], cidade = D.municipios[l[M]];
  const [classe, titulo, sub] = CABECALHOS[st.st] || CABECALHOS[IGUAL];
  let extra = "";
  if (st.st === MUDOU || st.st === CONFIRA || st.st === NOME) {
    const A = D.locais[st.local1];
    const rot = st.st === MUDOU ? "No 1º turno você votou em" : "No 1º turno o cadastro mostrava";
    extra += `<div class="local antes${st.st === MUDOU ? " riscado" : ""}"><span class="rotulo">${rot}</span><span class="nome">${esc(A.n)}</span><span class="end">${esc(enderecoTexto(A, ""))}</span></div>`;
  }
  if (l[AG] > 0) extra += `<p class="info">Sua seção (${l[S]}) vota junto com a seção ${l[AG]}, no mesmo local.</p>`;
  if (L.coord_suspeita) extra += `<p class="info">Este local não aparece no mapa porque a coordenada do cadastro do TSE não confere com o município. Use o endereço acima.</p>`;
  const osm = linkOSM(L);
  const res = $("#resultado");
  res.innerHTML = `<div class="res-cab ${classe}"><b>${titulo}</b><small>${sub}</small></div>
    <div class="res-corpo">
      <div class="local"><span class="rotulo">No 2º turno, 25/10, você vota em</span>
        <span class="nome">${esc(L.n)}</span><span class="end">${esc(enderecoTexto(L, cidade))}</span>
        <span class="rotulo" style="margin-top:6px">Zona ${l[Z]} · Seção ${l[S]}</span></div>
      ${extra}
      <div class="acoes">
        ${L.lat != null && mapa ? `<button type="button" id="ver-mapa">Ver no mapa</button>` : ""}
        <a class="principal" href="${linkGoogle(L, cidade)}" target="_blank" rel="noopener">Como chegar (Google Maps)</a>
        ${osm ? `<a href="${osm}" target="_blank" rel="noopener">Abrir no OpenStreetMap</a>` : ""}
        <button type="button" id="copiar">Copiar endereço</button>
      </div>
      <p class="lembrete">Confirme no aplicativo e-Título antes de sair de casa. Dados do cadastro do TSE de ${esc((D.gerado_tse || []).join(", "))}.</p>
    </div>`;
  $("#ver-mapa")?.addEventListener("click", () => { $("#mapa").scrollIntoView({ block: "center" }); focar(st.local2, true); });
  $("#copiar").addEventListener("click", async e => {
    const txt = `${L.n} — ${enderecoTexto(L, cidade)}`;
    try { await navigator.clipboard.writeText(txt); e.target.textContent = "Endereço copiado"; }
    catch { e.target.textContent = txt; }
  });
  res.hidden = false;
  focar(st.local2, false);
  rolar(res);
}
function rolar(el) {
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.top > innerHeight * 0.6) el.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

/* ---------- lista da cidade ---------- */
function mostrarCidade(m) {
  const box = $("#cidade-lista");
  const grupos = new Map();
  for (const [, ls] of porMun.get(m) || []) for (const l of ls) {
    const st = situacao(l); if (!st.atencao) continue;
    const k = st.st + "|" + st.local2 + "|" + st.local1;
    if (!grupos.has(k)) grupos.set(k, { st, z: new Set(), s: [] });
    const g = grupos.get(k); g.z.add(l[Z]); g.s.push(l[S]);
  }
  const nome = D.municipios[m];
  if (!grupos.size) {
    box.innerHTML = `<p style="margin:12px 0">Segundo o cadastro do TSE, nenhuma seção de <b>${esc(nome)}</b> muda de local do 1º para o 2º turno.</p>`;
  } else {
    const total = [...grupos.values()].reduce((a, g) => a + g.s.length, 0);
    box.innerHTML = `<details open><summary>${total} seç${total > 1 ? "ões" : "ão"} de ${esc(nome)} com mudança de local ou de endereço</summary><ul>${[...grupos.values()].map(g => {
      const N = D.locais[g.st.local2], A = D.locais[g.st.local1];
      g.s.sort((a, b) => a - b);
      const tipo = g.st.mudou ? "Mudou de local" : "Confira o endereço";
      return `<li><span class="selo-mini${g.st.mudou ? " forte" : ""}">${tipo}</span><br><span class="secs">Zona ${[...g.z].join(", ")} · seç${g.s.length > 1 ? "ões" : "ão"} ${g.s.join(", ")}</span><br><b>${esc(N.n)}</b><br><span class="suave">No 1º turno: ${esc(A.n)}</span></li>`;
    }).join("")}</ul></details>`;
  }
  box.hidden = false;
  if (mapa && UF !== "ZZ") {
    const pts = D.secoes.filter(l => l[M] === m).map(l => D.locais[situacao(l).local2]).filter(L => L.lat != null);
    if (pts.length) {
      const b = new maplibregl.LngLatBounds();
      pts.forEach(L => b.extend([L.lon, L.lat]));
      mapa.fitBounds(b, { padding: 40, maxZoom: 14, duration: 600 });
    }
  }
}

/* ---------- mapa ---------- */
const ESTILO_VAZIO = { version: 8, sources: {}, layers: [{ id: "fundo", type: "background", paint: { "background-color": "#eef1f1" } }] };
const VAZIO = { type: "FeatureCollection", features: [] };

async function estiloBase() {
  if (!CONFIG.estilo) return null;
  const url = CONFIG.estilo + (CONFIG.chaveCarto ? (CONFIG.estilo.includes("?") ? "&" : "?") + "key=" + encodeURIComponent(CONFIG.chaveCarto) : "");
  try {
    const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), 6000);
    const r = await fetch(url, { signal: ctrl.signal }); clearTimeout(t);
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch { return null; }
}

async function montarMapa() {
  if (!window.maplibregl) { $("#mapa").innerHTML = '<p style="padding:16px">O mapa não carregou neste aparelho. A busca acima continua funcionando.</p>'; return; }
  const base = await estiloBase();
  comBase = !!base;
  const m = new maplibregl.Map({
    container: "mapa", style: base || ESTILO_VAZIO, bounds: CONFIG.brasil, fitBoundsOptions: { padding: 10 },
    attributionControl: false, locale: {
      "CooperativeGesturesHandler.MobileHelpText": "Use dois dedos para mover o mapa",
      "CooperativeGesturesHandler.WindowsHelpText": "Use Ctrl + rolagem para aproximar o mapa",
      "CooperativeGesturesHandler.MacHelpText": "Use ⌘ + rolagem para aproximar o mapa",
      "NavigationControl.ZoomIn": "Aproximar", "NavigationControl.ZoomOut": "Afastar",
      "Popup.Close": "Fechar", "AttributionControl.ToggleAttribution": "Mostrar créditos do mapa"
    }, cooperativeGestures: matchMedia("(pointer: coarse)").matches, maxZoom: 18, dragRotate: false, pitchWithRotate: false
  });
  m.touchZoomRotate.disableRotation();
  m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  m.addControl(new maplibregl.AttributionControl({ compact: false,
    customAttribution: comBase ? '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> © <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a> · Locais: TSE'
      : "Locais: TSE · Limites municipais: IBGE" }), "bottom-right");
  m.on("load", () => {
    m.addSource("mun", { type: "geojson", data: VAZIO });
    m.addLayer({ id: "mun-linha", type: "line", source: "mun", layout: { visibility: comBase ? "none" : "visible" }, paint: { "line-color": "#b7c4c6", "line-width": 0.6 } });
    m.addSource("locais", { type: "geojson", data: VAZIO });
    m.addLayer({ id: "normal", type: "circle", source: "locais", filter: ["==", ["get", "mud"], 0],
      paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 1, 10, 3, 15, 7], "circle-color": css("--ponto-normal"), "circle-stroke-color": "#ffffff", "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 9, 0, 12, 1] } });
    m.addLayer({ id: "mudou", type: "circle", source: "locais", filter: ["==", ["get", "mud"], 1],
      paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 3, 11, 7, 15, 11], "circle-color": "#f59e0b", "circle-stroke-color": "#13262b", "circle-stroke-width": 1.6 } });
    m.addSource("sel", { type: "geojson", data: VAZIO });
    m.addLayer({ id: "sel", type: "circle", source: "sel", paint: { "circle-radius": 16, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#0f3b46", "circle-stroke-width": 4 } });
    popup = new maplibregl.Popup({ closeButton: true, maxWidth: "290px", offset: 10 });
    for (const id of ["mudou", "normal"]) {
      m.on("click", id, e => abrirPopup(e.features[0].properties.i));
      m.on("mouseenter", id, () => m.getCanvas().style.cursor = "pointer");
      m.on("mouseleave", id, () => m.getCanvas().style.cursor = "");
    }
    mapa = m;
    atualizarMapa();
  });
}

async function atualizarMapa() {
  const bloco = $("#mapa-bloco"), nota = $("#nota-mapa");
  if (mapa) { popup?.remove(); mapa.getSource("sel").setData(VAZIO); }
  if (UF === "ZZ") {  // o TSE não informa coordenadas dos locais no exterior
    bloco.hidden = true;
    if (mapa) { mapa.getSource("locais").setData(VAZIO); mapa.getSource("mun").setData(VAZIO); }
    return;
  }
  bloco.hidden = false;
  if (!mapa) return;
  mapa.resize();
  if (!D) {
    mapa.getSource("locais").setData(VAZIO); mapa.getSource("mun").setData(VAZIO);
    mapa.fitBounds(CONFIG.brasil, { padding: 10, duration: 0 });
    nota.textContent = "Escolha um estado para ver os locais.";
    return;
  }
  const feats = [];
  for (const [i, ls] of secoesDoLocal) {
    const L = D.locais[i]; if (L.lat == null) continue;
    feats.push({ type: "Feature", geometry: { type: "Point", coordinates: [L.lon, L.lat] }, properties: { i, mud: ls.some(l => situacao(l).atencao) ? 1 : 0 } });
  }
  mapa.getSource("locais").setData({ type: "FeatureCollection", features: feats });
  nota.textContent = "Toque em um ponto para ver o nome do local e as seções. Os pontos usam as coordenadas do cadastro do TSE e podem estar algumas dezenas de metros fora do lugar exato.";
  const info = UFS.find(u => u.uf === UF);
  if (info?.bbox) mapa.fitBounds([[info.bbox[0], info.bbox[1]], [info.bbox[2], info.bbox[3]]], { padding: 20, duration: 0 });
  if (!comBase) {
    const uf = UF;
    try {
      const g = (window.CONTORNOS && window.CONTORNOS[uf]) || await (await fetch(CONFIG.pastaDados + "contornos/" + uf + ".geojson")).json();
      if (uf === UF) mapa.getSource("mun").setData(g);
    } catch { mapa.getSource("mun").setData(VAZIO); }
  }
}

function abrirPopup(i) {
  if (!mapa || !popup) return;
  const L = D.locais[i], ls = secoesDoLocal.get(i) || [];
  const mud = ls.filter(l => situacao(l).atencao);
  const porZona = {};
  ls.forEach(l => (porZona[l[Z]] = porZona[l[Z]] || []).push(l[S]));
  const secs = Object.entries(porZona).map(([z, ss]) => `Zona ${z}: ${ss.sort((a, b) => a - b).join(", ")}`).join("<br>");
  const cidade = D.municipios[ls[0]?.[M]] || "";
  popup.setLngLat([L.lon, L.lat]).setHTML(
    `<b>${esc(L.n)}</b><br>${esc(enderecoTexto(L, cidade))}
     ${mud.length ? `<p style="margin:8px 0 0;color:#92400e"><b>${mud.length} seç${mud.length > 1 ? "ões" : "ão"} com mudança de local ou endereço.</b></p>` : ""}
     <p style="margin:8px 0 0;font-size:14px">Seções no 2º turno:<br>${secs}</p>
     <p style="margin:8px 0 0"><a href="${linkGoogle(L, cidade)}" target="_blank" rel="noopener">Como chegar</a></p>`).addTo(mapa);
}

function focar(i, zoom) {
  const L = D.locais[i];
  if (!mapa || L.lat == null) return;
  mapa.getSource("sel").setData({ type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [L.lon, L.lat] }, properties: {} }] });
  mapa.flyTo({ center: [L.lon, L.lat], zoom: zoom ? 16 : Math.max(mapa.getZoom(), 13), duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 900 });
  if (zoom) abrirPopup(i);
}

iniciar();
