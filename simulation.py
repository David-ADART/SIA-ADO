"""
Motor de simulación basada en agentes para peste porcina.

Este módulo NO dibuja nada: solo genera granjas/mataderos, calcula
conexiones y avanza el sistema día a día. La aplicación Streamlit
(app.py) se limita a mostrar y controlar este modelo.

Notación (tal como aparece en instrucciones.md):
    GC  granja de cría
    GE  granja de engorde
    MA  matadero
    AI  estado de infección del agente (0 limpio, 1 silente, 2 declarada, 3 desinfección)
    AC  cuarentena (0 no, 1 sí)
    MI  grado de infección del medio natural alrededor del agente [0, 1]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------

TIPOS_AGENTE = ("GC", "GE", "MA")

# Etiquetas para la interfaz y las leyendas
NOMBRE_TIPO = {
    "GC": "Granja de cría",
    "GE": "Granja de engorde",
    "MA": "Matadero",
}

NOMBRE_INFECCION = {
    0: "Limpio",
    1: "Silente",
    2: "Declarada",
    3: "Desinfección",
}

# Columnas fijas de las tres tablas históricas
HAS_COLS = ["dia", "AID", "AC", "AI", "MI"]
HIT_COLS = ["dia", "X", "Y", "NT", "IT", "IM"]
HIM_COLS = ["dia", "Y", "IMY", "IYM"]


def valores_por_defecto() -> dict:
    """Parámetros iniciales del prototipo (sección 7 de las instrucciones)."""
    return {
        "T": 60.0,       # lado del mapa, en km (por defecto T = 60)
        "Nc": 8,         # granjas de cría
        "Ne": 12,        # granjas de engorde
        "Nm": 3,         # mataderos
        "AR": 5.0,       # radio de seguridad (km)
        "PIMS": 0.2,     # P(agente infectado → contamina el medio)
        "PIME": 0.2,     # P(medio infectado → contamina el agente)
        "PITS": 0.9,     # P(agente infectado → contamina el transporte)
        "PITE": 0.9,     # P(transporte infectado → contamina el agente)
        "DI1": 3,        # días en silente hasta declararse
        "DI2": 4,        # días en declarada hasta desinfección
        "DI3": 15,       # días en desinfección hasta quedar limpio
        # PM(A,B): probabilidad de que el medio de A infecte el de B
        # a 1 km de distancia. Por defecto 0.05 en TODAS las conexiones.
        "PM": 0.05,
        "semilla": 42,
        "max_dias": 365,
    }


def costes_por_defecto() -> dict:
    """Costes diarios usados en la pestaña Análisis."""
    return {
        "CFCG": 200.0,   # fijo / día de cuarentena en granja
        "CACG": 4.0,     # por animal / día en cuarentena (granja)
        "CFCM": 300.0,   # fijo / día de cuarentena en matadero
        "CACM": 400.0,   # por animal no sacrificado / día
        "CFLG": 1000.0,  # fijo / día de limpieza en granja
        "CALG": 10.0,    # por animal eliminado en granja
        "CFLM": 600.0,   # fijo / día de limpieza en matadero
        "CALM": 15.0,    # por animal limpiado en matadero
    }


def _clip01(p: float) -> float:
    """Una probabilidad tiene que vivir en [0, 1]."""
    return float(np.clip(p, 0.0, 1.0))


def _bernoulli(rng: np.random.Generator, p: float) -> int:
    """Ensayo de Bernoulli. Devuelve 0 o 1."""
    return int(rng.random() < _clip01(p))


def _empty_has() -> pd.DataFrame:
    return pd.DataFrame(columns=HAS_COLS)


def _empty_hit() -> pd.DataFrame:
    return pd.DataFrame(columns=HIT_COLS)


def _empty_him() -> pd.DataFrame:
    return pd.DataFrame(columns=HIM_COLS)


def _posiciones_aleatorias(
    n: int,
    t: float,
    rng: np.random.Generator,
    min_dist: float = 1.0,
) -> np.ndarray:
    """
    Coloca n puntos en el cuadrado [0, T] x [0, T].

    La distancia euclídea entre dos agentes no puede ser menor de 1 km
    (sección 6). Si el cuadrado es demasiado pequeño para N puntos,
    se lanza un error para que el usuario suba T o baje N.
    """
    if n <= 0:
        return np.zeros((0, 2))
    if n == 1:
        return rng.uniform(0.0, t, size=(1, 2))

    max_intentos_punto = 500
    max_reinicios = 25
    for _reinicio in range(max_reinicios):
        puntos: list[np.ndarray] = []
        ok = True
        for _ in range(n):
            elegido = None
            for _intento in range(max_intentos_punto):
                cand = rng.uniform(0.0, t, size=2)
                if all(np.hypot(*(cand - p)) >= min_dist - 1e-9 for p in puntos):
                    elegido = cand
                    break
            if elegido is None:
                ok = False
                break
            puntos.append(elegido)
        if ok:
            return np.vstack(puntos)

    raise ValueError(
        f"No se pueden colocar {n} agentes en un cuadrado de {t:g}×{t:g} km "
        f"con distancia mínima {min_dist:g} km. Sube T o baja Nc+Ne+Nm."
    )


def generar_agentes(params: dict, rng: Optional[np.random.Generator] = None) -> pd.DataFrame:
    """
    Crea la tabla de agentes (sección 6).

    Variables fijas del agente: AID, AT, AX, AY, AN, AR, PIMS, PIME,
    PITS, PITE, DI1, DI2, DI3.
    Variables que cambian cada día: AI, AC, MI (todas empiezan a 0).
    Las posiciones respetan una distancia mínima de 1 km entre agentes.
    """
    rng = rng or np.random.default_rng(params.get("semilla"))
    nc, ne, nm = int(params["Nc"]), int(params["Ne"]), int(params["Nm"])
    t = float(params["T"])
    n = nc + ne + nm
    if n <= 0:
        raise ValueError("Hace falta al menos un agente (Nc + Ne + Nm > 0).")

    xy = _posiciones_aleatorias(n, t, rng)
    tipos = ["GC"] * nc + ["GE"] * ne + ["MA"] * nm

    filas = []
    for i in range(n):
        filas.append(
            {
                "AID": i + 1,
                "AT": tipos[i],
                "AX": round(float(xy[i, 0]), 3),
                "AY": round(float(xy[i, 1]), 3),
                # Tamaño: cabezas en granja, o cabezas/día que procesa un matadero
                "AN": int(rng.integers(500, 2001)),
                "AI": 0,
                "AC": 0,
                "MI": 0.0,
                "AR": float(params["AR"]),
                "PIMS": float(params["PIMS"]),
                "PIME": float(params["PIME"]),
                "PITS": float(params["PITS"]),
                "PITE": float(params["PITE"]),
                "DI1": int(params["DI1"]),
                "DI2": int(params["DI2"]),
                "DI3": int(params["DI3"]),
            }
        )
    return pd.DataFrame(filas)


def generar_conexiones(
    agentes: pd.DataFrame,
    rng: Optional[np.random.Generator] = None,
    pm_default: float = 0.05,
) -> pd.DataFrame:
    """
    Tabla de conexiones dirigida A → B (N×(N-1) filas).

    Columnas:
        IDA, IDB  identificadores
        D         distancia euclídea en km
        V         1 si B está dentro del radio de seguridad de A (D <= AR(A))
        M         transportes esperados al día de A hacia B
        PM        P(medio A infecta medio B en un día, a 1 km). Por defecto 0.05.

    Reglas de M (sección 3):
        GC → GE : Bernoulli(0.3) * AN(A) / 2500
        GE → MA : Bernoulli(0.3) * AN(A) / 2500
        resto   : 0
    """
    rng = rng or np.random.default_rng()
    agentes = agentes.set_index("AID", drop=False)
    filas = []
    for ida, a in agentes.iterrows():
        for idb, b in agentes.iterrows():
            if ida == idb:
                continue
            dx = float(a["AX"] - b["AX"])
            dy = float(a["AY"] - b["AY"])
            dist = float(np.hypot(dx, dy))
            v = 1 if dist <= float(a["AR"]) else 0

            if a["AT"] == "GC" and b["AT"] == "GE":
                m = (_bernoulli(rng, 0.3) * float(a["AN"]) / 2500.0)
            elif a["AT"] == "GE" and b["AT"] == "MA":
                m = (_bernoulli(rng, 0.3) * float(a["AN"]) / 2500.0)
            else:
                m = 0.0

            filas.append(
                {
                    "IDA": int(ida),
                    "IDB": int(idb),
                    "D": round(dist, 4),
                    "V": int(v),
                    "M": round(float(m), 4),
                    "PM": float(pm_default),
                }
            )
    return pd.DataFrame(filas)


def actualizar_vigilancia(agentes: pd.DataFrame, conexiones: pd.DataFrame) -> pd.DataFrame:
    """Recalcula V cuando el usuario cambia el radio AR de algún agente."""
    ar = agentes.set_index("AID")["AR"].to_dict()
    out = conexiones.copy()
    out["V"] = [
        1 if float(row["D"]) <= float(ar.get(int(row["IDA"]), 0.0)) else 0
        for _, row in out.iterrows()
    ]
    return out


def _indice_has(has: pd.DataFrame) -> tuple[dict, dict]:
    """
    Diccionarios (dia, aid) → MI y (dia, aid) → AI.
    Evita filtrar el DataFrame HAS miles de veces por día.
    """
    mi: dict[tuple[int, int], float] = {}
    ai: dict[tuple[int, int], int] = {}
    if has.empty:
        return mi, ai
    for r in has.itertuples(index=False):
        clave = (int(r.dia), int(r.AID))
        mi[clave] = float(r.MI)
        ai[clave] = int(r.AI)
    return mi, ai


def _mi_en_dia(mi_idx: dict, aid: int, dia: int) -> float:
    """Lee MI histórico. Días negativos (antes del inicio) valen 0."""
    if dia < 0:
        return 0.0
    return float(mi_idx.get((int(dia), int(aid)), 0.0))


def _dias_en_estado(ai_idx: dict, aid: int, ai_prev: int, dia_prev: int) -> int:
    """
    Cuántos días consecutivos (incluyendo dia_prev) lleva el agente
    con el mismo AI. Sirve para aplicar DI1, DI2 y DI3.
    """
    if dia_prev < 0:
        return 0
    cuenta = 0
    for d in range(dia_prev, -1, -1):
        if ai_idx.get((d, int(aid))) != int(ai_prev):
            break
        cuenta += 1
    return cuenta


def _prob_desde_lags(pm: float, mis: list[float], distancia: Optional[float] = None) -> float:
    """
    Probabilidad de que "al menos uno" de los 3 días anteriores
    propague infección:

        1 - Π_k (1 - pm * MI_{d-k} [/ D])

    Dos usos (sección 4 de instrucciones.md):
      - Medio de Y → agente Y: pm = PIME(Y), sin dividir por distancia.
        PIM(M,Y) = 1 - Π (1 - PIME(Y)·MI(Y)_{d-k}), k=1,2,3
      - Medio de X → medio de Y: pm = PM(X,Y), dividido por max(1, D).
        PIM(X,Y) = 1 - Π (1 - PM(X,Y)·MI(X)_{d-k} / max(1, D(X,Y)))

    Recortamos cada término a [0, 1] para no romper Bernoulli.
    """
    sobrevive = 1.0
    for mi in mis:
        term = pm * float(mi)
        if distancia is not None:
            # Fórmula: PM·MI / max(1, D). Así D<1 km no infla la probabilidad.
            term = term / max(1.0, float(distancia))
        sobrevive *= 1.0 - _clip01(term)
    return _clip01(1.0 - sobrevive)


def simular_un_dia(
    agentes: pd.DataFrame,
    conexiones: pd.DataFrame,
    has: pd.DataFrame,
    hit: pd.DataFrame,
    him: pd.DataFrame,
    dia_anterior: int,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Avanza el sistema un día (sección 4).

    Orden, tal como está escrito en las instrucciones:
        1) cuarentena a partir de AI del día anterior
        2) infección de cada agente
        3) infección del medio natural

    Devuelve (agentes_actualizados, has, hit, him).
    """
    d = dia_anterior + 1
    prev = agentes.set_index("AID", drop=False)
    nuevo = prev.copy()
    ids = [int(i) for i in prev.index]

    # Índices rápidos: no filtramos DataFrames dentro de los bucles
    mi_idx, ai_idx = _indice_has(has)
    dist = {(int(r.IDA), int(r.IDB)): float(r.D) for r in conexiones.itertuples(index=False)}
    m_ab = {(int(r.IDA), int(r.IDB)): float(r.M) for r in conexiones.itertuples(index=False)}
    # PM(X,Y): probabilidad de contagio medio→medio a 1 km (luego se divide por D)
    tiene_pm = "PM" in conexiones.columns
    pm_ab = {
        (int(r.IDA), int(r.IDB)): float(r.PM) if tiene_pm else 0.05
        for r in conexiones.itertuples(index=False)
    }
    en_radio: dict[int, set[int]] = {i: set() for i in ids}
    hacia: dict[int, list[int]] = {i: [] for i in ids}  # orígenes X con M>0 hacia Y
    for r in conexiones.itertuples(index=False):
        ida, idb = int(r.IDA), int(r.IDB)
        if int(r.V) == 1:
            en_radio.setdefault(ida, set()).add(idb)
        if float(r.M) > 0:
            hacia.setdefault(idb, []).append(ida)

    hit_rows: list[dict] = []
    him_rows: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Cuarentena
    #    Y entra en cuarentena si AYER él o alguien dentro de su radio
    #    tenía infección declarada (2) o estaba en desinfección (3).
    #    Sale de cuarentena si todos esos agentes estaban limpios o en
    #    silente (0 o 1). Las dos reglas se resumen en una sola.
    # ------------------------------------------------------------------
    for aid, row in prev.iterrows():
        ids_a_mirar = {int(aid)} | set(en_radio.get(int(aid), set()))
        hay_alerta = any(int(prev.loc[x, "AI"]) in (2, 3) for x in ids_a_mirar if x in prev.index)
        nuevo.at[aid, "AC"] = 1 if hay_alerta else 0

    # ------------------------------------------------------------------
    # 2. Estado de infección del agente
    # ------------------------------------------------------------------
    it_hacia: dict[int, list[int]] = {int(a): [] for a in prev.index}
    im_agente: dict[int, int] = {}

    for aid, row in prev.iterrows():
        ai_prev = int(row["AI"])
        dias_estado = _dias_en_estado(ai_idx, int(aid), ai_prev, dia_anterior)
        ai_nuevo = ai_prev
        imy = 0  # infección medio → agente hoy

        if ai_prev == 3 and dias_estado >= int(row["DI3"]):
            # Lleva DI3 días desinfectando → queda limpio
            ai_nuevo = 0
        elif ai_prev == 2 and dias_estado >= int(row["DI2"]):
            # Lleva DI2 días en infección declarada → empieza desinfección
            ai_nuevo = 3
        elif ai_prev == 1 and dias_estado >= int(row["DI1"]):
            # Lleva DI1 días en silente → se declara el brote
            ai_nuevo = 2
        elif ai_prev == 0:
            # Solo un agente limpio puede contagiarse de nuevo.
            # --- 2.a Infección por transporte procedente de cada X ---
            origenes = hacia.get(int(aid), [])
            for x in origenes:
                if x not in prev.index:
                    continue
                # Un origen en cuarentena no mueve animales
                if int(prev.loc[x, "AC"]) != 0:
                    nt = 0
                    it = 0
                else:
                    lam = float(m_ab.get((x, int(aid)), 0.0))
                    nt = int(rng.poisson(lam)) if lam > 0 else 0
                    # PIT1(X,Y)_d = (AI(X)≠0) * PITS(X) * PITE(Y)
                    # PIT(X,Y)_d  = 1 - (1-PIT1)^T(X,Y)
                    x_infectado = int(prev.loc[x, "AI"] != 0)
                    pit1 = x_infectado * float(prev.loc[x, "PITS"]) * float(row["PITE"])
                    pit_dia = 1.0 - (1.0 - _clip01(pit1)) ** nt if nt > 0 else 0.0
                    it = _bernoulli(rng, pit_dia) if nt > 0 else 0
                it_hacia[int(aid)].append(it)
                # IM (medio X → medio Y) se rellena en el bloque 3;
                # aquí dejamos un hueco que actualizaremos después.
                hit_rows.append(
                    {
                        "dia": d,
                        "X": x,
                        "Y": int(aid),
                        "NT": nt,
                        "IT": it,
                        "IM": 0,
                    }
                )

            # --- 2.b Infección del agente Y por SU propio medio ---
            # PIM(M,Y)_d = 1 - Π_k (1 - PIME(Y) · MI(Y)_{d-k}), k = 1,2,3
            # (en el texto aparece PIME(I) en el tercer factor: lo tomamos
            # como PIME(Y); los tres retardos son del medio de Y, no de X)
            pime_y = float(row["PIME"])
            mi_lags_y = [
                _mi_en_dia(mi_idx, int(aid), dia_anterior),      # MI(Y)_{d-1}
                _mi_en_dia(mi_idx, int(aid), dia_anterior - 1),  # MI(Y)_{d-2}
                _mi_en_dia(mi_idx, int(aid), dia_anterior - 2),  # MI(Y)_{d-3}
            ]
            pim_my = _prob_desde_lags(pime_y, mi_lags_y)
            imy = _bernoulli(rng, pim_my) if pim_my > 0 else 0

            # AI_d = 1 si hubo infección por medio O por algún transporte
            producto_limpio = (1 - imy)
            for it in it_hacia[int(aid)]:
                producto_limpio *= (1 - it)
            ai_nuevo = 0 if producto_limpio == 1 else 1

        im_agente[int(aid)] = imy
        nuevo.at[aid, "AI"] = int(ai_nuevo)

    # ------------------------------------------------------------------
    # 3. Infección del medio natural alrededor de cada Y
    # ------------------------------------------------------------------
    # Índice (X, Y) → IM para volcar luego en HIT
    im_medio: dict[tuple[int, int], int] = {}

    for aid, row in prev.iterrows():
        # 3.a El medio se "limpia" solo: cada día se reduce a la mitad
        mi = 0.5 * float(row["MI"])

        # 3.b El propio agente contamina su entorno SOLO si ayer estaba
        #     en infección silente (AI==1). Una vez declarado, se asume
        #     que ya no vierte al medio de la misma forma.
        p_propio = float(row["PIMS"]) * (1.0 if int(row["AI"]) == 1 else 0.0)
        iym = _bernoulli(rng, p_propio)
        mi = mi + iym

        # 3.c Contagio desde el medio de cada otro agente X
        for x in ids:
            if int(x) == int(aid):
                continue
            # D(B,A) del texto = distancia entre X e Y (euclídea, simétrica)
            dist_xy = dist.get((int(x), int(aid)))
            if dist_xy is None:
                dist_xy = dist.get((int(aid), int(x)))
            if dist_xy is None:
                continue
            mi_lags_x = [
                _mi_en_dia(mi_idx, int(x), dia_anterior),
                _mi_en_dia(mi_idx, int(x), dia_anterior - 1),
                _mi_en_dia(mi_idx, int(x), dia_anterior - 2),
            ]
            # PIM(X,Y) = 1 - Π (1 - PM(X,Y)·MI(X)_lag / max(1, D(X,Y)))
            pim_xy = _prob_desde_lags(
                float(pm_ab.get((int(x), int(aid)), 0.05)),
                mi_lags_x,
                distancia=dist_xy,
            )
            im_xy = _bernoulli(rng, pim_xy) if pim_xy > 0 else 0
            im_medio[(int(x), int(aid))] = im_xy
            mi = mi + im_xy

        # 3.d Tope [0, 1] y umbral de extinción
        mi = min(1.0, float(mi))
        if mi < 0.05:
            mi = 0.0
        nuevo.at[aid, "MI"] = round(mi, 4)

        him_rows.append(
            {
                "dia": d,
                "Y": int(aid),
                "IMY": int(im_agente.get(int(aid), 0)),
                "IYM": int(iym),
            }
        )

    # Completa IM en las filas HIT que ya teníamos (rutas con M>0)
    for fila in hit_rows:
        clave = (int(fila["X"]), int(fila["Y"]))
        fila["IM"] = int(im_medio.get(clave, 0))

    # Añade a HIT los pares donde hubo contagio medio→medio aunque M=0
    ya = {(int(f["X"]), int(f["Y"])) for f in hit_rows}
    for (x, y), im in im_medio.items():
        if im and (x, y) not in ya:
            hit_rows.append({"dia": d, "X": x, "Y": y, "NT": 0, "IT": 0, "IM": 1})

    # Instantánea del día para la tabla HAS
    has_rows = [
        {
            "dia": d,
            "AID": int(aid),
            "AC": int(nuevo.loc[aid, "AC"]),
            "AI": int(nuevo.loc[aid, "AI"]),
            "MI": float(nuevo.loc[aid, "MI"]),
        }
        for aid in nuevo.index
    ]

    agentes_out = nuevo.reset_index(drop=True)
    has_out = pd.concat([has, pd.DataFrame(has_rows)], ignore_index=True)
    hit_out = pd.concat([hit, pd.DataFrame(hit_rows)], ignore_index=True) if hit_rows else hit
    him_out = pd.concat([him, pd.DataFrame(him_rows)], ignore_index=True)
    return agentes_out, has_out, hit_out, him_out


