/* Onde as seções mudaram de local — mapa nacional das mudanças do 1º para o 2º turno de 2026.
   Dados: data/mudancas.json, gerado por scripts/gerar_dados.py com a mesma classificação da página de consulta. */
"use strict";

const CONFIG = Object.assign({
  estilo: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  chaveCarto: "",
  pastaDados: "data/",
  repo: "",
  brasil: [[-74.0, -33.8], [-34.7, 5.3]]
}, window.CONFIG_LOCAL || {});

const MUDOU = 1, CONFIRA = 2;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = n => n.toLocaleString("pt-BR");
const VAZIO = { type: "FeatureCollection", features: [] };

let M = null, UFS = [], mapa = null, popup = null, comBase = false, visiveis = [];

function filtro() {
  return { uf: $("#f-uf").value, mudou: $("#f-mudou").checked, confira: $("#f-confira").checked };
}
// seções de um local que passam pelos filtros de situação
function secoesVisiveis(L, f) {
  return L.s.filter(x => (x[2] === MUDOU && f.mudou) || (x[2] === CONFIRA && f.confira));
}
function nomeUF(uf) { return uf === "ZZ" ? "Exterior" : (UFS.find(u => u.uf === uf)?.nome || uf); }
function endereco(L) { return [L.e, L.b, L.mun, L.uf !== "ZZ" ? L.uf : ""].filter(Boolean).join(", "); }
function linkGoogle(L) {
  return L.lat != null ? `https://www.google.com/maps/dir/?api=1&destination=${L.lat},${L.lon}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(L.n + ", " + endereco(L))}`;
}

async function iniciar() {
  try {
    const [m, u] = await Promise.all([
      window.MUDANCAS || fetch(CONFIG.pastaDados + "mudancas.json").then(r => { if (!r.ok) throw 0; return r.json(); }),
      window.UFS || fetch(CONFIG.pastaDados + "ufs.json").then(r => { if (!r.ok) throw 0; return r.json(); })
    ]);
    M = m; UFS = u.ufs;
  } catch {
    $("#resumo").textContent = "";
    const e = $("#erro"); e.textContent = "Não foi possível carregar os dados. Recarregue a página."; e.hidden = false;
    return;
  }
  $("#data-tse").textContent = (M.gerado_tse || []).join(", ");
  const repo = CONFIG.repo || (location.hostname.endsWith(".github.io") && location.pathname.split("/")[1]
    ? `https://github.com/${location.hostname.split(".")[0]}/${location.pathname.split("/")[1]}` : "");
  if (repo) { $("#link-repo").href = repo; $("#repo-txt").hidden = false; }

  // estados com alguma mudança, com o total de seções
  const porUF = {};
  for (const L of M.locais) porUF[L.uf] = (porUF[L.uf] || 0) + L.s.length;
  const sel = $("#f-uf");
  Object.keys(porUF).sort((a, b) => (a === "ZZ") - (b === "ZZ") || nomeUF(a).localeCompare(nomeUF(b), "pt-BR")).forEach(uf => {
    const o = document.createElement("option");
    o.value = uf; o.textContent = `${uf === "ZZ" ? "Exterior" : nomeUF(uf) + " (" + uf + ")"} · ${fmt(porUF[uf])} seç${porUF[uf] > 1 ? "ões" : "ão"}`;
    sel.appendChild(o);
  });
  const inicial = location.hash.slice(1).toUpperCase();
  if (porUF[inicial]) sel.value = inicial;

  for (const id of ["#f-uf", "#f-mudou", "#f-confira"]) $(id).addEventListener("change", () => aplicar(true));
  aplicar(false);
  montarMapa();
}

