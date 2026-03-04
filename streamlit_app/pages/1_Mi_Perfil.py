"""
Página: Mi Perfil
Permite crear, ver y editar perfiles de usuario.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from datetime import datetime
from src.database import get_connection, init_db

st.set_page_config(page_title="Mi Perfil — Alertas Subvenciones Oviedo", page_icon="👤")
st.title("👤 Mi Perfil")
st.caption("Crea tu perfil para recibir alertas personalizadas de convocatorias relevantes.")

init_db()

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_all_perfiles():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM perfiles ORDER BY fecha_creacion DESC").fetchall()

def create_perfil(nombre, email, tipo, descripcion):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO perfiles (nombre, email, tipo_beneficiario, descripcion_libre, activo, fecha_creacion)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (nombre, email, tipo, descripcion, datetime.now().isoformat()))

def update_perfil(perfil_id, nombre, email, tipo, descripcion, activo):
    with get_connection() as conn:
        conn.execute("""
            UPDATE perfiles SET
                nombre=?, email=?, tipo_beneficiario=?, descripcion_libre=?, activo=?
            WHERE id=?
        """, (nombre, email, tipo, descripcion, int(activo), perfil_id))

def delete_perfil(perfil_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM matches WHERE perfil_id=?", (perfil_id,))
        conn.execute("DELETE FROM perfiles WHERE id=?", (perfil_id,))

# ── Mapa de tipos ─────────────────────────────────────────────────────────────

TIPOS = {
    "fisica":     "🧑 Persona física (familia, estudiante...)",
    "autonomo":   "🏪 Autónomo o pequeña empresa",
    "asociacion": "🤝 Asociación u ONG",
    "deportista": "⚽ Deportista o club deportivo",
}

# ── Formulario de creación ────────────────────────────────────────────────────

with st.expander("➕ Crear nuevo perfil", expanded=False):
    with st.form("form_nuevo_perfil"):
        st.markdown("##### Datos del perfil")
        col1, col2 = st.columns(2)
        nombre = col1.text_input("Nombre o razón social *", placeholder="Ej: Familia García")
        email  = col2.text_input("Email para notificaciones *", placeholder="tu@email.com")

        tipo = st.selectbox(
            "Tipo de beneficiario *",
            options=list(TIPOS.keys()),
            format_func=lambda x: TIPOS[x],
        )

        descripcion = st.text_area(
            "Descripción de tus intereses *",
            placeholder=(
                "Describe qué tipo de ayudas buscas y para qué. "
                "Cuanto más detallado, mejor será el matching.\n\n"
                "Ej: Soy autónomo con una pequeña tienda de ropa en Oviedo. "
                "Busco subvenciones para comercio local, reformas y digitalización."
            ),
            height=120,
        )

        submitted = st.form_submit_button("Crear perfil", type="primary")

        if submitted:
            if not nombre or not email or not descripcion:
                st.error("Por favor rellena todos los campos obligatorios.")
            elif "@" not in email:
                st.error("El email no parece válido.")
            else:
                create_perfil(nombre, email, tipo, descripcion)
                st.success(f"✅ Perfil '{nombre}' creado correctamente.")
                st.rerun()

# ── Lista de perfiles existentes ──────────────────────────────────────────────

st.markdown("### Perfiles existentes")
perfiles = get_all_perfiles()

if not perfiles:
    st.info("No hay perfiles todavía. Crea el primero usando el formulario de arriba.")
else:
    for p in perfiles:
        estado_icon = "🟢" if p["activo"] else "🔴"
        with st.expander(f"{estado_icon} {p['nombre']} — {p['email']}"):
            with st.form(f"form_editar_{p['id']}"):
                col1, col2 = st.columns(2)
                nombre_ed = col1.text_input("Nombre", value=p["nombre"], key=f"n_{p['id']}")
                email_ed  = col2.text_input("Email",  value=p["email"],  key=f"e_{p['id']}")

                tipo_keys = list(TIPOS.keys())
                tipo_idx  = tipo_keys.index(p["tipo_beneficiario"]) if p["tipo_beneficiario"] in tipo_keys else 0
                tipo_ed   = st.selectbox(
                    "Tipo",
                    options=tipo_keys,
                    index=tipo_idx,
                    format_func=lambda x: TIPOS[x],
                    key=f"t_{p['id']}",
                )

                desc_ed  = st.text_area("Descripción", value=p["descripcion_libre"] or "", key=f"d_{p['id']}", height=100)
                activo_ed = st.checkbox("Perfil activo (recibe alertas)", value=bool(p["activo"]), key=f"a_{p['id']}")

                col_save, col_del, _ = st.columns([1, 1, 3])
                save = col_save.form_submit_button("💾 Guardar", type="primary")
                delete = col_del.form_submit_button("🗑️ Eliminar")

                if save:
                    update_perfil(p["id"], nombre_ed, email_ed, tipo_ed, desc_ed, activo_ed)
                    st.success("Perfil actualizado.")
                    st.rerun()

                if delete:
                    delete_perfil(p["id"])
                    st.warning(f"Perfil '{p['nombre']}' eliminado.")
                    st.rerun()