"""
Capa de acceso a la base de datos SQLite.

Responsabilidad única: crear las tablas, guardar convocatorias
con lógica de upsert (insertar si es nueva, actualizar si cambió),
y devolver las novedades que necesitan matching semántico.
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from src.config import DB_PATH
from src.parser import Convocatoria

logger = logging.getLogger(__name__)


# ── Gestión de conexión ───────────────────────────────────────────────────────

@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager para conexiones a SQLite.
    Garantiza que la conexión se cierra aunque haya un error.
    Uso: with get_connection() as conn:
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    conn.execute("PRAGMA journal_mode=WAL")  # Mejor rendimiento en lecturas
    conn.execute("PRAGMA foreign_keys=ON")   # Activa integridad referencial
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Creación de tablas ────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Crea las tablas si no existen todavía.
    Es seguro llamar a esta función en cada ejecución del pipeline
    porque usa CREATE TABLE IF NOT EXISTS.
    """
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS convocatorias (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                url             TEXT    UNIQUE NOT NULL,
                titulo          TEXT    NOT NULL,
                categoria       TEXT,
                descripcion     TEXT,
                beneficiarios   TEXT,
                plazo_texto     TEXT,
                plazo_inicio    TEXT,
                plazo_fin       TEXT,
                estado          TEXT    DEFAULT 'sin_plazo',
                url_bases       TEXT,
                hash_contenido  TEXT    NOT NULL,
                fecha_primera   TEXT    NOT NULL,
                fecha_actualiz  TEXT    NOT NULL,
                es_nueva        INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS perfiles (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre              TEXT    NOT NULL,
                email               TEXT    NOT NULL,
                tipo_beneficiario   TEXT,
                descripcion_libre   TEXT,
                activo              INTEGER DEFAULT 1,
                fecha_creacion      TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS matches (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                perfil_id        INTEGER NOT NULL REFERENCES perfiles(id),
                convocatoria_id  INTEGER NOT NULL REFERENCES convocatorias(id),
                score_similitud  REAL    NOT NULL,
                motivo           TEXT    NOT NULL,
                notificado       INTEGER DEFAULT 0,
                fecha_match      TEXT    NOT NULL,
                fecha_notif      TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_convocatorias_url
                ON convocatorias(url);
            CREATE INDEX IF NOT EXISTS idx_convocatorias_estado
                ON convocatorias(estado);
            CREATE INDEX IF NOT EXISTS idx_matches_notificado
                ON matches(notificado);
        """)
    logger.info("Base de datos inicializada correctamente")


# ── Lógica de upsert ──────────────────────────────────────────────────────────

def upsert_convocatoria(
    conn: sqlite3.Connection,
    conv: Convocatoria,
) -> tuple[int, str] | None:
    """
    Inserta o actualiza una convocatoria en la DB.

    Lógica:
    - URL no existe → INSERT, motivo='nueva'
    - URL existe + hash igual → nada (sin cambios)
    - URL existe + hash distinto → UPDATE, motivo='actualizada'

    Devuelve (id, motivo) si hay novedad que procesar,
    o None si no hay ningún cambio.
    """
    now = datetime.now().isoformat()

    # Buscamos si la URL ya existe
    row = conn.execute(
        "SELECT id, hash_contenido FROM convocatorias WHERE url = ?",
        (conv.url,)
    ).fetchone()

    if row is None:
        # ── CASO 1: Convocatoria nueva ──
        cursor = conn.execute("""
            INSERT INTO convocatorias (
                url, titulo, categoria, descripcion, beneficiarios,
                plazo_texto, plazo_inicio, plazo_fin, estado, url_bases,
                hash_contenido, fecha_primera, fecha_actualiz, es_nueva
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            conv.url,
            conv.titulo,
            conv.categoria,
            conv.descripcion,
            conv.beneficiarios,
            conv.plazo_texto,
            conv.plazo_inicio.isoformat() if conv.plazo_inicio else None,
            conv.plazo_fin.isoformat() if conv.plazo_fin else None,
            conv.estado,
            conv.url_bases,
            conv.hash_contenido,
            now,
            now,
        ))
        logger.info(f"  [NUEVA] {conv.titulo[:55]}")
        return (cursor.lastrowid, "nueva")

    elif row["hash_contenido"] != conv.hash_contenido:
        # ── CASO 2: Convocatoria actualizada ──
        conn.execute("""
            UPDATE convocatorias SET
                titulo         = ?,
                categoria      = ?,
                descripcion    = ?,
                beneficiarios  = ?,
                plazo_texto    = ?,
                plazo_inicio   = ?,
                plazo_fin      = ?,
                estado         = ?,
                url_bases      = ?,
                hash_contenido = ?,
                fecha_actualiz = ?,
                es_nueva       = 0
            WHERE url = ?
        """, (
            conv.titulo,
            conv.categoria,
            conv.descripcion,
            conv.beneficiarios,
            conv.plazo_texto,
            conv.plazo_inicio.isoformat() if conv.plazo_inicio else None,
            conv.plazo_fin.isoformat() if conv.plazo_fin else None,
            conv.estado,
            conv.url_bases,
            conv.hash_contenido,
            now,
            conv.url,
        ))
        logger.info(f"  [ACTUALIZADA] {conv.titulo[:50]}")
        return (row["id"], "actualizada")

    else:
        # ── CASO 3: Sin cambios ──
        logger.debug(f"  [SIN CAMBIOS] {conv.titulo[:55]}")
        return None


def upsert_all(convocatorias: list[Convocatoria]) -> list[tuple[int, str, Convocatoria]]:
    """
    Procesa todas las convocatorias parseadas contra la DB.

    Devuelve lista de (id, motivo, convocatoria) solo para
    las que son nuevas o han cambiado — estas son las que
    necesitan pasar por el matcher semántico en la Fase 3.
    """
    novedades = []
    sin_cambios = 0

    with get_connection() as conn:
        for conv in convocatorias:
            result = upsert_convocatoria(conn, conv)
            if result is not None:
                conv_id, motivo = result
                novedades.append((conv_id, motivo, conv))
            else:
                sin_cambios += 1

    logger.info(
        f"Upsert completado: {len(novedades)} novedades "
        f"({sum(1 for _, m, _ in novedades if m == 'nueva')} nuevas, "
        f"{sum(1 for _, m, _ in novedades if m == 'actualizada')} actualizadas), "
        f"{sin_cambios} sin cambios"
    )
    return novedades


# ── Consultas de apoyo ────────────────────────────────────────────────────────

def get_perfiles_activos() -> list[sqlite3.Row]:
    """Devuelve todos los perfiles con activo=1."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM perfiles WHERE activo = 1"
        ).fetchall()


def save_match(
    perfil_id: int,
    convocatoria_id: int,
    score: float,
    motivo: str,
) -> None:
    """Guarda un match semántico en la tabla matches."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO matches
                (perfil_id, convocatoria_id, score_similitud, motivo, fecha_match)
            VALUES (?, ?, ?, ?, ?)
        """, (perfil_id, convocatoria_id, score, motivo, datetime.now().isoformat()))


def get_matches_pendientes() -> list[sqlite3.Row]:
    """
    Devuelve los matches que aún no han sido notificados por email,
    con toda la info de perfil y convocatoria en una sola consulta.
    """
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                m.id            AS match_id,
                m.score_similitud,
                m.motivo,
                m.fecha_match,
                p.nombre        AS perfil_nombre,
                p.email         AS perfil_email,
                c.titulo        AS conv_titulo,
                c.url           AS conv_url,
                c.categoria     AS conv_categoria,
                c.descripcion   AS conv_descripcion,
                c.estado        AS conv_estado,
                c.plazo_fin     AS conv_plazo_fin
            FROM matches m
            JOIN perfiles       p ON m.perfil_id       = p.id
            JOIN convocatorias  c ON m.convocatoria_id = c.id
            WHERE m.notificado = 0
            ORDER BY p.email, m.score_similitud DESC
        """).fetchall()


def mark_matches_notificados(match_ids: list[int]) -> None:
    """Marca una lista de matches como notificados."""
    with get_connection() as conn:
        conn.executemany(
            "UPDATE matches SET notificado = 1, fecha_notif = ? WHERE id = ?",
            [(datetime.now().isoformat(), mid) for mid in match_ids]
        )


def get_stats() -> dict:
    """Estadísticas rápidas para mostrar en el dashboard Streamlit."""
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM convocatorias"
        ).fetchone()[0]
        abiertas = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE estado = 'abierta'"
        ).fetchone()[0]
        expiradas = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE estado = 'expirada'"
        ).fetchone()[0]
        sin_plazo = conn.execute(
            "SELECT COUNT(*) FROM convocatorias WHERE estado = 'sin_plazo'"
        ).fetchone()[0]
        perfiles = conn.execute(
            "SELECT COUNT(*) FROM perfiles WHERE activo = 1"
        ).fetchone()[0]
        matches_pendientes = conn.execute(
            "SELECT COUNT(*) FROM matches WHERE notificado = 0"
        ).fetchone()[0]

    return {
        "total_convocatorias": total,
        "abiertas": abiertas,
        "expiradas": expiradas,
        "sin_plazo": sin_plazo,
        "perfiles_activos": perfiles,
        "matches_pendientes": matches_pendientes,
    }