function aplicar(enquadrar) {
  const f = filtro();
  visiveis = [];
  M.locais.forEach((L, i) => {
    if (f.uf && L.uf !== f.uf) return;
    const s = secoesVisiveis(L, f);
    if (s.length) visiveis.push({ i, L, s });
  });
  const nM = visiveis.reduce((a, v) => a + v.s.filter(x => x[2] === MUDOU).length, 0);
  const nC = visiveis.reduce((a, v) => a + v.s.filter(x => x[2] === CONFIRA).length, 0);
  const onde = f.uf ? (f.uf === "ZZ" ? "no exterior" : `em ${nomeUF(f.uf)}`) : "no Brasil e no exterior";
  $("#resumo").innerHTML = `<b>${fmt(nM)}</b> seç${nM === 1 ? "ão mudou" : "ões mudaram"} de local e <b>${fmt(nC)}</b> ${nC === 1 ? "precisa" : "precisam"} de conferência, em <b>${fmt(visiveis.length)}</b> loca${visiveis.length === 1 ? "l" : "is"} ${onde}.`;
  try { history.replaceState(null, "", f.uf ? "#" + f.uf : location.pathname); } catch { /* ignora */ }
  desenharLista();
  atualizarMapa(enquadrar);
}

/* ---------- lista ---------- */
const ROTULO = { [MUDOU]: "Mudou de local", [CONFIRA]: "Confira o endereço" };
function desenharLista() {
  const box = $("#lista");
  if (!visiveis.length) { box.innerHTML = `<p class="vazio">Nenhum local com os filtros escolhidos.</p>`; return; }
  let html = "", ufAtual = null, munAtual = null;
  for (const { i, L, s } of visiveis) {
    if (L.uf !== ufAtual) { if (ufAtual !== null) html += "</div>"; html += `<h3 class="uf-titulo">${esc(nomeUF(L.uf))}</h3><div class="uf-grupo">`; ufAtual = L.uf; munAtual = null; }
    if (L.mun !== munAtual) { html += `<p class="mun-titulo">${esc(L.mun)}</p>`; munAtual = L.mun; }
    const nM = s.filter(x => x[2] === MUDOU).length, nC = s.length - nM;
    const partes = [nM ? `${nM} mud${nM > 1 ? "aram" : "ou"} de local` : "", nC ? `${nC} para conferir` : ""].filter(Boolean).join(" · ");
    html += `<article class="card-mud" id="l${i}">
      <b class="nome">${esc(L.n)}</b>
      <span class="end">${esc(endereco(L))}</span>
      <details><summary>${s.length} seç${s.length > 1 ? "ões" : "ão"}: ${partes}</summary>
        <ul>${s.map(x => `<li><span class="selo-mini${x[2] === MUDOU ? " forte" : ""}">${ROTULO[x[2]]}</span> <b>Zona ${x[0]} · Seção ${x[1]}</b><br><span class="suave">No 1º turno: ${esc(x[3])}${x[4] ? " — " + esc(x[4]) : ""}</span></li>`).join("")}</ul>
      </details>
      <div class="acoes-mini">
        ${L.lat != null ? `<button type="button" data-ver="${i}">Ver no mapa</button>` : `<span class="suave">Sem ponto no mapa</span>`}
        <a href="${linkGoogle(L)}" target="_blank" rel="noopener">Como chegar</a>
      </div>
    </article>`;
  }
  html += "</div>";
  box.innerHTML = html;
  box.querySelectorAll("[data-ver]").forEach(b => b.addEventListener("click", () => {
    $("#mapa").scrollIntoView({ block: "center" }); focar(+b.dataset.ver);
  }));
}

/* ---------- mapa ---------- */
const ESTILO_VAZIO = { version: 8, sources: {}, layers: [{ id: "fundo", type: "background", paint: { "background-color": "#eef1f1" } }] };

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
  if (!window.maplibregl) { $("#mapa").innerHTML = '<p style="padding:16px">O mapa não carregou neste aparelho. A lista abaixo continua funcionando.</p>'; return; }
  const base = await estiloBase();
  comBase = !!base;
  const m = new maplibregl.Map({
    container: "mapa", style: base || ESTILO_VAZIO, bounds: CONFIG.brasil, fitBoundsOptions: { padding: 24 },
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
    m.addSource("pts", { type: "geojson", data: VAZIO });
    // raio cresce com o número de seções e um pouco com o zoom
    const raio = (k) => ["*", k, ["interpolate", ["linear"], ["get", "ns"], 1, 4, 5, 6.5, 20, 10, 60, 15]];
    m.addLayer({ id: "pts", type: "circle", source: "pts",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, raio(1), 10, raio(1.5), 15, raio(2)],
        "circle-color": ["match", ["get", "tipo"], 1, "#f59e0b", "#fde7c4"],
        "circle-stroke-color": ["match", ["get", "tipo"], 1, "#13262b", "#a14507"],
        "circle-stroke-width": ["match", ["get", "tipo"], 1, 1.4, 2.2],
        "circle-opacity": 0.95
      } });
    m.addSource("sel", { type: "geojson", data: VAZIO });
    m.addLayer({ id: "sel", type: "circle", source: "sel", paint: { "circle-radius": 20, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#0f3b46", "circle-stroke-width": 4 } });
    popup = new maplibregl.Popup({ closeButton: true, maxWidth: "300px", offset: 10 });
    m.on("click", "pts", e => abrirPopup(e.features[0].properties.i));
    m.on("mouseenter", "pts", () => m.getCanvas().style.cursor = "pointer");
    m.on("mouseleave", "pts", () => m.getCanvas().style.cursor = "");
    mapa = m;
    atualizarMapa(true);
  });
}

