"""
Script de diagnóstico: inspecciona el HTML real que recibe el scraper
de UNA página concreta para identificar la estructura correcta.
Ejecutar con: python -m scripts.debug_page
"""

import requests
from bs4 import BeautifulSoup

# Una URL concreta que sabemos que debería tener contenido real
# (la de subvenciones para autónomos y pymes que aparecía en los warnings)
TEST_URL = "https://sede.oviedo.es/tramites/subvenciones/subvenciones-para-autonomos-y-pymes"

USER_AGENT = "Mozilla/5.0 (compatible; OviedoAyudasMonitor/1.0)"

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    print(f"Descargando: {TEST_URL}\n")
    response = session.get(TEST_URL, timeout=15)

    print(f"Status code:       {response.status_code}")
    print(f"Encoding (header): {response.encoding}")
    print(f"Apparent encoding: {response.apparent_encoding}")
    print(f"Content-Type:      {response.headers.get('Content-Type')}")
    print(f"Longitud HTML:     {len(response.content)} bytes\n")

    # Probamos los dos encodings y vemos cuál da texto legible
    for enc in [response.encoding, response.apparent_encoding, "utf-8", "iso-8859-1"]:
        try:
            response.encoding = enc
            text_sample = response.text[:200]
            print(f"Con encoding '{enc}': {repr(text_sample[:80])}")
        except Exception as e:
            print(f"Con encoding '{enc}': ERROR - {e}")

    print("\n" + "="*60)
    print("PARSEANDO CON BEAUTIFULSOUP (forzando utf-8):")
    print("="*60)

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    # ── Diagnóstico de título ──────────────────────────────────────
    print("\n[TÍTULO]")
    h1 = soup.find("h1")
    print(f"  <h1>: {h1.get_text(strip=True) if h1 else 'NO ENCONTRADO'}")

    title = soup.find("title")
    print(f"  <title>: {title.get_text(strip=True) if title else 'NO ENCONTRADO'}")

    # ── Diagnóstico de contenedores principales ───────────────────
    print("\n[CONTENEDORES PRINCIPALES]")
    candidates = [
        ("div#main-content",     soup.find("div", id="main-content")),
        ("div.portlet-body",     soup.find("div", class_="portlet-body")),
        ("main",                 soup.find("main")),
        ("article",              soup.find("article")),
        ("div#content",          soup.find("div", id="content")),
        ("div.journal-content",  soup.find("div", class_="journal-content-article")),
        ("div.portlet-content",  soup.find("div", class_="portlet-content")),
    ]

    for label, element in candidates:
        if element:
            text = element.get_text(strip=True)
            print(f"  ✓ {label}: {len(text)} chars — '{text[:80]}...'")
        else:
            print(f"  ✗ {label}: no encontrado")

    # ── Mostramos TODOS los divs con id para encontrar el bueno ───
    print("\n[TODOS LOS DIV CON ID]")
    for div in soup.find_all("div", id=True):
        text = div.get_text(strip=True)
        if len(text) > 50:  # Solo los que tienen contenido real
            print(f"  id='{div['id']}': {len(text)} chars")

    # ── Guardamos el HTML completo para inspección manual ─────────
    output_path = "data/debug_page.html"
    with open(output_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(response.text)
    print(f"\n[ARCHIVO] HTML completo guardado en: {output_path}")
    print("Ábrelo en el navegador o en VS Code para ver la estructura real.")

if __name__ == "__main__":
    main()