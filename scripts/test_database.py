"""
Script de prueba para verificar que la DB se inicializa
y el upsert funciona correctamente.
Ejecutar con: python -m scripts.test_database
"""

import logging
from src.scraper import run_scraper
from src.parser import parse_all
from src.database import init_db, upsert_all, get_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    print("=" * 60)
    print("TEST: Base de datos — Fase 2")
    print("=" * 60)

    print("\n[1/4] Inicializando base de datos...")
    init_db()

    print("\n[2/4] Scraping + parsing...")
    raw_data = run_scraper()
    convocatorias = parse_all(raw_data)
    print(f"  → {len(convocatorias)} convocatorias parseadas")

    print("\n[3/4] Primer upsert (todo debe ser NUEVO)...")
    novedades = upsert_all(convocatorias)
    print(f"  → {len(novedades)} novedades registradas")

    print("\n[4/4] Segundo upsert (todo debe ser SIN CAMBIOS)...")
    novedades2 = upsert_all(convocatorias)
    print(f"  → {len(novedades2)} novedades (debería ser 0)")

    print("\n" + "=" * 60)
    print("ESTADÍSTICAS DE LA DB:")
    print("=" * 60)
    stats = get_stats()
    for key, value in stats.items():
        print(f"  {key:<25}: {value}")

    # Verificación automática
    print("\n" + "=" * 60)
    print("VERIFICACIÓN:")
    if len(novedades) == len(convocatorias):
        print("  ✓ Primer upsert: todas las convocatorias son nuevas")
    else:
        print(f"  ✗ Primer upsert: esperaba {len(convocatorias)}, obtuvo {len(novedades)}")

    if len(novedades2) == 0:
        print("  ✓ Segundo upsert: cero cambios (idempotencia correcta)")
    else:
        print(f"  ✗ Segundo upsert: esperaba 0, obtuvo {len(novedades2)}")

    print("=" * 60)