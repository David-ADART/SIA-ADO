const S = {
  params: {},
  costes: {},
  agentes: [],
  conexiones: [],
  has: [],
  hit: [],
  him: [],
  series_estados: [],
  series_costes: [],
  estadisticos: null,
  brotes: [],
  viewDay: 0,
  day: 0,
  mostrarRadios: false,
  mostrarRutas: true,
  proyect: null,
  charts: {}
};

const PARAM_META = [
  ["T", "Territorio km (T)", "Lado del cuadrado, km. Por defecto 60."],
  ["Nc", "Granjas de cría (Nc)", "Número de granjas de cría (GC)."],
  ["Ne", "Granjas de engorde (Ne)", "Número de granjas de engorde (GE)."],
  ["Nm", "Mataderos (Nm)", "Número de mataderos (MA)."],
  ["semilla", "Semilla RNG", "Misma semilla + mismos parámetros = mismo mapa."],
  ["max_dias", "Tope de días", "Freno de seguridad de la simulación."]
];
const AGENTE_META = [
  ["AR", "Radio seguridad km (AR)", "Si D(A,B) ≤ AR(A) entonces V(A,B)=1."],
  ["PIMS", "P. infectar medio (PIMS)", "Agente silente contamina su medio."],
  ["PIME", "P. infectarse del medio (PIME)", "El medio de Y infecta al agente Y."],
  ["PITS", "P. infectar transporte (PITS)", "Carga de un camión contaminado."],
  ["PITE", "P. infectarse del transporte (PITE)", "Descarga de un camión contaminado."],
  ["PM", "P. medio→medio a 1 km (PM)", "PM(A,B) a 1 km, luego se divide por max(1,D)."],
  ["DI1", "Días silente→declarada (DI1)", ""],
  ["DI2", "Días declarada→desinfección (DI2)", ""],
  ["DI3", "Días desinfección→limpio (DI3)", ""]
];
const COST_META = [
  ["CFCG", "CFCG cuarentena granja €/día"],
  ["CACG", "CACG animal cuarentena granja €"],
  ["CFCM", "CFCM cuarentena matadero €/día"],
  ["CACM", "CACM animal no sacrificado €"],
  ["CFLG", "CFLG limpieza granja €/día"],
  ["CALG", "CALG animal eliminado granja €"],
  ["CFLM", "CFLM limpieza matadero €/día"],
  ["CALM", "CALM animal limpiado matadero €"]
];

function $(id) { return document.getElementById(id); }

function setStatus(msg) { $("status-line").textContent = msg; }

function leerForms() {
  PARAM_META.concat(AGENTE_META).forEach(([k]) => {
    const el = document.getElementById("p-" + k);
    if (el) S.params[k] = el.value.includes(".") || ["T","AR","PIMS","PIME","PITS","PITE","PM"].includes(k)
      ? Number(el.value) : parseInt(el.value, 10);
  });
  COST_META.forEach(([k]) => {
    const el = document.getElementById("c-" + k);
    if (el) S.costes[k] = Number(el.value);
  });
}

function pintarCampos(host, meta, src, prefix) {
  host.innerHTML = "";
  meta.forEach(([k, lab, help]) => {
    const d = document.createElement("div");
    d.className = "field";
    d.innerHTML = `<label title="${help || ""}">${lab}</label><input id="${prefix}-${k}" type="number" step="any" />`;
    host.appendChild(d);
    d.querySelector("input").value = src[k];
  });
}

function tabla(el, rows) {
  if (!rows || !rows.length) { el.innerHTML = "<tr><td>Sin datos</td></tr>"; return; }
  const cols = Object.keys(rows[0]);
  el.innerHTML = "<thead><tr>" + cols.map((c) => "<th>" + c + "</th>").join("") + "</tr></thead><tbody>" +
    rows.slice(0, 400).map((r) => "<tr>" + cols.map((c) => "<td>" + r[c] + "</td>").join("") + "</tr>").join("") +
    "</tbody>";
}

