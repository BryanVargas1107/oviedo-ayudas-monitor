"""
Página: Convocatorias
Dashboard con todas las convocatorias extraídas, filtros y búsqueda.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from src.database import get_connection, init_db

st.set_page_config(
    page_title="Convocatorias — Alertas Subvenciones Oviedo",
    page_icon="🔍",
    layout="wide",
)
st.title("🔍 Convocatorias")
st.caption("Todas las convocatorias extraídas de la sede electrónica del Ayuntamiento de Oviedo.")

init_db()

# ── Carga de datos ────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)  # Cache de 5 minutos
def load_convocatorias():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT titulo, categoria, estado, plazo_fin,
                   descripcion, beneficiarios, url, fecha_primera
            FROM convocatorias
            ORDER BY
                CASE estado
                    WHEN 'abierta'   THEN 1
                    WHEN 'sin_plazo' THEN 2
                    WHEN 'expirada'  THEN 3
                END,
                fecha_primera DESC
        """).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

df = load_convocatorias()

if df.empty:
    st.info("No hay convocatorias en la base de datos. Ejecuta el pipeline primero.")
    st.code("python -m scripts.run_pipeline --dry-run")
    st.stop()

# ── Filtros ───────────────────────────────────────────────────────────────────

st.markdown("### Filtros")
col1, col2, col3 = st.columns(3)

estados_disponibles = ["Todos"] + sorted(df["estado"].unique().tolist())
estado_sel = col1.selectbox("Estado", estados_disponibles)

categorias_disponibles = ["Todas"] + sorted(df["categoria"].unique().tolist())
categoria_sel = col2.selectbox("Categoría", categorias_disponibles)

busqueda = col3.text_input("🔎 Buscar en título o descripción", placeholder="ej: deporte, beca, pyme...")

# Aplicamos filtros
df_filtrado = df.copy()

if estado_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["estado"] == estado_sel]

if categoria_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["categoria"] == categoria_sel]

if busqueda:
    mask = (
        df_filtrado["titulo"].str.contains(busqueda, case=False, na=False) |
        df_filtrado["descripcion"].str.contains(busqueda, case=False, na=False)
    )
    df_filtrado = df_filtrado[mask]

# ── Contador ──────────────────────────────────────────────────────────────────

st.markdown(f"**{len(df_filtrado)}** convocatorias encontradas")
st.divider()

# ── Tarjetas de convocatorias ─────────────────────────────────────────────────

ESTADO_COLORS = {
    "abierta":   "🟢",
    "expirada":  "🔴",
    "sin_plazo": "⚪",
}

if df_filtrado.empty:
    st.warning("No hay convocatorias que coincidan con los filtros seleccionados.")
else:
    for _, row in df_filtrado.iterrows():
        icon = ESTADO_COLORS.get(row["estado"], "⚪")
        with st.expander(f"{icon} {row['titulo']}"):
            col_a, col_b, col_c = st.columns(3)
            col_a.markdown(f"**Estado:** `{row['estado']}`")
            col_b.markdown(f"**Categoría:** `{row['categoria']}`")
            col_c.markdown(f"**Plazo fin:** `{row['plazo_fin'] or 'No especificado'}`")

            if row["descripcion"]:
                st.markdown(f"**Descripción:** {row['descripcion']}")
            if row["beneficiarios"]:
                st.markdown(f"**Dirigido a:** {row['beneficiarios']}")

            st.markdown(f"[🔗 Ver en la sede electrónica]({row['url']})")