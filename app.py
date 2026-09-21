"""
SIA-ADO — interfaz Streamlit del simulador de peste porcina.

Ejecutar desde la carpeta del proyecto:

    streamlit run app.py

El modelo (agentes, transportes, medio, tablas HAS/HIT/HIM) vive en
simulation.py. Aquí solo está el cuadro de mandos.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulation import (
    NOMBRE_INFECCION,
    NOMBRE_TIPO,
    Simulacion,
    agentes_en_dia,
    costes_por_defecto,
    series_costes,
    series_estados,
    sistema_estable,
    valores_por_defecto,
)

# ---------------------------------------------------------------------------
# Configuración de página y estilo táctico
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SIA-ADO | Peste Porcina",
    page_icon="🐗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at top, #152016 0%, #0b0f0a 55%, #070907 100%) !important;
    color: #d7e3c6;
}
.block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1500px; }

h1, h2, h3, h4 { font-family: 'Rajdhani', sans-serif; letter-spacing: 0.08em; text-transform: uppercase; }
p, label, span, div { font-family: 'Rajdhani', sans-serif; }

.tactical-banner {
    border: 1px solid #3d5a32;
    background:
        linear-gradient(90deg, rgba(197,165,114,0.08) 0%, rgba(11,15,10,0.4) 40%, rgba(255,77,46,0.06) 100%),
        repeating-linear-gradient(90deg, rgba(61,90,50,0.15) 0 12px, transparent 12px 24px);
    padding: 0.85rem 1.2rem;
    margin-bottom: 1rem;
    position: relative;
}
.tactical-banner:before, .tactical-banner:after {
    content: "";
    position: absolute; width: 12px; height: 12px; border-color: #c5a572; border-style: solid;
}
.tactical-banner:before { top: -1px; left: -1px; border-width: 2px 0 0 2px; }
.tactical-banner:after  { bottom: -1px; right: -1px; border-width: 0 2px 2px 0; }
.tactical-banner .kicker {
    font-family: 'Share Tech Mono', monospace;
    color: #c5a572; font-size: 0.78rem; letter-spacing: 0.28em;
}
.tactical-banner h1 {
    margin: 0.15rem 0 0 0; font-size: 1.7rem; color: #e8f0d8;
}
.tactical-banner .sub {
    font-family: 'Share Tech Mono', monospace; color: #8aa078; font-size: 0.82rem;
}

.kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.6rem; margin: 0.4rem 0 0.9rem 0; }
.kpi {
    border: 1px solid #2f4228;
    background: rgba(12, 18, 11, 0.85);
    padding: 0.55rem 0.7rem 0.45rem 0.7rem;
}
.kpi .lbl {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.68rem; letter-spacing: 0.16em; color: #8aa078;
}
.kpi .val {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.35rem; color: #e8f0d8; line-height: 1.2;
}
.kpi.alert .val { color: #ff4d2e; }
.kpi.warn .val { color: #ffd000; }
.kpi.ok .val { color: #7cff6b; }

.legend-bar {
    display: flex; flex-wrap: wrap; gap: 0.9rem 1.4rem;
    border: 1px solid #2f4228; padding: 0.55rem 0.8rem; margin-top: 0.4rem;
    font-family: 'Share Tech Mono', monospace; font-size: 0.78rem; color: #c5d3b4;
}
.dot { display:inline-block; width: 10px; height: 10px; margin-right: 6px; vertical-align: -1px; }
.sq { display:inline-block; width: 10px; height: 10px; margin-right: 6px; vertical-align: -1px; }
.dm { display:inline-block; width: 8px; height: 8px; margin-right: 6px; vertical-align: 0px;
      transform: rotate(45deg); }

div[data-testid="stTabs"] button { font-family: 'Rajdhani', sans-serif; letter-spacing: 0.12em; font-weight: 700; }
.stButton>button {
    font-family: 'Share Tech Mono', monospace;
    letter-spacing: 0.08em;
    border-radius: 0 !important;
    border: 1px solid #c5a572 !important;
    background: #151c12 !important;
    color: #e8f0d8 !important;
}
.stButton>button:hover { background: #24321c !important; border-color: #7cff6b !important; color: #7cff6b !important; }

[data-testid="stMetricValue"] { font-family: 'Share Tech Mono', monospace; }
hr { border-color: #2f4228 !important; }

.panel-title {
    font-family: 'Share Tech Mono', monospace;
    color: #c5a572; letter-spacing: 0.22em; font-size: 0.78rem;
    margin: 0.3rem 0 0.5rem 0;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# Colores de infección (mapa y leyenda)
COLOR_AI = {
    0: "#3dff7a",  # limpio
    1: "#ffd000",  # silente
    2: "#ff3b3b",  # declarada
    3: "#3ec6ff",  # desinfección
}
SIMBOLO = {"GC": "circle", "GE": "square", "MA": "diamond"}


def _init_state() -> None:
    if "sim" not in st.session_state:
        st.session_state.sim = Simulacion()
    if "costes" not in st.session_state:
        st.session_state.costes = costes_por_defecto()
    if "last_map_sel" not in st.session_state:
        st.session_state.last_map_sel = None
    if "params_ui" not in st.session_state:
        st.session_state.params_ui = valores_por_defecto()


def csv_button(df: pd.DataFrame, nombre: str, key: str) -> None:
    st.download_button(
        label=f"DESCARGAR {nombre}.CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{nombre}.csv",
        mime="text/csv",
        key=key,
        disabled=df is None or df.empty,
        use_container_width=True,
    )


def construir_mapa(
    agentes: pd.DataFrame,
    conexiones: pd.DataFrame,
    hit_dia: pd.DataFrame,
    t: float,
    mostrar_radios: bool,
    mostrar_rutas: bool,
) -> go.Figure:
    """Mapa cuadrado T×T km con granjas, radios y flechas de transporte del día."""
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="rgba(11,15,10,0)",
        plot_bgcolor="#0c120b",
        margin=dict(l=40, r=20, t=20, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(color="#c5d3b4", family="Share Tech Mono"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            range=[0, t],
            autorange=False,
            title="X (km)",
            gridcolor="#243322",
            zeroline=False,
            color="#8aa078",
            showline=True,
            linecolor="#3d5a32",
        ),
        yaxis=dict(
            range=[0, t],
            autorange=False,
            title="Y (km)",
            scaleanchor="x",
            scaleratio=1,
            gridcolor="#243322",
            zeroline=False,
            color="#8aa078",
            showline=True,
            linecolor="#3d5a32",
        ),
        height=620,
        clickmode="event+select",
    )

    if agentes.empty:
        fig.add_annotation(
            text="SIN AGENTES — genere el teatro de operaciones",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color="#8aa078", size=14, family="Share Tech Mono"),
        )
        return fig

    # Radios de seguridad (polígono denso que se ve como un círculo)
    if mostrar_radios:
        theta = np.linspace(0, 2 * math.pi, 72)
        for _, r in agentes.iterrows():
            fig.add_trace(
                go.Scatter(
                    x=float(r["AX"]) + float(r["AR"]) * np.cos(theta),
                    y=float(r["AY"]) + float(r["AR"]) * np.sin(theta),
                    mode="lines",
                    line=dict(color="rgba(197,165,114,0.28)", width=1, dash="dot"),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    # Flechas de transporte del día visto
    if mostrar_rutas and hit_dia is not None and not hit_dia.empty:
        pos = agentes.set_index("AID")[["AX", "AY"]]
        movs = hit_dia[hit_dia["NT"] > 0]
        for _, m in movs.iterrows():
            if int(m["X"]) not in pos.index or int(m["Y"]) not in pos.index:
                continue
            x0, y0 = pos.loc[int(m["X"]), ["AX", "AY"]]
            x1, y1 = pos.loc[int(m["Y"]), ["AX", "AY"]]
            infecto = int(m["IT"]) == 1
            color = "#ff7a18" if infecto else "#3dff7a"
            fig.add_trace(
                go.Scatter(
                    x=[x0, x1],
                    y=[y0, y1],
                    mode="lines",
                    line=dict(color=color, width=2 if infecto else 1),
                    opacity=0.85,
                    hovertemplate=(
                        f"T{int(m['X'])} → T{int(m['Y'])}<br>"
                        f"camiones: {int(m['NT'])}<br>"
                        f"infección transporte: {int(m['IT'])}<extra></extra>"
                    ),
                    showlegend=False,
                )
            )
            fig.add_annotation(
                x=x1,
                y=y1,
                ax=x0,
                ay=y0,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.1,
                arrowwidth=1.4,
                arrowcolor=color,
                opacity=0.9,
            )

    # Agentes, un trazo por tipo para la leyenda de símbolos
    an_max = max(float(agentes["AN"].max()), 1.0)
    for tipo, simbolo in SIMBOLO.items():
        sub = agentes[agentes["AT"] == tipo]
        if sub.empty:
            continue
        colores = [COLOR_AI.get(int(ai), "#999") for ai in sub["AI"]]
        bordes = ["#ffffff" if int(ac) == 1 else "#0b0f0a" for ac in sub["AC"]]
        fig.add_trace(
            go.Scatter(
                x=sub["AX"],
                y=sub["AY"],
                mode="markers+text",
                name=NOMBRE_TIPO[tipo],
                text=[f"{int(a)}" for a in sub["AID"]],
                textposition="top center",
                textfont=dict(color="#c5d3b4", size=10, family="Share Tech Mono"),
                marker=dict(
                    symbol=simbolo,
                    size=14 + 22 * (sub["AN"] / an_max),
                    color=colores,
                    line=dict(width=2.4, color=bordes),
                    opacity=0.95,
                ),
                customdata=list(
                    zip(
                        sub["AID"],
                        sub["AT"],
                        sub["AN"],
                        sub["AI"],
                        sub["AC"],
                        sub["MI"],
                    )
                ),
                hovertemplate=(
                    "<b>AID %{customdata[0]}</b> · %{customdata[1]}<br>"
                    "animales AN=%{customdata[2]}<br>"
                    "infección AI=%{customdata[3]}<br>"
                    "cuarentena AC=%{customdata[4]}<br>"
                    "medio MI=%{customdata[5]:.2f}<br>"
                    "x=%{x:.2f} y=%{y:.2f} km"
                    "<extra></extra>"
                ),
            )
        )
    return fig


def _extraer_click_aid(evento) -> int | None:
    """Lee el AID clicado en el mapa Plotly (Streamlit >= 1.35)."""
    try:
        sel = evento.selection if hasattr(evento, "selection") else evento.get("selection")
        points = sel.get("points") if isinstance(sel, dict) else getattr(sel, "points", None)
        if not points:
            return None
        p0 = points[0]
        cd = p0.get("customdata") if isinstance(p0, dict) else None
        if cd is None and hasattr(p0, "get"):
            cd = p0.get("customdata")
        if cd is not None:
            return int(cd[0])
    except Exception:
        return None
    return None


def _kpis_html(sim: Simulacion, vista: pd.DataFrame) -> str:
    n = 0 if vista.empty else len(vista)
    inf = 0 if vista.empty else int((vista["AI"] != 0).sum())
    cua = 0 if vista.empty else int((vista["AC"] == 1).sum())
    medio = 0.0 if vista.empty else float(vista["MI"].sum())
    if vista.empty:
        estado, cls = "STANDBY", ""
    elif inf == 0 and medio == 0:
        estado, cls = "ESTABLE", "ok"
    elif int((vista["AI"] == 2).sum()) > 0:
        estado, cls = "BROTE DECLARADO", "alert"
    else:
        estado, cls = "VIGILANCIA", "warn"
    return f"""
    <div class="kpi-row">
      <div class="kpi"><div class="lbl">DÍA TÁCTICO</div><div class="val">{sim.view_day:03d} / {sim.day:03d}</div></div>
      <div class="kpi"><div class="lbl">AGENTES N</div><div class="val">{n}</div></div>
      <div class="kpi {'alert' if inf else 'ok'}"><div class="lbl">INFECTADOS</div><div class="val">{inf}</div></div>
      <div class="kpi {'warn' if cua else ''}"><div class="lbl">CUARENTENA</div><div class="val">{cua}</div></div>
      <div class="kpi {cls}"><div class="lbl">ESTADO</div><div class="val">{estado}</div></div>
    </div>
    """


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_init_state()
sim: Simulacion = st.session_state.sim
if st.session_state.pop("pending_slider_reset", False):
    st.session_state["slider_dia"] = 0

st.markdown(
    """
    <div class="tactical-banner">
      <div class="kicker">ONEDEFENSE · SIA-ADO · PROTOCOLO EPIDEMIOLÓGICO</div>
      <h1>Simulación táctica de peste porcina</h1>
      <div class="sub">TEATRO DE OPERACIONES · GRANJAS DE CRÍA / ENGORDE / MATADEROS · CONTAGIO POR TRANSPORTE Y MEDIO</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_dash, tab_agentes, tab_res, tab_analisis = st.tabs(
    ["DASHBOARD", "AGENTES", "RESULTADOS", "ANÁLISIS"]
)