function kpis() {
  const vista = agentesDelDia(S);
  const n = vista.length;
  const inf = vista.filter((a) => Number(a.AI) !== 0).length;
  const cua = vista.filter((a) => Number(a.AC) === 1).length;
  const medio = vista.reduce((s, a) => s + Number(a.MI || 0), 0);
  let estado = "STANDBY", cls = "";
  if (!n) { estado = "STANDBY"; }
  else if (inf === 0 && medio === 0) { estado = "ESTABLE"; cls = "ok"; }
  else if (vista.some((a) => Number(a.AI) === 2)) { estado = "BROTE DECLARADO"; cls = "alert"; }
  else { estado = "VIGILANCIA"; cls = "warn"; }
  $("kpis").innerHTML = `
    <div class="kpi"><div class="lbl">DÍA TÁCTICO</div><div class="val">${String(S.viewDay).padStart(3,"0")} / ${String(S.day).padStart(3,"0")}</div></div>
    <div class="kpi"><div class="lbl">AGENTES N</div><div class="val">${n}</div></div>
    <div class="kpi ${inf ? "alert" : "ok"}"><div class="lbl">INFECTADOS</div><div class="val">${inf}</div></div>
    <div class="kpi ${cua ? "warn" : ""}"><div class="lbl">CUARENTENA</div><div class="val">${cua}</div></div>
    <div class="kpi ${cls}"><div class="lbl">ESTADO</div><div class="val">${estado}</div></div>`;
}

function refrescarBrotes() {
  const sel = $("sel-brotes");
  const prev = new Set(S.brotes.map(Number));
  sel.innerHTML = "";
  S.agentes.forEach((a) => {
    const o = document.createElement("option");
    o.value = a.AID;
    o.textContent = a.AID + " · " + a.AT;
    o.selected = prev.has(Number(a.AID));
    sel.appendChild(o);
  });
}

function leerBrotes() {
  S.brotes = Array.from($("sel-brotes").selectedOptions).map((o) => Number(o.value));
}

function payloadSimular() {
  leerForms();
  leerBrotes();
  return Object.assign({}, S.params, {
    costes: S.costes,
    brotes: S.brotes,
    agentes: S.agentes,
    conexiones: S.conexiones
  });
}

function aplicarResultado(data) {
  S.agentes = data.agentes || S.agentes;
  S.conexiones = data.conexiones || S.conexiones;
  S.has = data.has || [];
  S.hit = data.hit || [];
  S.him = data.him || [];
  S.series_estados = data.series_estados || [];
  S.series_costes = data.series_costes || [];
  S.estadisticos = data.estadisticos || null;
  S.params = data.params || S.params;
  S.day = Number(data.dia_final || 0);
  S.viewDay = S.day;
  S.brotes = [].concat(data.brotes || S.brotes).map(Number).filter((n) => !Number.isNaN(n));
  $("slider-dia").max = Math.max(S.day, 0);
  $("slider-dia").value = S.viewDay;
  $("slider-dia").disabled = S.day === 0;
  $("slider-val").textContent = S.viewDay;
  $("btn-simular").disabled = S.agentes.length === 0;
  $("btn-reiniciar").disabled = S.agentes.length === 0;
  $("btn-play").disabled = S.day === 0;
  tabla($("tabla-agentes"), S.agentes);
  tabla($("tabla-conexiones"), S.conexiones);
  tabla($("tabla-has"), S.has);
  tabla($("tabla-hit"), S.hit);
  tabla($("tabla-him"), S.him);
  refrescarBrotes();
  pintarStats();
  pintarCharts();
  kpis();
  S.proyect = dibujarMapa($("mapa"), S);
}

function pintarStats() {
  const e = S.estadisticos;
  if (!e) { $("stats-box").textContent = "Sin simulación todavía."; return; }
  const items = [
    ["Día final", S.day],
    ["Pico silente", e.pico_silente.valor + " (d" + e.pico_silente.dia + ")"],
    ["Pico declarada", e.pico_declarada.valor + " (d" + e.pico_declarada.dia + ")"],
    ["Pico desinfección", e.pico_desinfeccion.valor + " (d" + e.pico_desinfeccion.dia + ")"],
    ["Pico cuarentena", e.pico_cuarentena.valor + " (d" + e.pico_cuarentena.dia + ")"],
    ["Inf. transporte", e.infecciones_transporte],
    ["Inf. medio→agente", e.infecciones_medio_agente],
    ["Coste acumulado", Math.round(e.coste_acumulado).toLocaleString("es-ES") + " €"]
  ];
  $("stats-box").innerHTML = items.map(([k, v]) => `<div class="stat"><b>${k}</b>${v}</div>`).join("");
}