async function atualizarMapa(enquadrar) {
  const f = filtro();
  $("#mapa-bloco").hidden = f.uf === "ZZ";   // o TSE não informa coordenadas dos locais no exterior
  if (!mapa) return;
  popup?.remove(); mapa.getSource("sel").setData(VAZIO);
  const feats = visiveis.filter(v => v.L.lat != null).map(({ i, L, s }) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [L.lon, L.lat] },
    properties: { i, ns: s.length, tipo: s.some(x => x[2] === MUDOU) ? 1 : 2 }
  }));
  // pontos menores por cima dos maiores
  feats.sort((a, b) => b.properties.ns - a.properties.ns);
  mapa.getSource("pts").setData({ type: "FeatureCollection", features: feats });
  if (enquadrar) {
    if (f.uf && feats.length) {
      const b = new maplibregl.LngLatBounds(); feats.forEach(x => b.extend(x.geometry.coordinates));
      mapa.fitBounds(b, { padding: 50, maxZoom: 12, duration: 0 });
    } else if (!f.uf) mapa.fitBounds(CONFIG.brasil, { padding: 24, duration: 0 });
  }
  if (!comBase) {
    const uf = f.uf;
    if (!uf || uf === "ZZ") { mapa.getSource("mun").setData(VAZIO); return; }
    try {
      const g = await (await fetch(CONFIG.pastaDados + "contornos/" + uf + ".geojson")).json();
      if (filtro().uf === uf) mapa.getSource("mun").setData(g);
    } catch { mapa.getSource("mun").setData(VAZIO); }
  }
}

function abrirPopup(i) {
  if (!mapa || !popup) return;
  const v = visiveis.find(x => x.i === i); if (!v) return;
  const { L, s } = v;
  const max = 6;
  popup.setLngLat([L.lon, L.lat]).setHTML(
    `<b>${esc(L.n)}</b><br>${esc(endereco(L))}
     <p style="margin:8px 0 0;font-size:14px">${s.slice(0, max).map(x => `<b>Zona ${x[0]} · Seção ${x[1]}</b> <span style="color:${x[2] === MUDOU ? "#92400e" : "#4e6268"}">(${x[2] === MUDOU ? "mudou" : "conferir"})</span><br>no 1º turno: ${esc(x[3])}`).join("<br>")}
     ${s.length > max ? `<br>… e mais ${s.length - max}` : ""}</p>
     <p style="margin:8px 0 0"><a href="#l${i}" data-lista="${i}">Ver na lista</a> · <a href="${linkGoogle(L)}" target="_blank" rel="noopener">Como chegar</a></p>`).addTo(mapa);
  popup.getElement().querySelector("[data-lista]")?.addEventListener("click", e => {
    e.preventDefault();
    const card = document.getElementById("l" + i);
    card?.querySelector("details")?.setAttribute("open", "");
    card?.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
}

function focar(i) {
  const v = visiveis.find(x => x.i === i); if (!mapa || !v || v.L.lat == null) return;
  mapa.getSource("sel").setData({ type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [v.L.lon, v.L.lat] }, properties: {} }] });
  mapa.flyTo({ center: [v.L.lon, v.L.lat], zoom: 15, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 900 });
  abrirPopup(i);
}

iniciar();
