"""
Script de prueba para el motor de matching semántico.
Inserta perfiles de prueba, corre el pipeline completo
y muestra los matches encontrados con su score.
Ejecutar con: python -m scripts.test_matcher
"""

import logging
from datetime import datetime
from src.scraper import run_scraper
from src.parser import parse_all
from src.database import init_db, upsert_all, get_perfiles_activos, get_connection
from src.matcher import run_matching

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ── Perfiles de prueba que cubren los 4 tipos ────────────────────────────────
PERFILES_PRUEBA = [
    {
        "nombre": "Familia García",
        "email": "familia@test.com",
        "tipo_beneficiario": "fisica",
        "descripcion_libre": (
            "Familia con hijos en edad escolar. "
            "Buscamos ayudas para material escolar, comedor y actividades educativas."
        ),
    },
    {
        "nombre": "Taller Mecánico Pérez",
        "email": "taller@test.com",
        "tipo_beneficiario": "autonomo",
        "descripcion_libre": (
            "Autónomo con taller mecánico en Oviedo. "
            "Interesado en subvenciones para pequeños negocios y comercio local."
        ),
    },
    {
        "nombre": "Asociación Vecinal Norte",
        "email": "asociacion@test.com",
        "tipo_beneficiario": "asociacion",
        "descripcion_libre": (
            "Asociación sin ánimo de lucro de participación ciudadana. "
            "Buscamos subvenciones para proyectos sociales y culturales en el barrio."
        ),
    },
    {
        "nombre": "Club Deportivo Oviedo Junior",
        "email": "club@test.com",
        "tipo_beneficiario": "deportista",
        "descripcion_libre": (
            "Club deportivo con jóvenes deportistas de atletismo. "
            "Buscamos subvenciones para competiciones, material y formación deportiva."
        ),
    },
]


def insert_perfiles_prueba() -> int:
    """Inserta los perfiles de prueba si no existen ya."""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM perfiles").fetchone()[0]
        if existing > 0:
            print(f"  → Ya existen {existing} perfiles en la DB, no se reinsertan")
            return existing

        now = datetime.now().isoformat()
        for p in PERFILES_PRUEBA:
            conn.execute("""
                INSERT INTO perfiles
                    (nombre, email, tipo_beneficiario, descripcion_libre, activo, fecha_creacion)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (p["nombre"], p["email"], p["tipo_beneficiario"], p["descripcion_libre"], now))

        print(f"  → {len(PERFILES_PRUEBA)} perfiles de prueba insertados")
        return len(PERFILES_PRUEBA)


if __name__ == "__main__":
    print("=" * 60)
    print("TEST: Matching Semántico — Fase 3")
    print("=" * 60)

    print("\n[1/5] Inicializando DB...")
    init_db()

    print("\n[2/5] Insertando perfiles de prueba...")
    insert_perfiles_prueba()

    print("\n[3/5] Scraping + parsing + upsert...")
    raw_data = run_scraper()
    convocatorias = parse_all(raw_data)
    novedades = upsert_all(convocatorias)
    print(f"  → {len(novedades)} novedades para matching")

    if not novedades:
        print("\n  ⚠ La DB ya tiene estos datos del test anterior.")
        print("  Simulamos novedades pasando todas las convocatorias...")
        novedades = [(i + 1, "nueva", c) for i, c in enumerate(convocatorias)]
        print(f"  → {len(novedades)} convocatorias forzadas como novedades")

    print("\n[4/5] Cargando perfiles activos...")
    perfiles = get_perfiles_activos()
    print(f"  → {len(perfiles)} perfiles activos")

    print("\n[5/5] Ejecutando matching semántico...")
    matches = run_matching(novedades, perfiles)

    print("\n" + "=" * 60)
    print(f"RESULTADOS: {len(matches)} matches encontrados")
    print("=" * 60)

    # Agrupamos por perfil para mostrar mejor
    by_perfil: dict = {}
    for m in matches:
        key = m.perfil_nombre
        if key not in by_perfil:
            by_perfil[key] = []
        by_perfil[key].append(m)

    for perfil_nombre, perfil_matches in by_perfil.items():
        # Ordenamos por score descendente
        perfil_matches.sort(key=lambda x: x.score, reverse=True)
        print(f"\n  👤 {perfil_nombre} ({len(perfil_matches)} matches):")
        for m in perfil_matches:
            print(f"     [{m.score:.3f}] {m.convocatoria.titulo[:55]}")