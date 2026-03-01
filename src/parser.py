"""
Parser y normalizador de convocatorias.

Responsabilidad única: recibe los dicts en crudo del scraper
y devuelve objetos Convocatoria limpios y estructurados.
"""

import re
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Dataclass principal ───────────────────────────────────────────────────────

@dataclass
class Convocatoria:
    url: str
    titulo: str
    categoria: str
    descripcion: str
    beneficiarios: str
    plazo_texto: str
    plazo_inicio: Optional[date]
    plazo_fin: Optional[date]
    estado: str                  # 'abierta' | 'expirada' | 'sin_plazo'
    url_bases: Optional[str]
    hash_contenido: str
    fecha_scraping: datetime = field(default_factory=datetime.now)


# ── Patrones de fecha ─────────────────────────────────────────────────────────

# Cubre formatos como: "31/12/2024", "31-12-2024", "31 de diciembre de 2024"
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b")
_FECHA_LITERAL = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES.keys()) + r")\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)

# Palabras clave que indican plazos en el texto
_KEYWORDS_PLAZO = re.compile(
    r"(plazo|presentaci[oó]n|solicitud|hasta el|del \d|convocatoria abierta|"
    r"periodo de solicitud|fecha l[ií]mite)",
    re.IGNORECASE,
)


# ── Funciones de extracción ───────────────────────────────────────────────────

def _extract_description(soup: BeautifulSoup) -> str:
    """
    Extrae la descripción principal de la convocatoria.
    Busca el primer párrafo sustancial (más de 50 caracteres).
    """
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 50:
            return text
    # Fallback: primeros 400 caracteres del texto completo
    full_text = soup.get_text(separator=" ", strip=True)
    return full_text[:400] if full_text else ""


def _extract_beneficiarios(soup: BeautifulSoup, full_text: str) -> str:
    """
    Intenta encontrar la sección de beneficiarios/destinatarios.
    Usa múltiples estrategias en orden de fiabilidad.
    """
    keywords_section = [
        "beneficiario", "destinatario", "dirigido", "pueden solicitar",
        "quién puede", "a quién va", "personas que pueden",
    ]
    keywords_inline = [
        "beneficiarios?", "destinatarios?", "dirigido a",
        "pueden solicitar", "podrán solicitar",
    ]

    # Estrategia 1: busca encabezados con palabras clave
    for tag in soup.find_all(["h2", "h3", "h4", "strong", "b", "p"]):
        text = tag.get_text(strip=True).lower()
        if any(kw in text for kw in keywords_section):
            # Toma el siguiente elemento hermano con contenido
            next_el = tag.find_next_sibling()
            if next_el:
                content = next_el.get_text(strip=True)
                if len(content) > 10:
                    return content
            # Si no hay hermano, el propio tag puede tener el contenido
            own_text = tag.get_text(strip=True)
            if len(own_text) > 30:
                return own_text

    # Estrategia 2: regex en el texto plano
    pattern = re.compile(
        r"(" + "|".join(keywords_inline) + r")[:\s]+([^.]{20,300}\.?)",
        re.IGNORECASE,
    )
    match = pattern.search(full_text)
    if match:
        return match.group(2).strip()

    # Estrategia 3: segundo párrafo sustancial
    # (en muchas páginas el primer párrafo es descripción y el segundo son beneficiarios)
    paragraphs = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 40
    ]
    if len(paragraphs) >= 2:
        return paragraphs[1]

    return ""


def _extract_plazo(full_text: str) -> tuple[str, Optional[date], Optional[date]]:
    """
    Extrae el plazo de presentación del texto completo.
    Devuelve (texto_plazo, fecha_inicio, fecha_fin).
    """
    # Encuentra todas las fechas en el documento
    fechas_encontradas = []

    for match in _FECHA_NUMERICA.finditer(full_text):
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            fechas_encontradas.append((date(year, month, day), match.start()))
        except ValueError:
            pass

    for match in _FECHA_LITERAL.finditer(full_text):
        day = int(match.group(1))
        month = _MESES[match.group(2).lower()]
        year = int(match.group(3))
        try:
            fechas_encontradas.append((date(year, month, day), match.start()))
        except ValueError:
            pass

    if not fechas_encontradas:
        return ("", None, None)

    # Ordena por posición en el texto
    fechas_encontradas.sort(key=lambda x: x[1])
    fechas = [f[0] for f in fechas_encontradas]

    # Extrae fragmento de texto alrededor de la primera fecha como plazo_texto
    first_pos = fechas_encontradas[0][1]
    start = max(0, first_pos - 50)
    end = min(len(full_text), first_pos + 100)
    plazo_texto = full_text[start:end].strip()

    if len(fechas) == 1:
        return (plazo_texto, None, fechas[0])
    else:
        return (plazo_texto, fechas[0], fechas[-1])