function mkChart(id, labels, datasets) {
  if (S.charts[id]) S.charts[id].destroy();
  const ctx = $(id).getContext("2d");
  S.charts[id] = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#d7e3c6" } } },
      scales: {
        x: { ticks: { color: "#8aa078" }, grid: { color: "#243322" }, title: { display: true, text: "Día", color: "#8aa078" } },
        y: { ticks: { color: "#8aa078" }, grid: { color: "#243322" } }
      }
    }
  });
}

function pintarCharts() {
  const ser = S.series_estados || [];
  const sco = S.series_costes || [];
  if (!ser.length) return;
  const lab = ser.map((r) => r.dia);
  mkChart("chart-n", lab, [
    { label: "Silente", data: ser.map((r) => r.n_silente), borderColor: "#ffd000", tension: 0.2 },
    { label: "Declarada", data: ser.map((r) => r.n_declarada), borderColor: "#ff3b3b", tension: 0.2 },
    { label: "Desinfección", data: ser.map((r) => r.n_desinfeccion), borderColor: "#3ec6ff", tension: 0.2 },
    { label: "Cuarentena", data: ser.map((r) => r.n_cuarentena), borderColor: "#ffffff", tension: 0.2 }
  ]);
  mkChart("chart-anim", lab, [
    { label: "Anim. silente", data: ser.map((r) => r.anim_silente), borderColor: "#ffd000", tension: 0.2 },
    { label: "Anim. declarada", data: ser.map((r) => r.anim_declarada), borderColor: "#ff3b3b", tension: 0.2 },
    { label: "Anim. desinfección", data: ser.map((r) => r.anim_desinfeccion), borderColor: "#3ec6ff", tension: 0.2 },
    { label: "Anim. cuarentena", data: ser.map((r) => r.anim_cuarentena), borderColor: "#ffffff", tension: 0.2 }
  ]);
  if (sco.length) {
    mkChart("chart-cost", sco.map((r) => r.dia), [
      { label: "Cuarentena granjas", data: sco.map((r) => r.c_c_granja), borderColor: "#ffd000", tension: 0.2 },
      { label: "Cuarentena mataderos", data: sco.map((r) => r.c_c_mata), borderColor: "#ff7a18", tension: 0.2 },
      { label: "Limpieza granjas", data: sco.map((r) => r.c_l_granja), borderColor: "#3ec6ff", tension: 0.2 },
      { label: "Limpieza mataderos", data: sco.map((r) => r.c_l_mata), borderColor: "#7cff6b", tension: 0.2 }
    ]);
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("panel-" + btn.dataset.tab).classList.add("active");
  });
});

$("btn-generar").addEventListener("click", async () => {
  try {
    leerForms();
    setStatus("Generando teatro…");
    const data = await API.generar(S.params);
    S.agentes = data.agentes;
    S.conexiones = data.conexiones;
    S.params = data.params || S.params;
    S.has = []; S.hit = []; S.him = [];
    S.day = 0; S.viewDay = 0; S.estadisticos = null;
    S.brotes = [];
    $("btn-simular").disabled = false;
    $("btn-reiniciar").disabled = false;
    $("btn-play").disabled = true;
    tabla($("tabla-agentes"), S.agentes);
    tabla($("tabla-conexiones"), S.conexiones);
    refrescarBrotes();
    kpis();
    S.proyect = dibujarMapa($("mapa"), S);
    setStatus("Teatro listo · N=" + S.agentes.length + " · marque un brote e inicie");
  } catch (err) {
    setStatus("ERROR: " + err.message);
  }
});

$("btn-simular").addEventListener("click", async () => {
  try {
    leerBrotes();
    if (!S.agentes.length) { setStatus("Genere agentes primero."); return; }
    if (!S.brotes.length) { setStatus("Marque al menos un brote silente."); return; }
    setStatus("Simulando vía POST /simular …");
    const data = await API.simular(payloadSimular());
    aplicarResultado(data);
    setStatus((data.estable ? "ESTABLE" : "TOPE DE DÍAS") + " en día " + data.dia_final +
      " · coste " + Math.round(data.estadisticos.coste_acumulado).toLocaleString("es-ES") + " €");
  } catch (err) {
    setStatus("ERROR: " + err.message);
  }
});