def snapshot_dia0(agentes: pd.DataFrame) -> pd.DataFrame:
    """HAS del día 0: la foto inicial, antes de simular."""
    filas = [
        {
            "dia": 0,
            "AID": int(r["AID"]),
            "AC": int(r["AC"]),
            "AI": int(r["AI"]),
            "MI": float(r["MI"]),
        }
        for _, r in agentes.iterrows()
    ]
    return pd.DataFrame(filas, columns=HAS_COLS)


def sistema_estable(agentes: pd.DataFrame) -> bool:
    """Parada: todos los agentes limpios y todo el medio a 0."""
    if agentes.empty:
        return True
    return bool((agentes["AI"] == 0).all() and (agentes["MI"] == 0).all())


def agentes_en_dia(agentes: pd.DataFrame, has: pd.DataFrame, dia: int) -> pd.DataFrame:
    """Combina la ficha fija del agente con AI/AC/MI de un día concreto."""
    if agentes.empty or has.empty:
        return agentes.copy()
    snap = has.loc[has["dia"] == dia, ["AID", "AI", "AC", "MI"]]
    if snap.empty:
        return agentes.copy()
    base = agentes.drop(columns=["AI", "AC", "MI"])
    return base.merge(snap, on="AID", how="left")


def series_estados(has: pd.DataFrame, agentes: pd.DataFrame) -> pd.DataFrame:
    """
    Serie diaria para la pestaña Análisis:
      nº de agentes y nº de animales en silente / declarada / desinfección / cuarentena.
    """
    if has.empty:
        return pd.DataFrame()
    an = agentes.set_index("AID")["AN"]
    h = has.copy()
    h["AN"] = h["AID"].map(an).fillna(0)
    filas = []
    for dia, g in h.groupby("dia"):
        filas.append(
            {
                "dia": int(dia),
                "n_silente": int((g["AI"] == 1).sum()),
                "n_declarada": int((g["AI"] == 2).sum()),
                "n_desinfeccion": int((g["AI"] == 3).sum()),
                "n_cuarentena": int((g["AC"] == 1).sum()),
                "anim_silente": int(g.loc[g["AI"] == 1, "AN"].sum()),
                "anim_declarada": int(g.loc[g["AI"] == 2, "AN"].sum()),
                "anim_desinfeccion": int(g.loc[g["AI"] == 3, "AN"].sum()),
                "anim_cuarentena": int(g.loc[g["AC"] == 1, "AN"].sum()),
            }
        )
    return pd.DataFrame(filas).sort_values("dia")