def _determine_estado(plazo_fin: Optional[date], plazo_texto: str) -> str:
    """Determina si la convocatoria está abierta, expirada o sin plazo definido."""
    today = date.today()

    if plazo_fin is None:
        # Sin fecha → revisamos si el texto sugiere que está abierta
        if re.search(r"abierto|abierta|permanente|continuo", plazo_texto, re.IGNORECASE):
            return "abierta"
        return "sin_plazo"

    return "abierta" if plazo_fin >= today else "expirada"


def _extract_url_bases(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Busca el enlace a las bases de la convocatoria (normalmente un PDF)."""
    from urllib.parse import urljoin

    keywords = ["bases", "convocatoria", "normativa", "reglamento", "bases reguladoras"]

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text(strip=True).lower()
        # Prioriza enlaces a PDF con texto relevante
        if href.lower().endswith(".pdf") and any(kw in link_text for kw in keywords):
            return urljoin(base_url, href)

    # Fallback: cualquier PDF en la página
    for a_tag in soup.find_all("a", href=True):
        if a_tag["href"].lower().endswith(".pdf"):
            from urllib.parse import urljoin
            return urljoin(base_url, a_tag["href"])

    return None


def _compute_hash(titulo: str, descripcion: str, beneficiarios: str) -> str:
    """
    Calcula un hash MD5 del contenido principal.
    Si este hash cambia entre ejecuciones, la convocatoria se marca
    como 'actualizada' y se re-lanza el matching semántico.
    """
    content = f"{titulo}|{descripcion}|{beneficiarios}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


# ── Función principal ─────────────────────────────────────────────────────────

def parse_convocatoria(raw: dict) -> Optional[Convocatoria]:
    """
    Convierte un dict en crudo del scraper en un objeto Convocatoria limpio.
    Devuelve None si los datos son insuficientes para crear un registro útil.
    """
    try:
        soup = BeautifulSoup(raw["html_contenido"], "html.parser")
        full_text = raw["texto_contenido"]
        titulo = raw["titulo"]

        # Validación mínima: si no hay título ni texto, descartamos
        if not titulo or len(full_text) < 100:
            logger.warning(f"Convocatoria descartada por datos insuficientes: {raw['url']}")
            return None

        descripcion = _extract_description(soup)
        beneficiarios = _extract_beneficiarios(soup, full_text)
        plazo_texto, plazo_inicio, plazo_fin = _extract_plazo(full_text)
        estado = _determine_estado(plazo_fin, plazo_texto)
        url_bases = _extract_url_bases(soup, raw["url"])
        hash_contenido = _compute_hash(titulo, descripcion, beneficiarios)

        return Convocatoria(
            url=raw["url"],
            titulo=titulo,
            categoria=raw["categoria"],
            descripcion=descripcion,
            beneficiarios=beneficiarios,
            plazo_texto=plazo_texto,
            plazo_inicio=plazo_inicio,
            plazo_fin=plazo_fin,
            estado=estado,
            url_bases=url_bases,
            hash_contenido=hash_contenido,
        )

    except Exception as e:
        logger.error(f"Error parseando {raw.get('url', 'URL desconocida')}: {e}")
        return None


def parse_all(raw_list: list[dict]) -> list[Convocatoria]:
    """Parsea una lista de dicts crudos y devuelve solo los válidos."""
    results = []
    for raw in raw_list:
        convocatoria = parse_convocatoria(raw)
        if convocatoria:
            results.append(convocatoria)

    logger.info(f"Parsing completado: {len(results)}/{len(raw_list)} convocatorias válidas")
    return results