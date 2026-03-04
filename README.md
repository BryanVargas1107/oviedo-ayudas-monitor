# 📋 Alertas Subvenciones Oviedo

Monitor diario automatizado de ayudas, becas y subvenciones publicadas en la
[sede electrónica del Ayuntamiento de Oviedo](https://sede.oviedo.es).

El sistema extrae convocatorias cada mañana, las compara semánticamente con
perfiles de usuario definidos en una interfaz web, y envía notificaciones por
email cuando detecta convocatorias relevantes.

---

## 🎯 ¿Qué problema resuelve?

Las convocatorias de subvenciones municipales están dispersas en múltiples
categorías de la sede electrónica y se publican sin avisos. Familias, autónomos,
asociaciones y clubes deportivos pierden oportunidades por no estar al tanto.

Este sistema monitoriza la sede diariamente y avisa automáticamente cuando
aparece algo relevante para cada perfil.

---

## ⚙️ Arquitectura del sistema
```
GitHub Actions (cron 08:00 UTC)
        │
        ▼
┌─────────────────────────────────────────────────┐
│                   PIPELINE                      │
│                                                 │
│  1. Scraper    → requests + BeautifulSoup       │
│     sede.oviedo.es (encoding fix ISO-8859-1)    │
│                                                 │
│  2. Parser     → extracción de fechas, estado   │
│     MD5 hash para detectar cambios              │
│                                                 │
│  3. Database   → SQLite upsert logic            │
│     nueva | actualizada | sin cambios           │
│                                                 │
│  4. Matcher    → sentence-transformers          │
│     paraphrase-multilingual-MiniLM-L12-v2       │
│     cosine similarity > 0.45                    │
│                                                 │
│  5. Notifier   → Gmail SMTP                     │
│     email HTML agrupado por perfil              │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│              STREAMLIT DASHBOARD                │
│  · Mi Perfil    → gestión de perfiles           │
│  · Convocatorias → explorador con filtros       │
│  · Mis Alertas  → historial de matches          │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ Stack tecnológico

| Capa | Tecnología | Motivo de elección |
|------|-----------|-------------------|
| Scraping | `requests` + `BeautifulSoup` | Sede estática, sin JS dinámico |
| Matching | `sentence-transformers` | Similitud semántica multilingüe |
| Modelo NLP | `paraphrase-multilingual-MiniLM-L12-v2` | Ligero, preciso en español |
| Base de datos | `SQLite` | Sin servidor, portable, suficiente para el volumen |
| Interfaz | `Streamlit` | Prototipado rápido de dashboards de datos |
| Notificaciones | `Gmail SMTP` | Integración directa, sin servicios externos |
| Automatización | `GitHub Actions` | CI/CD gratuito, cron nativo |
| Lenguaje | `Python 3.11` | Ecosistema data science |

---

## 📁 Estructura del proyecto
```
oviedo-ayudas-monitor/
├── .github/workflows/
│   └── daily_monitor.yml     # Cron job diario
├── src/
│   ├── config.py             # Configuración central
│   ├── scraper.py            # Extracción HTTP + BeautifulSoup
│   ├── parser.py             # Normalización y detección de plazos
│   ├── database.py           # SQLite + lógica de upsert
│   ├── matcher.py            # Motor de matching semántico
│   └── notifier.py           # Envío de emails HTML
├── streamlit_app/
│   ├── app.py                # Dashboard principal
│   └── pages/
│       ├── 1_Mi_Perfil.py    # Gestión de perfiles
│       ├── 2_Convocatorias.py # Explorador de convocatorias
│       └── 3_Mis_Alertas.py  # Historial de alertas
├── scripts/
│   └── run_pipeline.py       # Orquestador del pipeline
├── .env.example              # Variables de entorno necesarias
└── requirements.txt
```

---

## 🔍 Decisiones técnicas destacadas

**Encoding ISO-8859-1 → UTF-8**
La sede electrónica declara `charset=ISO-8859-1` en algunas cabeceras HTTP
pero sirve contenido UTF-8. La solución fue decodificar desde bytes crudos
usando `apparent_encoding` de la librería `chardet`, evitando la decodificación
automática de `requests`.

**Detección de cambios por hash MD5**
En lugar de descargar y recomparar todo el texto en cada ejecución, se calcula
un hash MD5 de `título + descripción + beneficiarios`. Si el hash cambia entre
ejecuciones, la convocatoria se marca como `actualizada` y vuelve a pasar por
el matcher semántico.

**Matching semántico en batch**
Los embeddings de todos los perfiles y todas las convocatorias se calculan en
un solo batch, generando una matriz de similitud coseno de dimensión
`(n_perfiles × n_convocatorias)`. Esto es significativamente más eficiente que
calcular cada par individualmente.

**Caché del modelo en GitHub Actions**
El modelo `paraphrase-multilingual-MiniLM-L12-v2` pesa ~120MB. Se cachea entre
ejecuciones de GitHub Actions usando `actions/cache`, reduciendo el tiempo de
ejecución diario de ~3 minutos a ~40 segundos tras la primera descarga.

---

## 🚀 Instalación y uso local

### Requisitos
- Python 3.11+
- Git

### Setup
```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/oviedo-ayudas-monitor.git
cd oviedo-ayudas-monitor

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales de Gmail
```

### Ejecutar el pipeline
```bash
# Prueba sin enviar emails
python -m scripts.run_pipeline --dry-run

# Ejecución completa
python -m scripts.run_pipeline
```

### Lanzar la interfaz Streamlit
```bash
cd streamlit_app
streamlit run app.py
```

---

## 🔐 Variables de entorno

Copia `.env.example` como `.env` y rellena los valores:
```env
GMAIL_USER=tu_cuenta@gmail.com
GMAIL_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx  # App Password de 16 caracteres
SIMILARITY_THRESHOLD=0.45               # Umbral de similitud semántica (0-1)
REQUEST_DELAY_SECONDS=1                 # Pausa entre peticiones HTTP
```

Para obtener una App Password de Gmail:
1. Activa la verificación en dos pasos en tu cuenta Google
2. Ve a Seguridad → Contraseñas de aplicaciones
3. Crea una contraseña para "oviedo-ayudas-monitor"

---

## 📊 Resultados

- **~30 convocatorias** monitorizadas diariamente
- **4 categorías** de beneficiarios soportadas
- **Detección automática** de convocatorias nuevas y actualizadas
- **Matching semántico** con precisión >0.45 de similitud coseno

---

## 🗂️ Fases de desarrollo

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Scraper + Parser | ✅ |
| 2 | Base de datos SQLite | ✅ |
| 3 | Matching semántico | ✅ |
| 4 | Notificador email | ✅ |
| 5 | Pipeline completo | ✅ |
| 6 | Interfaz Streamlit | ✅ |
| 7 | GitHub Actions + README | ✅ |

---

## 👨‍💻 Autor

Desarrollado como proyecto de portfolio por **Bryan Vargas Sanchez**
como parte de mi formación en Ciencia de Datos.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-blue?logo=linkedin)](https://linkedin.com/in/bryan-vargas-sanchez-3a79a92a0/)
[![GitHub](https://img.shields.io/badge/GitHub-black?logo=github)](https://github.com/BryanVargas1107)

---

*Proyecto desarrollado con fines educativos y de portfolio.*
*Los datos se extraen de fuentes públicas de la administración local.*
