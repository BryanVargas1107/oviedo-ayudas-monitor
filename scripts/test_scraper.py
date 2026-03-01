"""
Script de prueba para verificar que scraper + parser funcionan
contra la sede real antes de conectar el resto del pipeline.
Ejecutar con: python -m scripts.test_scraper
"""

import logging
from src.scraper import run_scraper
from src.parser import parse_all

# Configuramos logging para ver qué está pasando
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    print("=" * 60)
    print("TEST: Scraper + Parser — Sede Ayuntamiento de Oviedo")
    print("=" * 60)

    print("\n[1/2] Ejecutando scraper...")
    raw_data = run_scraper()
    print(f"\n  → {len(raw_data)} convocatorias encontradas en crudo")

    print("\n[2/2] Parseando resultados...")
    convocatorias = parse_all(raw_data)
    print(f"\n  → {len(convocatorias)} convocatorias parseadas correctamente")

    print("\n" + "=" * 60)
    print("MUESTRA DE RESULTADOS (primeras 3 convocatorias):")
    print("=" * 60)

    for i, c in enumerate(convocatorias[:3], 1):
        print(f"\n[{i}] {c.titulo}")
        print(f"    URL:          {c.url}")
        print(f"    Categoría:    {c.categoria}")
        print(f"    Estado:       {c.estado}")
        print(f"    Plazo fin:    {c.plazo_fin}")
        print(f"    Beneficiarios:{c.beneficiarios[:80]}...")
        print(f"    Hash:         {c.hash_contenido}")
        print(f"    Descripción:  {c.descripcion[:100]}...")