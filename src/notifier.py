"""
Notificador de email vía Gmail SMTP.

Responsabilidad única: dado un grupo de matches pendientes,
construye un email HTML por perfil y lo envía.
Agrupa todos los matches de un mismo perfil en un solo email
para no saturar al usuario con múltiples correos.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from collections import defaultdict

from jinja2 import Template

from src.config import GMAIL_USER, GMAIL_APP_PASSWORD
from src.matcher import MatchResult
from src.database import save_match, mark_matches_notificados, get_connection

logger = logging.getLogger(__name__)


# ── Plantilla HTML del email ──────────────────────────────────────────────────

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <style>
    body {
      font-family: Arial, sans-serif;
      background-color: #f4f4f4;
      margin: 0;
      padding: 20px;
      color: #333;
    }
    .container {
      max-width: 650px;
      margin: auto;
      background: #ffffff;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .header {
      background-color: #1a5276;
      color: white;
      padding: 24px 30px;
    }
    .header h1 {
      margin: 0;
      font-size: 20px;
    }
    .header p {
      margin: 6px 0 0;
      font-size: 13px;
      opacity: 0.85;
    }
    .body {
      padding: 24px 30px;
    }
    .intro {
      font-size: 15px;
      margin-bottom: 20px;
      color: #555;
    }
    .card {
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      margin-bottom: 16px;
      overflow: hidden;
    }
    .card-header {
      background-color: #eaf0fb;
      padding: 12px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-header h3 {
      margin: 0;
      font-size: 15px;
      color: #1a5276;
    }
    .badge {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 12px;
      font-weight: bold;
      text-transform: uppercase;
    }
    .badge-nueva      { background: #d5f5e3; color: #1e8449; }
    .badge-actualizada { background: #fef9e7; color: #9a7d0a; }
    .badge-abierta    { background: #d5f5e3; color: #1e8449; }
    .badge-expirada   { background: #fadbd8; color: #922b21; }
    .badge-sin_plazo  { background: #eaeded; color: #555; }
    .card-body {
      padding: 12px 16px;
    }
    .card-body p {
      margin: 6px 0;
      font-size: 13px;
      color: #555;
      line-height: 1.5;
    }
    .card-body .label {
      font-weight: bold;
      color: #333;
    }
    .score-bar {
      display: inline-block;
      height: 6px;
      border-radius: 3px;
      background: #1a5276;
      vertical-align: middle;
      margin-right: 6px;
    }
    .cta {
      display: inline-block;
      margin-top: 10px;
      padding: 8px 16px;
      background-color: #1a5276;
      color: white;
      text-decoration: none;
      border-radius: 4px;
      font-size: 13px;
    }
    .footer {
      background-color: #f4f4f4;
      padding: 16px 30px;
      font-size: 11px;
      color: #999;
      text-align: center;
    }
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📋 Alertas Subvenciones Oviedo</h1>
    <p>Nuevas convocatorias relevantes para tu perfil · {{ fecha }}</p>
  </div>
  <div class="body">
    <p class="intro">
      Hola <strong>{{ nombre }}</strong>, hemos encontrado
      <strong>{{ matches|length }} convocatoria(s)</strong>
      que podrían interesarte:
    </p>

    {% for m in matches %}
    <div class="card">
      <div class="card-header">
        <h3>{{ m.convocatoria.titulo }}</h3>
        <div>
          <span class="badge badge-{{ m.motivo }}">{{ m.motivo }}</span>
          &nbsp;
          <span class="badge badge-{{ m.convocatoria.estado }}">
            {{ m.convocatoria.estado }}
          </span>
        </div>
      </div>
      <div class="card-body">
        {% if m.convocatoria.descripcion %}
        <p>
          <span class="label">Descripción:</span>
          {{ m.convocatoria.descripcion[:200] }}{% if m.convocatoria.descripcion|length > 200 %}...{% endif %}
        </p>
        {% endif %}
        {% if m.convocatoria.beneficiarios %}
        <p>
          <span class="label">Dirigido a:</span>
          {{ m.convocatoria.beneficiarios[:150] }}{% if m.convocatoria.beneficiarios|length > 150 %}...{% endif %}
        </p>
        {% endif %}
        {% if m.convocatoria.plazo_fin %}
        <p>
          <span class="label">Plazo fin:</span>
          {{ m.convocatoria.plazo_fin }}
        </p>
        {% endif %}
        <p>
          <span class="label">Relevancia:</span>
          <span class="score-bar" style="width:{{ (m.score * 100)|int }}px"></span>
          {{ "%.0f"|format(m.score * 100) }}%
        </p>
        <a href="{{ m.convocatoria.url }}" target="_blank"
           style="display:inline-block; margin-top:10px; padding:8px 16px;
                  background-color:#1a5276; color:#ffffff !important;
                  text-decoration:none; border-radius:4px; font-size:13px;
                  font-family:Arial,sans-serif; font-weight:bold;">
          Ver convocatoria →
        </a>
      </div>
    </div>
    {% endfor %}
  </div>
  <div class="footer">
    Este email fue generado automáticamente por Alertas Subvenciones Oviedo.<br>
    Datos extraídos de <a href="https://sede.oviedo.es">sede.oviedo.es</a>
    el {{ fecha }}.
  </div>
</div>
</body>
</html>
"""


