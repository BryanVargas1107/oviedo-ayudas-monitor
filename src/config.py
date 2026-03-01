"""
Configuración central del proyecto.
Todas las constantes y parámetros están aquí para no tener
"números mágicos" dispersos por el código.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Scraper ───────────────────────────────────────────────────────────────────

# URLs de entrada al catálogo de subvenciones de la sede electrónica
SEED_URLS = [
    "https://sede.oviedo.es/tramites/subvenciones",
    "https://sede.oviedo.es/tramites/educacion-formacion-y-empleo",
    "https://sede.oviedo.es/tramites/entidades-ciudadanas.-asociaciones",
]

BASE_URL = "https://sede.oviedo.es"

# Segundos de espera entre peticiones HTTP (respeta el servidor)
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY_SECONDS", 1.0))

# Timeout en segundos para cada petición HTTP
REQUEST_TIMEOUT = 15

# User-Agent que nos identifica correctamente ante el servidor
USER_AGENT = (
    "Mozilla/5.0 (compatible; OviedoAyudasMonitor/1.0; "
    "portfolio project; contact: github.com/TU_USUARIO)"
)

# ── Matching semántico ────────────────────────────────────────────────────────

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE_DIR = ".model_cache"
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.45))

# ── Base de datos ─────────────────────────────────────────────────────────────

DB_PATH = "data/convocatorias.db"

# ── Gmail SMTP ────────────────────────────────────────────────────────────────

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")