def series_costes(has: pd.DataFrame, agentes: pd.DataFrame, costes: dict) -> pd.DataFrame:
    """
    Costes diarios (sección 7).

    Cuarentena granja (GC/GE):  CFCG + CACG * AN   si AC=1
    Cuarentena matadero (MA):   CFCM + CACM * AN   si AC=1
    Limpieza granja:            CFLG + CALG * AN   si AI=3
    Limpieza matadero:          CFLM + CALM * AN   si AI=3
    """
    if has.empty:
        return pd.DataFrame()
    meta = agentes.set_index("AID")[["AT", "AN"]]
    h = has.copy()
    h = h.merge(meta, left_on="AID", right_index=True, how="left")
    es_granja = h["AT"].isin(["GC", "GE"])
    es_mata = h["AT"] == "MA"
    en_c = h["AC"] == 1
    en_l = h["AI"] == 3

    h["c_c_granja"] = np.where(es_granja & en_c, costes["CFCG"] + costes["CACG"] * h["AN"], 0.0)
    h["c_c_mata"] = np.where(es_mata & en_c, costes["CFCM"] + costes["CACM"] * h["AN"], 0.0)
    h["c_l_granja"] = np.where(es_granja & en_l, costes["CFLG"] + costes["CALG"] * h["AN"], 0.0)
    h["c_l_mata"] = np.where(es_mata & en_l, costes["CFLM"] + costes["CALM"] * h["AN"], 0.0)

    out = (
        h.groupby("dia", as_index=False)[["c_c_granja", "c_c_mata", "c_l_granja", "c_l_mata"]]
        .sum()
        .sort_values("dia")
    )
    out["c_total"] = out["c_c_granja"] + out["c_c_mata"] + out["c_l_granja"] + out["c_l_mata"]
    return out