$("btn-reiniciar").addEventListener("click", () => {
  S.has = []; S.hit = []; S.him = [];
  S.day = 0; S.viewDay = 0; S.estadisticos = null;
  S.agentes = S.agentes.map((a) => Object.assign({}, a, { AI: 0, AC: 0, MI: 0 }));
  $("btn-play").disabled = true;
  $("slider-dia").max = 0; $("slider-dia").value = 0; $("slider-dia").disabled = true;
  tabla($("tabla-has"), []); tabla($("tabla-hit"), []); tabla($("tabla-him"), []);
  kpis();
  S.proyect = dibujarMapa($("mapa"), S);
  setStatus("Reiniciado · AI/AC/MI = 0");
});

let playTimer = null;
$("btn-play").addEventListener("click", () => {
  if (playTimer) { clearInterval(playTimer); playTimer = null; return; }
  S.viewDay = 0;
  playTimer = setInterval(() => {
    if (S.viewDay >= S.day) { clearInterval(playTimer); playTimer = null; return; }
    S.viewDay += 1;
    $("slider-dia").value = S.viewDay;
    $("slider-val").textContent = S.viewDay;
    kpis();
    S.proyect = dibujarMapa($("mapa"), S);
  }, 280);
});

$("slider-dia").addEventListener("input", (e) => {
  S.viewDay = Number(e.target.value);
  $("slider-val").textContent = S.viewDay;
  kpis();
  S.proyect = dibujarMapa($("mapa"), S);
});
$("chk-radios").addEventListener("change", (e) => { S.mostrarRadios = e.target.checked; S.proyect = dibujarMapa($("mapa"), S); });
$("chk-rutas").addEventListener("change", (e) => { S.mostrarRutas = e.target.checked; S.proyect = dibujarMapa($("mapa"), S); });
$("sel-brotes").addEventListener("change", leerBrotes);
$("mapa").addEventListener("click", (evt) => {
  if (S.day !== 0) return;
  const aid = aidEnClick($("mapa"), evt, S.proyect);
  if (aid == null) return;
  const set = new Set(S.brotes.map(Number));
  if (set.has(Number(aid))) set.delete(Number(aid)); else set.add(Number(aid));
  S.brotes = Array.from(set);
  S.agentes = S.agentes.map((a) => Object.assign({}, a, {
    AI: set.has(Number(a.AID)) ? 1 : 0,
    AC: 0,
    MI: 0
  }));
  refrescarBrotes();
  kpis();
  S.proyect = dibujarMapa($("mapa"), S);
});

(async function init() {
  try {
    const d = await API.defaults();
    S.params = d.params;
    S.costes = d.costes;
    pintarCampos($("form-params"), PARAM_META, S.params, "p");
    pintarCampos($("form-agente"), AGENTE_META, S.params, "p");
    pintarCampos($("form-costes"), COST_META, S.costes, "c");
    kpis();
    S.proyect = dibujarMapa($("mapa"), S);
    setStatus("API R conectada · pulse GENERAR AGENTES");
  } catch (err) {
    setStatus("Sin API: " + err.message + " · arranque plumber en el puerto 8000");
    S.params = { T: 60, Nc: 8, Ne: 12, Nm: 3, AR: 5, PIMS: 0.2, PIME: 0.2, PITS: 0.9, PITE: 0.9, DI1: 3, DI2: 4, DI3: 15, PM: 0.05, semilla: 42, max_dias: 365 };
    S.costes = { CFCG: 200, CACG: 4, CFCM: 300, CACM: 400, CFLG: 1000, CALG: 10, CFLM: 600, CALM: 15 };
    pintarCampos($("form-params"), PARAM_META, S.params, "p");
    pintarCampos($("form-agente"), AGENTE_META, S.params, "p");
    pintarCampos($("form-costes"), COST_META, S.costes, "c");
    kpis();
    S.proyect = dibujarMapa($("mapa"), S);
  }
})();