# ============================= DASHBOARD ====================================
with tab_dash:
    c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1.1, 1.1, 2])
    with c1:
        if st.button("▶ INICIAR SIMULACIÓN", use_container_width=True, disabled=sim.agentes.empty):
            if sim.agentes.empty:
                st.warning("Genere agentes primero (pestaña Agentes).")
            elif int((sim.agentes["AI"] != 0).sum()) == 0 and sim.day == 0:
                st.warning("Marque al menos un brote silente (click en el mapa o lista).")
            else:
                sim.running = True
                sim.playing = False
    with c2:
        if st.button("❚❚ PAUSAR", use_container_width=True):
            sim.running = False
            sim.playing = False
    with c3:
        if st.button("▶ REANUDAR", use_container_width=True, disabled=sim.agentes.empty):
            if not sistema_estable(sim.agentes) or sim.day == 0:
                sim.running = True
                sim.playing = False
    with c4:
        if st.button("↺ REINICIAR", use_container_width=True, disabled=sim.agentes.empty):
            sim.resetear_estados(mantener_brote=False)
            st.session_state["pending_slider_reset"] = True
            st.rerun()
    with c5:
        if st.button("▷ PLAY SECUENCIA", use_container_width=True, disabled=sim.day == 0):
            sim.playing = True
            sim.running = False
            sim.view_day = 0

    vista = agentes_en_dia(sim.agentes, sim.has, sim.view_day) if not sim.agentes.empty else sim.agentes
    st.markdown(_kpis_html(sim, vista), unsafe_allow_html=True)

    col_map, col_side = st.columns([3.2, 1.15])
    with col_side:
        st.markdown('<div class="panel-title">FOCO INICIAL · DÍA 0</div>', unsafe_allow_html=True)
        if sim.agentes.empty:
            st.info("Vaya a **Agentes**, fije parámetros y pulse GENERAR.")
        else:
            opciones = [
                f"{int(r.AID)} · {r.AT} · {NOMBRE_TIPO[r.AT]}"
                for r in sim.agentes.itertuples()
            ]
            ya = [
                f"{int(r.AID)} · {r.AT} · {NOMBRE_TIPO[r.AT]}"
                for r in sim.agentes.itertuples()
                if int(r.AI) == 1 and sim.day == 0
            ]
            # Si ya se simuló, el multiselect refleja el brote del día 0 histórico
            if sim.day > 0 and not sim.has.empty:
                d0 = sim.has[sim.has["dia"] == 0]
                ya = [
                    f"{int(r.AID)} · {sim.agentes.set_index('AID').loc[int(r.AID), 'AT']} · {NOMBRE_TIPO[sim.agentes.set_index('AID').loc[int(r.AID), 'AT']]}"
                    for r in d0.itertuples()
                    if int(r.AI) == 1
                ]
            sel = st.multiselect(
                "Seleccione granjas del brote (AI=1 silente)",
                options=opciones,
                default=ya,
                disabled=sim.day != 0,
                help="Solo se puede sembrar el brote en el día 0, antes de iniciar la simulación.",
            )
            if sim.day == 0:
                aids = [int(s.split("·")[0].strip()) for s in sel]
                actuales = set(sim.agentes.loc[sim.agentes["AI"] == 1, "AID"].astype(int))
                if set(aids) != actuales:
                    sim.marcar_brote(aids)
                    st.rerun()

            st.markdown('<div class="panel-title">CAPAS DEL MAPA</div>', unsafe_allow_html=True)
            mostrar_radios = st.checkbox("Radios de seguridad AR", value=False)
            mostrar_rutas = st.checkbox("Flechas de transporte del día", value=True)
            st.caption("Click en un símbolo del mapa (día 0) para marcar/desmarcar brote silente. El borde blanco indica cuarentena.")

    with col_map:
        hit_dia = (
            sim.hit[sim.hit["dia"] == sim.view_day]
            if (not sim.hit.empty and sim.view_day > 0)
            else pd.DataFrame()
        )
        fig = construir_mapa(
            vista,
            sim.conexiones,
            hit_dia,
            float(sim.params.get("T", 10)),
            mostrar_radios=mostrar_radios if not sim.agentes.empty else False,
            mostrar_rutas=mostrar_rutas if not sim.agentes.empty else False,
        )
        try:
            evento = st.plotly_chart(
                fig,
                use_container_width=True,
                on_select="rerun",
                selection_mode="points",
                key="mapa_tactico",
            )
        except TypeError:
            st.plotly_chart(fig, use_container_width=True, key="mapa_tactico")
            evento = None
        aid_click = _extraer_click_aid(evento) if evento is not None else None
        if aid_click is not None and sim.day == 0:
            firma = (aid_click, str(getattr(evento, "selection", evento)))
            if st.session_state.last_map_sel != firma:
                st.session_state.last_map_sel = firma
                sim.toggle_brote(aid_click)
                st.rerun()

        st.markdown(
            """
            <div class="legend-bar">
              <span><span class="dot" style="background:#3dff7a;border-radius:50%"></span>AI=0 Limpio</span>
              <span><span class="dot" style="background:#ffd000;border-radius:50%"></span>AI=1 Silente</span>
              <span><span class="dot" style="background:#ff3b3b;border-radius:50%"></span>AI=2 Declarada</span>
              <span><span class="dot" style="background:#3ec6ff;border-radius:50%"></span>AI=3 Desinfección</span>
              <span><span class="dot" style="background:transparent;border:2px solid #fff;border-radius:50%"></span>Cuarentena AC=1</span>
              <span><span class="dot" style="background:#c5d3b4;border-radius:50%"></span>GC cría</span>
              <span><span class="sq" style="background:#c5d3b4"></span>GE engorde</span>
              <span><span class="dm" style="background:#c5d3b4"></span>MA matadero</span>
              <span style="color:#3dff7a">→ transporte limpio</span>
              <span style="color:#ff7a18">→ transporte que infectó</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    max_d = max(int(sim.day), 0)
    if sim.running or sim.playing:
        st.session_state["slider_dia"] = int(sim.view_day)
    elif "slider_dia" not in st.session_state:
        st.session_state["slider_dia"] = int(sim.view_day)
    # Streamlit no permite min_value == max_value; con día 0 usamos rango 0–1 desactivado.
    if st.session_state.get("slider_dia", 0) > max_d:
        st.session_state["slider_dia"] = max_d
    view = st.slider(
        "Retroceder al día",
        min_value=0,
        max_value=max(max_d, 1),
        key="slider_dia",
        disabled=max_d == 0,
        help="Mueve el mapa a cualquier día ya simulado. No recalcula: lee HAS/HIT.",
    )
    view = 0 if max_d == 0 else min(int(view), max_d)
    if (not sim.running) and (not sim.playing) and int(view) != sim.view_day:
        sim.view_day = int(view)
        st.rerun()

    if sim.running:
        st.caption("Simulando día a día… PAUSAR detiene el avance. El sistema para solo cuando AI=0 y MI=0 en todos los agentes.")
        fin = sim.paso()
        time.sleep(0.12)
        if fin:
            if sistema_estable(sim.agentes):
                st.success(f"Sistema estabilizado en el día {sim.day} (todos los AI=0 y MI=0).")
            else:
                st.warning(
                    f"Se alcanzó el tope de {int(sim.params.get('max_dias', 365))} días "
                    "sin extinguir el brote. Sube el tope en Agentes o baja PM en la tabla "
                    "de conexiones / PIME si quieres que se apague."
                )
        st.rerun()

    if sim.playing:
        if sim.view_day < sim.day:
            sim.view_day += 1
            time.sleep(0.35)
            st.rerun()
        else:
            sim.playing = False


# ============================== AGENTES =====================================
with tab_agentes:
    st.markdown('<div class="panel-title">PARÁMETROS A GENERAR</div>', unsafe_allow_html=True)
    p1, p2, p3, p4, p5 = st.columns(5)
    params = dict(st.session_state.params_ui)
    with p1:
        params["T"] = st.number_input(
            "Territorio km (T)",
            min_value=2.0,
            max_value=100.0,
            value=float(params["T"]),
            step=1.0,
            help="Lado del cuadrado donde se colocan las granjas, en kilómetros. Por defecto T=10.",
        )
    with p2:
        params["Nc"] = st.number_input(
            "Granjas de cría (Nc)",
            min_value=0,
            max_value=80,
            value=int(params["Nc"]),
            help="Número de granjas de cría (GC) a generar aleatoriamente.",
        )
    with p3:
        params["Ne"] = st.number_input(
            "Granjas de engorde (Ne)",
            min_value=0,
            max_value=80,
            value=int(params["Ne"]),
            help="Número de granjas de engorde (GE) a generar aleatoriamente.",
        )
    with p4:
        params["Nm"] = st.number_input(
            "Mataderos (Nm)",
            min_value=0,
            max_value=40,
            value=int(params["Nm"]),
            help="Número de mataderos (MA) a generar aleatoriamente.",
        )
    with p5:
        params["semilla"] = st.number_input(
            "Semilla RNG",
            min_value=0,
            max_value=999999,
            value=int(params["semilla"]),
            help="Semilla del generador aleatorio. Misma semilla + mismos parámetros = mismo mapa.",
        )

    st.markdown('<div class="panel-title">VALORES POR DEFECTO DEL AGENTE</div>', unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        params["AR"] = st.number_input("Radio seguridad km (AR)", 0.1, 50.0, float(params["AR"]), 0.5,
                                       help="Radio de seguridad alrededor del agente. Si D(A,B) ≤ AR(A), entonces V(A,B)=1 y B entra en la lógica de cuarentena de A.")
        params["DI1"] = st.number_input("Días silente→declarada (DI1)", 1, 60, int(params["DI1"]),
                                        help="Días que un agente permanece en infección silente (AI=1) antes de que el brote se declare (AI=2).")
    with d2:
        params["PIMS"] = st.number_input("P. infectar medio (PIMS)", 0.0, 1.0, float(params["PIMS"]), 0.05,
                                         help="Probabilidad diaria de que un agente en infección silente contamine su medio natural.")
        params["DI2"] = st.number_input("Días declarada→desinfección (DI2)", 1, 60, int(params["DI2"]),
                                        help="Días desde que se declara la infección (AI=2) hasta que empieza la desinfección (AI=3).")
    with d3:
        params["PIME"] = st.number_input("P. infectarse del medio (PIME)", 0.0, 1.0, float(params["PIME"]), 0.05,
                                         help="PIME(Y): probabilidad de que el agente Y se infecte a partir de SU medio. En cada día se combinan los 3 días anteriores: PIM(M,Y)=1-(1-PIME·MI_{d-1})(1-PIME·MI_{d-2})(1-PIME·MI_{d-3}).")
        params["DI3"] = st.number_input("Días desinfección→limpio (DI3)", 1, 90, int(params["DI3"]),
                                        help="Días de desinfección (AI=3) hasta eliminar la infección (AI=0).")
    with d4:
        params["PITS"] = st.number_input("P. infectar transporte (PITS)", 0.0, 1.0, float(params["PITS"]), 0.05,
                                         help="Probabilidad de que un agente infectado contamine un camión al cargar.")
        params["PITE"] = st.number_input("P. infectarse del transporte (PITE)", 0.0, 1.0, float(params["PITE"]), 0.05,
                                         help="Probabilidad de que un agente se infecte al descargar un camión contaminado.")

    e1, e2 = st.columns(2)
    with e1:
        params["PM"] = st.number_input(
            "P. medio→medio a 1 km (PM)",
            0.0, 1.0, float(params["PM"]), 0.05,
            help="Valor inicial de PM(A,B) en cada conexión: probabilidad de que el medio de A infecte el de B en un día si están a 1 km. Por defecto 0.05. Luego se atenúa con la distancia D. Se puede editar par a par en la tabla de conexiones.",
        )
    with e2:
        params["max_dias"] = st.number_input(
            "Tope de días de simulación",
            10, 2000, int(params["max_dias"]),
            help="Freno de seguridad. La simulación también para antes si todos los AI y MI vuelven a 0.",
        )

    st.session_state.params_ui = params
    if not sim.agentes.empty:
        sim.params["max_dias"] = int(params["max_dias"])
    st.caption(f"N = Nc + Ne + Nm = {int(params['Nc']) + int(params['Ne']) + int(params['Nm'])} agentes.")

    if st.button("GENERAR AGENTES ALEATORIOS", type="primary"):
        try:
            sim.generar(params)
            st.session_state["pending_slider_reset"] = True
            st.success(f"Generados {len(sim.agentes)} agentes en un teatro de {params['T']} km.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.markdown('<div class="panel-title">TABLA DE AGENTES</div>', unsafe_allow_html=True)
    st.caption("AID, AT, AX, AY, AN, AI, AC y MI no se editan a mano. AR, PIMS, PIME, PITS, PITE, DI1–DI3 sí.")
    if sim.agentes.empty:
        st.info("Aún no hay agentes.")
    else:
        colcfg = {
            "AID": st.column_config.NumberColumn("AID", disabled=True),
            "AT": st.column_config.TextColumn("AT (tipo)", disabled=True),
            "AX": st.column_config.NumberColumn("AX km", format="%.3f", disabled=True),
            "AY": st.column_config.NumberColumn("AY km", format="%.3f", disabled=True),
            "AN": st.column_config.NumberColumn("AN tamaño", disabled=True),
            "AI": st.column_config.NumberColumn("AI infección", disabled=True),
            "AC": st.column_config.NumberColumn("AC cuarentena", disabled=True),
            "MI": st.column_config.NumberColumn("MI medio", format="%.3f", disabled=True),
            "AR": st.column_config.NumberColumn("AR radio km", min_value=0.1, max_value=50.0, step=0.1),
            "PIMS": st.column_config.NumberColumn("PIMS", min_value=0.0, max_value=1.0, step=0.05),
            "PIME": st.column_config.NumberColumn("PIME", min_value=0.0, max_value=1.0, step=0.05),
            "PITS": st.column_config.NumberColumn("PITS", min_value=0.0, max_value=1.0, step=0.05),
            "PITE": st.column_config.NumberColumn("PITE", min_value=0.0, max_value=1.0, step=0.05),
            "DI1": st.column_config.NumberColumn("DI1", min_value=1, max_value=90, step=1),
            "DI2": st.column_config.NumberColumn("DI2", min_value=1, max_value=90, step=1),
            "DI3": st.column_config.NumberColumn("DI3", min_value=1, max_value=180, step=1),
        }
        edit_ag = st.data_editor(
            sim.agentes,
            column_config=colcfg,
            disabled=["AID", "AT", "AX", "AY", "AN", "AI", "AC", "MI"],
            hide_index=True,
            use_container_width=True,
            key=f"editor_agentes_{sim.gen_id}",
        )
        cols_edit = ["AR", "PIMS", "PIME", "PITS", "PITE", "DI1", "DI2", "DI3"]
        if not np.allclose(
            edit_ag[cols_edit].to_numpy(dtype=float),
            sim.agentes[cols_edit].to_numpy(dtype=float),
            equal_nan=True,
        ):
            sim.aplicar_edicion_agentes(edit_ag)
        csv_button(sim.agentes, "agentes", "dl_agentes")

    st.markdown('<div class="panel-title">CONEXIONES ENTRE AGENTES</div>', unsafe_allow_html=True)
    st.caption("D distancia km, V=1 si B está en el radio de A, M transportes esperados/día y PM contagio medio→medio a 1 km (ambos editables). Rutas típicas: GC→GE y GE→MA.")
    if sim.conexiones.empty:
        st.info("Las conexiones aparecen al generar agentes.")
    else:
        if "PM" not in sim.conexiones.columns:
            sim.conexiones = sim.conexiones.copy()
            sim.conexiones["PM"] = 0.05
        edit_cn = st.data_editor(
            sim.conexiones,
            column_config={
                "IDA": st.column_config.NumberColumn("IDA", disabled=True),
                "IDB": st.column_config.NumberColumn("IDB", disabled=True),
                "D": st.column_config.NumberColumn("D km", format="%.3f", disabled=True),
                "V": st.column_config.NumberColumn("V vigilancia", disabled=True),
                "M": st.column_config.NumberColumn("M transportes/día", min_value=0.0, step=0.01),
                "PM": st.column_config.NumberColumn("PM medio→medio", min_value=0.0, max_value=1.0, step=0.01, format="%.3f"),
            },
            disabled=["IDA", "IDB", "D", "V"],
            hide_index=True,
            use_container_width=True,
            key=f"editor_conexiones_{sim.gen_id}",
        )
        cols_cn = [c for c in ["M", "PM"] if c in edit_cn.columns and c in sim.conexiones.columns]
        if cols_cn and not np.allclose(
            edit_cn[cols_cn].to_numpy(dtype=float),
            sim.conexiones[cols_cn].to_numpy(dtype=float),
            equal_nan=True,
        ):
            sim.aplicar_edicion_conexiones(edit_cn)
        csv_button(sim.conexiones, "conexiones", "dl_conexiones")


# ============================= RESULTADOS ===================================
with tab_res:
    st.markdown('<div class="panel-title">TABLAS HISTÓRICAS DE LA SIMULACIÓN</div>', unsafe_allow_html=True)
    st.caption("HAS = estado diario de cada agente. HIT = transportes e infecciones entre pares. HIM = infecciones agente↔medio.")

    c_a, c_b, c_c = st.columns(3)
    with c_a:
        st.subheader("HAS — estados")
        st.dataframe(sim.has, hide_index=True, use_container_width=True, height=420)
        csv_button(sim.has, "HAS", "dl_has")
    with c_b:
        st.subheader("HIT — transportes")
        st.dataframe(sim.hit, hide_index=True, use_container_width=True, height=420)
        csv_button(sim.hit, "HIT", "dl_hit")
    with c_c:
        st.subheader("HIM — medio")
        st.dataframe(sim.him, hide_index=True, use_container_width=True, height=420)
        csv_button(sim.him, "HIM", "dl_him")


# ============================== ANÁLISIS ====================================
with tab_analisis:
    st.markdown('<div class="panel-title">SERIES TEMPORALES DE ESTADOS</div>', unsafe_allow_html=True)
    ser = series_estados(sim.has, sim.agentes)
    if ser.empty:
        st.info("No hay histórico todavía. Genere agentes, siembre un brote e inicie la simulación.")
    else:
        fig_n = go.Figure()
        paleta = {
            "n_silente": ("Silente", COLOR_AI[1]),
            "n_declarada": ("Declarada", COLOR_AI[2]),
            "n_desinfeccion": ("Desinfección", COLOR_AI[3]),
            "n_cuarentena": ("Cuarentena", "#ffffff"),
        }
        for col, (nombre, color) in paleta.items():
            fig_n.add_trace(go.Scatter(x=ser["dia"], y=ser[col], name=nombre, mode="lines+markers",
                                       line=dict(color=color, width=2)))
        fig_n.update_layout(
            title="Número de granjas / mataderos por estado",
            xaxis_title="Día",
            yaxis_title="Nº de agentes",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0c120b",
            font=dict(color="#d7e3c6"),
            legend=dict(orientation="h"),
            height=380,
            xaxis=dict(gridcolor="#243322"),
            yaxis=dict(gridcolor="#243322"),
        )
        st.plotly_chart(fig_n, use_container_width=True)

        fig_a = go.Figure()
        paleta_a = {
            "anim_silente": ("Silente", COLOR_AI[1]),
            "anim_declarada": ("Declarada", COLOR_AI[2]),
            "anim_desinfeccion": ("Desinfección", COLOR_AI[3]),
            "anim_cuarentena": ("Cuarentena", "#ffffff"),
        }
        for col, (nombre, color) in paleta_a.items():
            fig_a.add_trace(go.Scatter(x=ser["dia"], y=ser[col], name=nombre, mode="lines+markers",
                                       line=dict(color=color, width=2)))
        fig_a.update_layout(
            title="Número de animales por estado",
            xaxis_title="Día",
            yaxis_title="Nº de animales",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0c120b",
            font=dict(color="#d7e3c6"),
            legend=dict(orientation="h"),
            height=380,
            xaxis=dict(gridcolor="#243322"),
            yaxis=dict(gridcolor="#243322"),
        )
        st.plotly_chart(fig_a, use_container_width=True)

    st.markdown('<div class="panel-title">CÁLCULO DE COSTES</div>', unsafe_allow_html=True)
    st.caption("Ocho estimaciones en €. Se aplican cada día según cuarentena (AC=1) y desinfección (AI=3).")
    costes = dict(st.session_state.costes)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        costes["CFCG"] = st.number_input("CFCG fijo cuarentena granja €/día", 0.0, 1e7, float(costes["CFCG"]), 10.0,
                                         help="Coste fijo por cada día que una granja (GC o GE) está en cuarentena.")
        costes["CACG"] = st.number_input("CACG animal en cuarentena granja €", 0.0, 1e6, float(costes["CACG"]), 0.5,
                                         help="Coste por cada animal que pasa un día en cuarentena en granja.")
    with k2:
        costes["CFCM"] = st.number_input("CFCM fijo cuarentena matadero €/día", 0.0, 1e7, float(costes["CFCM"]), 10.0,
                                         help="Coste fijo por cada día de cuarentena en un matadero.")
        costes["CACM"] = st.number_input("CACM animal no sacrificado €", 0.0, 1e6, float(costes["CACM"]), 1.0,
                                         help="Coste por cada animal que un matadero deja de procesar ese día por cuarentena.")
    with k3:
        costes["CFLG"] = st.number_input("CFLG fijo limpieza granja €/día", 0.0, 1e7, float(costes["CFLG"]), 10.0,
                                         help="Coste fijo por día de desinfección en granja (AI=3).")
        costes["CALG"] = st.number_input("CALG animal eliminado en granja €", 0.0, 1e6, float(costes["CALG"]), 0.5,
                                         help="Coste por cada animal eliminado/limpiado en granja durante la desinfección.")
    with k4:
        costes["CFLM"] = st.number_input("CFLM fijo limpieza matadero €/día", 0.0, 1e7, float(costes["CFLM"]), 10.0,
                                         help="Coste fijo por día de desinfección en matadero.")
        costes["CALM"] = st.number_input("CALM animal limpiado en matadero €", 0.0, 1e6, float(costes["CALM"]), 0.5,
                                         help="Coste por cada animal limpiado en matadero durante la desinfección.")
    st.session_state.costes = costes

    sco = series_costes(sim.has, sim.agentes, costes)
    if sco.empty:
        st.info("Los costes aparecerán cuando exista un histórico HAS.")
    else:
        fig_c = go.Figure()
        series_c = [
            ("c_c_granja", "Cuarentena granjas", "#ffd000"),
            ("c_c_mata", "Cuarentena mataderos", "#ff7a18"),
            ("c_l_granja", "Limpieza granjas", "#3ec6ff"),
            ("c_l_mata", "Limpieza mataderos", "#7cff6b"),
        ]
        for col, nombre, color in series_c:
            fig_c.add_trace(go.Scatter(x=sco["dia"], y=sco[col], name=nombre, mode="lines+markers",
                                       line=dict(color=color, width=2)))
        fig_c.update_layout(
            title="Costes diarios (€)",
            xaxis_title="Día",
            yaxis_title="€ / día",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0c120b",
            font=dict(color="#d7e3c6"),
            legend=dict(orientation="h"),
            height=400,
            xaxis=dict(gridcolor="#243322"),
            yaxis=dict(gridcolor="#243322"),
        )
        st.plotly_chart(fig_c, use_container_width=True)
        total = float(sco["c_total"].sum())
        st.metric("Coste acumulado del brote", f"{total:,.0f} €")
        csv_button(sco, "costes_diarios", "dl_costes")