@dataclass
class Simulacion:
    """
    Estado completo que guarda Streamlit en st.session_state.

    day     último día ya simulado (0 = solo condiciones iniciales)
    running la simulación se está ejecutando sola
    playing se está re reproduciendo el histórico en el mapa
    """

    params: dict = field(default_factory=valores_por_defecto)
    agentes: pd.DataFrame = field(default_factory=pd.DataFrame)
    conexiones: pd.DataFrame = field(default_factory=pd.DataFrame)
    has: pd.DataFrame = field(default_factory=_empty_has)
    hit: pd.DataFrame = field(default_factory=_empty_hit)
    him: pd.DataFrame = field(default_factory=_empty_him)
    day: int = 0
    running: bool = False
    playing: bool = False
    view_day: int = 0
    rng_seed: int = 42
    gen_id: int = 0

    def generar(self, params: dict) -> None:
        """Botón 'Generar agentes': reconstruye el mundo y borra el histórico."""
        self.params = dict(params)
        rng = np.random.default_rng(int(params.get("semilla", 42)))
        self.rng_seed = int(params.get("semilla", 42))
        self.agentes = generar_agentes(params, rng)
        self.conexiones = generar_conexiones(
            self.agentes,
            rng,
            pm_default=float(params.get("PM", 0.05)),
        )
        self.gen_id += 1
        self.resetear_estados(mantener_brote=False)

    def resetear_estados(self, mantener_brote: bool = False) -> None:
        """
        Botón Reiniciar: AI, AC, MI a 0, tablas históricas vacías, día 0.
        Si mantener_brote=False también se pierden los focos iniciales.
        """
        if self.agentes.empty:
            self.has, self.hit, self.him = _empty_has(), _empty_hit(), _empty_him()
            self.day = 0
            self.view_day = 0
            self.running = False
            self.playing = False
            return
        brotes = set(self.agentes.loc[self.agentes["AI"] == 1, "AID"]) if mantener_brote else set()
        self.agentes = self.agentes.copy()
        self.agentes["AI"] = 0
        self.agentes["AC"] = 0
        self.agentes["MI"] = 0.0
        if brotes:
            self.agentes.loc[self.agentes["AID"].isin(brotes), "AI"] = 1
        self.has = snapshot_dia0(self.agentes)
        self.hit = _empty_hit()
        self.him = _empty_him()
        self.day = 0
        self.view_day = 0
        self.running = False
        self.playing = False

    def marcar_brote(self, aids: list[int], silente: bool = True) -> None:
        """Pone (o quita) infección silente en el día 0, antes de simular."""
        if self.agentes.empty or self.day != 0:
            return
        self.agentes = self.agentes.copy()
        self.agentes["AI"] = 0
        if silente and aids:
            self.agentes.loc[self.agentes["AID"].isin(aids), "AI"] = 1
        self.has = snapshot_dia0(self.agentes)

    def toggle_brote(self, aid: int) -> None:
        """Click en el mapa: alterna limpio ↔ silente en día 0."""
        if self.agentes.empty or self.day != 0:
            return
        self.agentes = self.agentes.copy()
        mask = self.agentes["AID"] == int(aid)
        actual = int(self.agentes.loc[mask, "AI"].iloc[0])
        self.agentes.loc[mask, "AI"] = 0 if actual == 1 else 1
        self.has = snapshot_dia0(self.agentes)

    def aplicar_edicion_agentes(self, editado: pd.DataFrame) -> None:
        """Tras el data_editor: copia parámetros editables y recalcula V."""
        if editado.empty:
            return
        estado = self.agentes.set_index("AID")[["AI", "AC", "MI"]]
        out = editado.copy().set_index("AID")
        out.loc[estado.index, ["AI", "AC", "MI"]] = estado[["AI", "AC", "MI"]]
        self.agentes = out.reset_index()
        if not self.conexiones.empty:
            self.conexiones = actualizar_vigilancia(self.agentes, self.conexiones)

    def aplicar_edicion_conexiones(self, editado: pd.DataFrame) -> None:
        """El usuario puede retocar a mano M (transportes) y PM (medio→medio)."""
        if editado.empty or self.conexiones.empty:
            return
        edit = editado.set_index(["IDA", "IDB"])
        c = self.conexiones.copy()
        c["M"] = [
            float(edit["M"].get((int(r["IDA"]), int(r["IDB"])), r["M"]))
            for _, r in c.iterrows()
        ]
        if "PM" in edit.columns:
            c["PM"] = [
                float(edit["PM"].get((int(r["IDA"]), int(r["IDB"])), r.get("PM", 0.05)))
                for _, r in c.iterrows()
            ]
        self.conexiones = c

    def paso(self) -> bool:
        """Simula el día siguiente. Devuelve True si el sistema ya está estable."""
        if self.agentes.empty:
            return True
        if sistema_estable(self.agentes) and self.day > 0:
            self.running = False
            return True
        rng = np.random.default_rng(self.rng_seed + 10007 * (self.day + 1))
        self.agentes, self.has, self.hit, self.him = simular_un_dia(
            agentes=self.agentes,
            conexiones=self.conexiones,
            has=self.has,
            hit=self.hit,
            him=self.him,
            dia_anterior=self.day,
            rng=rng,
        )
        self.day += 1
        self.view_day = self.day
        if sistema_estable(self.agentes) or self.day >= int(self.params.get("max_dias", 365)):
            self.running = False
            return True
        return False
