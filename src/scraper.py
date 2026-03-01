"""
Scraper para la sede electrónica del Ayuntamiento de Oviedo.

Responsabilidad única: dado un conjunto de URLs semilla,
devuelve una lista de dicts con el HTML en crudo de cada
convocatoria encontrada. No parsea, no limpia, no guarda.
"""

import time
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.config import (
    SEED_URLS,
    BASE_URL,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


def _build_session() -> requests.Session:
    """Crea una sesión HTTP reutilizable con headers comunes."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _get_page(session: requests.Session, url: str) -> BeautifulSoup | None:
    """
    Descarga una URL y devuelve un objeto BeautifulSoup.
    Maneja el problema de encoding ISO-8859-1 de la sede.
    Devuelve None si hay cualquier error de red.
    """
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # Usamos content (bytes) + decodificación manual para evitar
        # que requests aplique el encoding incorrecto de la cabecera HTTP
        encoding = response.apparent_encoding or "utf-8"
        try:
            text = response.content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            text = response.content.decode("utf-8", errors="replace")

        return BeautifulSoup(text, "html.parser")

    except requests.exceptions.Timeout:
        logger.warning(f"Timeout al acceder a: {url}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code} en: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de red en {url}: {e}")
        return None


def _is_convocatoria_url(url: str) -> bool:
    """
    Determina si una URL apunta a una convocatoria individual
    (no a una categoría/listado).

    Las URLs de categoría tienen 2 segmentos: /tramites/categoria
    Las URLs de convocatoria tienen 3 segmentos: /tramites/categoria/nombre
    """
    path = urlparse(url).path
    # Eliminamos slashes del principio y final y contamos segmentos
    segments = [s for s in path.strip("/").split("/") if s]
    return len(segments) == 3 and segments[0] == "tramites"

# Palabras clave que identifican convocatorias relevantes
# Se buscan en la URL (slug) y en el título
_KEYWORDS_RELEVANTES = {
    "subvenci", "ayuda", "beca", "convocatoria", "premio",
    "incentivo", "programa", "cooperacion", "prestacion",
    "bonificiacion", "bonificaci", "justificacion",
}

def _is_relevant(url: str, titulo: str = "") -> bool:
    """
    Filtra solo las páginas que son ayudas, subvenciones o becas.
    Comprueba tanto la URL (slug) como el título de la página.
    """
    texto = (url + " " + titulo).lower()
    return any(kw in texto for kw in _KEYWORDS_RELEVANTES)

def _extract_convocatoria_links(soup: BeautifulSoup, seed_url: str) -> list[str]:
    """
    Extrae todos los enlaces a convocatorias individuales
    desde una página de categoría (seed URL).
    """
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Construye URL absoluta si el href es relativo
        full_url = urljoin(BASE_URL, href)
        # Solo queremos URLs del mismo dominio
        if urlparse(full_url).netloc != urlparse(BASE_URL).netloc:
            continue
        if _is_convocatoria_url(full_url):
            links.append(full_url)

    # Eliminamos duplicados manteniendo el orden
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def _scrape_convocatoria(
    session: requests.Session, url: str, categoria: str
) -> dict | None:
    """
    Descarga una convocatoria individual y extrae sus campos en crudo.
    Devuelve un dict con el HTML sin procesar de cada sección.
    """
    soup = _get_page(session, url)
    if soup is None:
        return None

    # Intentamos extraer el contenido principal
    # La sede usa un div con id="main-content" o similar como contenedor
    main = (
        soup.find("div", id="main-content")
        or soup.find("div", class_="portlet-body")
        or soup.find("main")
        or soup.find("article")
        or soup.body
    )

    if main is None:
        logger.warning(f"No se encontró contenido principal en: {url}")
        return None

    # Extraemos la categoría del PATH de la URL, no de la URL completa
    # urlparse separa el dominio del path correctamente
    # Ejemplo: /tramites/deportes/subvenciones-... → path_segments[1] = "deportes"
    url_path = urlparse(url).path
    path_segments = [s for s in url_path.strip("/").split("/") if s]
    categoria_real = path_segments[1] if len(path_segments) >= 3 else categoria

    return {
        "url": url,
        "categoria": categoria_real,
        "titulo": _extract_titulo(soup),
        "html_contenido": str(main),
        "texto_contenido": main.get_text(separator=" ", strip=True),
    }


def _extract_titulo(soup: BeautifulSoup) -> str:
    """Extrae el título de la página con fallbacks progresivos."""
    # Intento 1: <h1> — existe pero puede estar vacío en Liferay
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text:  # Solo devuelve si tiene contenido real
            return text

    # Intento 2: <title> — siempre tiene contenido
    # Formato: "Nombre convocatoria - Sede electrónica"
    title_tag = soup.find("title")
    if title_tag:
        full_title = title_tag.get_text(strip=True)
        return full_title.split(" - ")[0].strip()

    # Fallback final
    return "Sin título"


def run_scraper() -> list[dict]:
    """
    Función principal del scraper.
    Recorre todas las seed URLs, encuentra convocatorias
    y devuelve una lista de dicts con los datos en crudo.
    """
    session = _build_session()
    all_raw_data = []
    
    # Deduplicación GLOBAL entre seeds: la misma URL no se descarga dos veces
    # aunque aparezca en el menú de navegación de varias páginas semilla
    seen_urls: set[str] = set()
    total_links_found = 0

    for seed_url in SEED_URLS:
        categoria = seed_url.rstrip("/").split("/")[-1]
        logger.info(f"Procesando categoría: {categoria}")

        seed_soup = _get_page(session, seed_url)
        if seed_soup is None:
            logger.error(f"No se pudo acceder a la seed URL: {seed_url}")
            continue

        links = _extract_convocatoria_links(seed_soup, seed_url)
        
        # Filtramos los ya vistos en seeds anteriores
        new_links = [l for l in links if l not in seen_urls]
        seen_urls.update(new_links)
        
        logger.info(
            f"  → {len(links)} encontradas, "
            f"{len(new_links)} nuevas (sin duplicados entre seeds)"
        )
        total_links_found += len(new_links)

        for link in new_links:
             # Filtro rápido por URL antes de hacer la petición HTTP
            if not _is_relevant(link):
                logger.debug(f"    ✗ Descartada por URL: {link.split('/')[-1]}")
                continue
            time.sleep(REQUEST_DELAY)
            raw_data = _scrape_convocatoria(session, link, categoria)
            if raw_data:
                # Segundo filtro: por título una vez descargada
                if not _is_relevant(raw_data["url"], raw_data["titulo"]):
                    logger.debug(f"    ✗ Descartada por título: {raw_data['titulo'][:50]}")
                    continue
                all_raw_data.append(raw_data)
                logger.info(f"    ✓ {raw_data['titulo'][:60]}")

    logger.info(
        f"Scraping completado: {len(all_raw_data)}/{total_links_found} "
        f"convocatorias extraídas correctamente"
    )
    return all_raw_data