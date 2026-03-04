"""
Página: Mis Alertas
Historial de matches y notificaciones del sistema.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from src.database import get_connection, init_db, get_perfiles_activos

st.set_page_config(
    page_title="Mis Alertas — Alertas Subvenciones Oviedo",
    page_icon="🔔",
    layout="wide",
)
st.title("🔔 Mis Alertas")
st.caption("Historial de convocatorias detectadas para cada perfil.")

init_db()

# ── Carga de datos ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_matches():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                p.nombre        AS perfil,
                p.email         AS email,
                c.titulo        AS convocatoria,
                c.categoria     AS categoria,
                c.estado        AS estado_conv,
                c.url           AS url,
                m.score_similitud AS score,
                m.motivo        AS motivo,
                m.notificado    AS notificado,
                m.fecha_match   AS fecha_match,
                m.fecha_notif   AS fecha_notif
            FROM matches m
            JOIN perfiles      p ON m.perfil_id      = p.id
            JOIN convocatorias c ON m.convocatoria_id = c.id
            ORDER BY m.fecha_match DESC
        """).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

df = load_matches()
perfiles = get_perfiles_activos()

# ── Sin datos ─────────────────────────────────────────────────────────────────

if df.empty:
    st.info(
        "No hay alertas registradas todavía. "
        "Las alertas aparecen aquí cuando el pipeline detecta convocatorias "
        "relevantes para tus perfiles."
    )
    if not perfiles:
        st.warning("Además, no tienes ningún perfil activo. Crea uno en la página **Mi Perfil**.")
    st.stop()

# ── Filtros ───────────────────────────────────────────────────────────────────

st.markdown("### Filtros")
col1, col2, col3 = st.columns(3)

perfiles_disponibles = ["Todos"] + sorted(df["perfil"].unique().tolist())
perfil_sel = col1.selectbox("Perfil", perfiles_disponibles)

motivos_disponibles = ["Todos", "nueva", "actualizada"]
motivo_sel = col2.selectbox("Motivo", motivos_disponibles)

notif_opciones = {"Todos": None, "Notificados": 1, "Pendientes": 0}
notif_sel = col3.selectbox("Estado notificación", list(notif_opciones.keys()))

# Aplicamos filtros
df_f = df.copy()
if perfil_sel != "Todos":
    df_f = df_f[df_f["perfil"] == perfil_sel]
if motivo_sel != "Todos":
    df_f = df_f[df_f["motivo"] == motivo_sel]
if notif_opciones[notif_sel] is not None:
    df_f = df_f[df_f["notificado"] == notif_opciones[notif_sel]]

# ── Métricas rápidas ──────────────────────────────────────────────────────────

st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total alertas",    len(df_f))
m2.metric("Notificadas",      int(df_f["notificado"].sum()))
m3.metric("Pendientes",       int((df_f["notificado"] == 0).sum()))
m4.metric("Score promedio",   f"{df_f['score'].mean():.2f}" if not df_f.empty else "—")

st.divider()

# ── Tabla de alertas ──────────────────────────────────────────────────────────

if df_f.empty:
    st.warning("No hay alertas que coincidan con los filtros.")
else:
    # Formateamos para mostrar
    df_display = df_f[[
        "perfil", "convocatoria", "score", "motivo",
        "estado_conv", "notificado", "fecha_match"
    ]].copy()

    df_display["score"]       = df_display["score"].apply(lambda x: f"{x:.2f}")
    df_display["notificado"]  = df_display["notificado"].apply(lambda x: "✅" if x else "⏳")
    df_display["fecha_match"] = pd.to_datetime(df_display["fecha_match"]).dt.strftime("%d/%m/%Y %H:%M")

    df_display.columns = [
        "Perfil", "Convocatoria", "Score", "Motivo",
        "Estado", "Notificado", "Fecha"
    ]

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Detalle al hacer clic en una fila
    st.divider()
    st.markdown("### Detalle de alerta")
    titulos = df_f["convocatoria"].tolist()
    sel = st.selectbox("Selecciona una convocatoria para ver el detalle", titulos)

    if sel:
        row = df_f[df_f["convocatoria"] == sel].iloc[0]
        col_a, col_b = st.columns(2)
        col_a.markdown(f"**Perfil:** {row['perfil']}")
        col_a.markdown(f"**Email:** {row['email']}")
        col_a.markdown(f"**Score de relevancia:** `{row['score']:.3f}`")
        col_a.markdown(f"**Motivo:** `{row['motivo']}`")
        col_b.markdown(f"**Estado convocatoria:** `{row['estado_conv']}`")
        col_b.markdown(f"**Categoría:** `{row['categoria']}`")
        col_b.markdown(f"**Notificado:** {'✅ Sí' if row['notificado'] else '⏳ Pendiente'}")
        if row["fecha_notif"]:
            col_b.markdown(f"**Fecha notificación:** {row['fecha_notif'][:10]}")
        st.markdown(f"[🔗 Ver convocatoria en la sede electrónica]({row['url']})")