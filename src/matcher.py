"""
Motor de matching semántico.

Responsabilidad única: dado un perfil de usuario y una lista
de convocatorias nuevas o actualizadas, calcula la similitud
semántica entre ambos usando sentence-transformers y devuelve
los pares (perfil, convocatoria) que superan el umbral.

El modelo se carga UNA sola vez por ejecución y se cachea
en disco para no descargarlo en cada run de GitHub Actions.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import sqlite3
from sentence_transformers import SentenceTransformer, util

from src.config import MODEL_NAME, MODEL_CACHE_DIR, SIMILARITY_THRESHOLD
from src.parser import Convocatoria

logger = logging.getLogger(__name__)


# ── Modelo (singleton por ejecución) ─────────────────────────────────────────

_model: Optional[SentenceTransformer] = None

def _get_model() -> SentenceTransformer:
    """
    Carga el modelo la primera vez y lo reutiliza en llamadas posteriores.
    El parámetro cache_folder evita descargarlo en cada ejecución
    de GitHub Actions (se guarda en .model_cache/).
    """
    global _model
    if _model is None:
        logger.info(f"Cargando modelo: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME, cache_folder=MODEL_CACHE_DIR)
        logger.info("Modelo cargado correctamente")
    return _model


# ── Construcción de textos para embedding ────────────────────────────────────

def _build_convocatoria_text(conv: Convocatoria) -> str:
    """
    Construye el texto que representa a la convocatoria para el embedding.
    Concatenamos título + descripción + beneficiarios porque juntos
    dan el mejor contexto semántico al modelo.
    """
    partes = [conv.titulo]
    if conv.descripcion:
        partes.append(conv.descripcion)
    if conv.beneficiarios:
        partes.append(conv.beneficiarios)
    return " | ".join(partes)


def _build_perfil_text(perfil: sqlite3.Row) -> str:
    """
    Construye el texto que representa al perfil para el embedding.
    Combinamos el tipo de beneficiario con la descripción libre
    para enriquecer el contexto semántico.
    """
    tipo_map = {
        "fisica":      "Soy una persona física buscando ayudas y subvenciones.",
        "autonomo":    "Soy autónomo o tengo una pequeña empresa buscando subvenciones.",
        "asociacion":  "Somos una asociación o entidad sin ánimo de lucro.",
        "deportista":  "Soy deportista o represento un club deportivo.",
    }
    tipo_texto = tipo_map.get(perfil["tipo_beneficiario"], "")
    descripcion = perfil["descripcion_libre"] or ""
    return f"{tipo_texto} {descripcion}".strip()


# ── Dataclass de resultado ────────────────────────────────────────────────────

@dataclass
class MatchResult:
    perfil_id: int
    perfil_nombre: str
    perfil_email: str
    convocatoria_id: int
    convocatoria: Convocatoria
    score: float
    motivo: str  # 'nueva' | 'actualizada'


# ── Función principal ─────────────────────────────────────────────────────────

def run_matching(
    novedades: list[tuple[int, str, Convocatoria]],
    perfiles: list[sqlite3.Row],
) -> list[MatchResult]:
    """
    Calcula similitud semántica entre todas las novedades y todos los perfiles.

    Parámetros:
        novedades: lista de (conv_id, motivo, convocatoria) del upsert
        perfiles:  lista de rows de la tabla perfiles

    Devuelve lista de MatchResult que superan SIMILARITY_THRESHOLD.
    """
    if not novedades:
        logger.info("Sin novedades que procesar en el matcher")
        return []

    if not perfiles:
        logger.info("Sin perfiles activos en la DB — no hay matching que hacer")
        return []

    model = _get_model()

    # ── Preparamos los textos ──────────────────────────────────────────────
    conv_ids    = [conv_id  for conv_id, _, _    in novedades]
    conv_motivos = [motivo  for _, motivo, _     in novedades]
    convs       = [conv     for _, _, conv       in novedades]

    conv_texts  = [_build_convocatoria_text(c) for c in convs]
    perfil_texts = [_build_perfil_text(p)      for p in perfiles]

    logger.info(
        f"Calculando embeddings: "
        f"{len(conv_texts)} convocatorias × {len(perfil_texts)} perfiles"
    )

    # ── Calculamos embeddings en batch (más eficiente que uno a uno) ───────
    conv_embeddings   = model.encode(conv_texts,   convert_to_tensor=True, show_progress_bar=False)
    perfil_embeddings = model.encode(perfil_texts, convert_to_tensor=True, show_progress_bar=False)

    # ── Matriz de similitud: shape (n_perfiles, n_convocatorias) ───────────
    similarity_matrix = util.cos_sim(perfil_embeddings, conv_embeddings)

    # ── Filtramos por umbral y construimos resultados ──────────────────────
    results = []
    for p_idx, perfil in enumerate(perfiles):
        for c_idx, conv in enumerate(convs):
            score = float(similarity_matrix[p_idx][c_idx])

            if score >= SIMILARITY_THRESHOLD:
                results.append(MatchResult(
                    perfil_id=perfil["id"],
                    perfil_nombre=perfil["nombre"],
                    perfil_email=perfil["email"],
                    convocatoria_id=conv_ids[c_idx],
                    convocatoria=conv,
                    score=score,
                    motivo=conv_motivos[c_idx],
                ))
                logger.info(
                    f"  ✓ MATCH [{score:.3f}] "
                    f"{perfil['nombre']} ↔ {conv.titulo[:45]}"
                )

    logger.info(
        f"Matching completado: {len(results)} matches "
        f"(umbral={SIMILARITY_THRESHOLD})"
    )
    return results