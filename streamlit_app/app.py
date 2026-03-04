"""
Alertas Subvenciones Oviedo — Interfaz Streamlit.
Punto de entrada de la aplicación.
"""

import streamlit as st

st.set_page_config(
    page_title="Alertas Subvenciones Oviedo",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estilos globales ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a5276, #2980b9);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .badge-abierta   { color: #1e8449; font-weight: bold; }
    .badge-expirada  { color: #922b21; font-weight: bold; }
    .badge-sin_plazo { color: #7f8c8d; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ── Cabecera ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>📋 Alertas Subvenciones Oviedo</h1>
    <p>Monitor diario de ayudas, becas y subvenciones del Ayuntamiento de Oviedo</p>
</div>
""", unsafe_allow_html=True)

# ── Métricas de resumen ───────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, get_stats

init_db()
stats = get_stats()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total convocatorias", stats["total_convocatorias"])
col2.metric("Abiertas",            stats["abiertas"])
col3.metric("Expiradas",           stats["expiradas"])
col4.metric("Perfiles activos",    stats["perfiles_activos"])
col5.metric("Alertas pendientes",  stats["matches_pendientes"])

st.divider()

# ── Navegación ────────────────────────────────────────────────────────────────
st.markdown("### ¿Qué quieres hacer?")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("""
    #### 👤 Mi Perfil
    Crea o edita tu perfil para recibir alertas
    personalizadas según tus intereses.
    """)
    st.page_link("pages/1_Mi_Perfil.py", label="Ir a Mi Perfil →")

with col_b:
    st.markdown("""
    #### 🔍 Convocatorias
    Explora todas las convocatorias activas
    con filtros por categoría y estado.
    """)
    st.page_link("pages/2_Convocatorias.py", label="Ir a Convocatorias →")

with col_c:
    st.markdown("""
    #### 🔔 Mis Alertas
    Revisa el historial de convocatorias
    que el sistema ha detectado para ti.
    """)
    st.page_link("pages/3_Mis_Alertas.py", label="Ir a Mis Alertas →")