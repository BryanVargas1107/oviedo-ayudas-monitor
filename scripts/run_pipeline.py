"""
Pipeline principal del sistema Alertas Subvenciones Oviedo.

Orquesta las 4 fases en orden:
  1. Scraper  → descarga convocatorias de la sede electrónica
  2. Parser   → limpia y estructura los datos
  3. Database → upsert con detección de cambios por hash
  4. Matcher  → similitud semántica contra perfiles activos
  5. Notifier → envío de emails agrupados por perfil

Este script es el punto de entrada para GitHub Actions (cron diario)
y también puede ejecutarse manualmente en local.

Uso:
    python -m scripts.run_pipeline
    python -m scripts.run_pipeline --dry-run   (sin enviar emails)
"""

import sys
import logging
import argparse
from datetime import datetime

from src.scraper  import run_scraper
from src.parser   import parse_all
from src.database import init_db, upsert_all, get_perfiles_activos, get_stats
from src.matcher  import run_matching
from src.notifier import run_notifier

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("pipeline")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> dict:
    """
    Ejecuta el pipeline completo.

    Parámetros:
        dry_run: si True, ejecuta todo excepto el envío de emails.
                 Útil para probar sin notificar.

    Devuelve un dict con estadísticas de la ejecución.
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("PIPELINE INICIADO")
    if dry_run:
        logger.info("MODO DRY-RUN: los emails NO se enviarán")
    logger.info("=" * 60)

    stats = {
        "inicio":             start_time.isoformat(),
        "dry_run":            dry_run,
        "convocatorias_raw":  0,
        "convocatorias_ok":   0,
        "novedades":          0,
        "nuevas":             0,
        "actualizadas":       0,
        "perfiles_activos":   0,
        "matches":            0,
        "emails_enviados":    0,
        "emails_fallidos":    0,
        "duracion_segundos":  0,
        "estado":             "ok",
        "error":              None,
    }

    try:
        # ── Fase 1: Base de datos ──────────────────────────────────────────
        logger.info("\n[1/5] Inicializando base de datos...")
        init_db()

        # ── Fase 2: Scraping ───────────────────────────────────────────────
        logger.info("\n[2/5] Scraping de la sede electrónica...")
        raw_data = run_scraper()
        stats["convocatorias_raw"] = len(raw_data)

        if not raw_data:
            logger.warning("El scraper no devolvió ningún resultado. Abortando.")
            stats["estado"] = "warning"
            return stats

        # ── Fase 3: Parsing ────────────────────────────────────────────────
        logger.info("\n[3/5] Parseando convocatorias...")
        convocatorias = parse_all(raw_data)
        stats["convocatorias_ok"] = len(convocatorias)

        # ── Fase 4: Upsert en DB ───────────────────────────────────────────
        logger.info("\n[4/5] Actualizando base de datos...")
        novedades = upsert_all(convocatorias)
        stats["novedades"]    = len(novedades)
        stats["nuevas"]       = sum(1 for _, m, _ in novedades if m == "nueva")
        stats["actualizadas"] = sum(1 for _, m, _ in novedades if m == "actualizada")

        if not novedades:
            logger.info("Sin novedades hoy. No hay nada que notificar.")
            return stats

        # ── Fase 5: Matching semántico ─────────────────────────────────────
        logger.info("\n[5/5] Ejecutando matching semántico...")
        perfiles = get_perfiles_activos()
        stats["perfiles_activos"] = len(perfiles)

        if not perfiles:
            logger.warning(
                "No hay perfiles activos en la DB. "
                "Añade perfiles desde la app Streamlit."
            )
            return stats

        matches = run_matching(novedades, perfiles)
        stats["matches"] = len(matches)

        # ── Fase 6: Notificaciones ─────────────────────────────────────────
        if matches and not dry_run:
            notif_stats = run_notifier(matches)
            stats["emails_enviados"] = notif_stats["emails_enviados"]
            stats["emails_fallidos"] = notif_stats["emails_fallidos"]
        elif dry_run and matches:
            logger.info(
                f"DRY-RUN: se habrían enviado emails a "
                f"{len(set(m.perfil_email for m in matches))} perfil(es)"
            )

    except Exception as e:
        logger.error(f"Error crítico en el pipeline: {e}", exc_info=True)
        stats["estado"] = "error"
        stats["error"]  = str(e)

    finally:
        duracion = (datetime.now() - start_time).total_seconds()
        stats["duracion_segundos"] = round(duracion, 1)

        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN DEL PIPELINE")
        logger.info("=" * 60)
        logger.info(f"  Estado:            {stats['estado']}")
        logger.info(f"  Duración:          {stats['duracion_segundos']}s")
        logger.info(f"  Convocatorias:     {stats['convocatorias_ok']}/{stats['convocatorias_raw']}")
        logger.info(f"  Novedades:         {stats['novedades']} ({stats['nuevas']} nuevas, {stats['actualizadas']} actualizadas)")
        logger.info(f"  Perfiles activos:  {stats['perfiles_activos']}")
        logger.info(f"  Matches:           {stats['matches']}")
        logger.info(f"  Emails enviados:   {stats['emails_enviados']}")
        if stats['emails_fallidos']:
            logger.warning(f"  Emails fallidos:   {stats['emails_fallidos']}")
        logger.info("=" * 60)

    return stats


# ── Punto de entrada ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline diario de Alertas Subvenciones Oviedo"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta el pipeline sin enviar emails",
    )
    args = parser.parse_args()

    resultado = run(dry_run=args.dry_run)

    # Código de salida para GitHub Actions:
    # 0 = éxito, 1 = error crítico
    sys.exit(0 if resultado["estado"] in ("ok", "warning") else 1)