# ── Funciones de envío ────────────────────────────────────────────────────────

def _build_email_html(nombre: str, matches: list[MatchResult]) -> str:
    """Renderiza la plantilla HTML con los datos del perfil y sus matches."""
    template = Template(EMAIL_TEMPLATE)
    return template.render(
        nombre=nombre,
        matches=matches,
        fecha=datetime.now().strftime("%d/%m/%Y"),
    )


def _send_email(destinatario: str, asunto: str, html_body: str) -> bool:
    """
    Envía un email HTML vía Gmail SMTP.
    Devuelve True si el envío fue exitoso, False si hubo error.
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.error(
            "Credenciales de Gmail no configuradas. "
            "Revisa GMAIL_USER y GMAIL_APP_PASSWORD en el .env"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"Alertas Subvenciones Oviedo <{GMAIL_USER}>"
    msg["To"]      = destinatario

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        logger.info(f"  ✓ Email enviado a: {destinatario}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Error de autenticación Gmail. "
            "Verifica que la App Password es correcta y que "
            "la verificación en dos pasos está activada."
        )
        return False
    except smtplib.SMTPException as e:
        logger.error(f"Error SMTP al enviar a {destinatario}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado al enviar email: {e}")
        return False


# ── Función principal ─────────────────────────────────────────────────────────

def run_notifier(matches: list[MatchResult]) -> dict:
    """
    Agrupa los matches por perfil, construye un email por perfil
    y los envía. Marca los matches como notificados en la DB.

    Devuelve un dict con estadísticas del proceso.
    """
    if not matches:
        logger.info("Sin matches que notificar")
        return {"emails_enviados": 0, "emails_fallidos": 0, "matches_notificados": 0}

    # ── Primero guardamos todos los matches en la DB ───────────────────────
    for m in matches:
        save_match(
            perfil_id=m.perfil_id,
            convocatoria_id=m.convocatoria_id,
            score=m.score,
            motivo=m.motivo,
        )

    # ── Agrupamos por email: una persona = un solo email ──────────────────
    por_email: dict[str, list[MatchResult]] = defaultdict(list)
    for m in matches:
        por_email[m.perfil_email].append(m)

    enviados  = 0
    fallidos  = 0
    match_ids_notificados = []

    for email, perfil_matches in por_email.items():
        # Ordenamos por score descendente dentro de cada email
        perfil_matches.sort(key=lambda x: x.score, reverse=True)
        nombre = perfil_matches[0].perfil_nombre

        n_nuevas      = sum(1 for m in perfil_matches if m.motivo == "nueva")
        n_actualizadas = sum(1 for m in perfil_matches if m.motivo == "actualizada")

        partes_asunto = []
        if n_nuevas:
            partes_asunto.append(f"{n_nuevas} nueva(s)")
        if n_actualizadas:
            partes_asunto.append(f"{n_actualizadas} actualizada(s)")

        asunto = f"[Oviedo Ayudas] {', '.join(partes_asunto)} convocatoria(s) para ti"

        logger.info(
            f"Enviando email a {email} "
            f"({len(perfil_matches)} matches)"
        )

        html = _build_email_html(nombre, perfil_matches)
        success = _send_email(email, asunto, html)

        if success:
            enviados += 1
            # Recuperamos los IDs de los matches guardados para marcarlos
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT m.id FROM matches m
                    JOIN perfiles p ON m.perfil_id = p.id
                    WHERE p.email = ? AND m.notificado = 0
                """, (email,)).fetchall()
                match_ids_notificados.extend([r["id"] for r in rows])
        else:
            fallidos += 1

    # ── Marcamos todos los matches enviados como notificados ──────────────
    if match_ids_notificados:
        mark_matches_notificados(match_ids_notificados)

    stats = {
        "emails_enviados":     enviados,
        "emails_fallidos":     fallidos,
        "matches_notificados": len(match_ids_notificados),
    }
    logger.info(
        f"Notificador completado: {enviados} emails enviados, "
        f"{fallidos} fallidos, {len(match_ids_notificados)} matches marcados"
    )
    return stats