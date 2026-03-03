"""
Script de prueba para el notificador de email.
Envía un email real de prueba a la dirección que configures.
Ejecutar con: python -m scripts.test_notifier
"""

import logging
from datetime import date
from src.notifier import _build_email_html, _send_email
from src.matcher import MatchResult
from src.parser import Convocatoria

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ── Cambia esta dirección por la tuya para recibir el email de prueba ─────────
EMAIL_DESTINO = "b.vargas0711@gmail.com"


def make_fake_match(titulo, descripcion, score, motivo="nueva", estado="abierta"):
    """Crea un MatchResult falso para la prueba visual del email."""
    conv = Convocatoria(
        url=f"https://sede.oviedo.es/tramites/subvenciones/{titulo.lower().replace(' ', '-')}",
        titulo=titulo,
        categoria="subvenciones",
        descripcion=descripcion,
        beneficiarios="Asociaciones sin ánimo de lucro del municipio de Oviedo.",
        plazo_texto="Plazo hasta el 30 de junio de 2026",
        plazo_inicio=None,
        plazo_fin=date(2026, 6, 30),
        estado=estado,
        url_bases=None,
        hash_contenido="abc123",
    )
    return MatchResult(
        perfil_id=1,
        perfil_nombre="Usuario de Prueba",
        perfil_email=EMAIL_DESTINO,
        convocatoria_id=1,
        convocatoria=conv,
        score=score,
        motivo=motivo,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("TEST: Notificador de Email — Fase 4")
    print("=" * 60)

    # Creamos matches de prueba variados
    matches_prueba = [
        make_fake_match(
            titulo="Subvenciones para proyectos de participación ciudadana",
            descripcion="Subvenciones para entidades sin ánimo de lucro destinadas "
                        "a proyectos de participación ciudadana en el concejo de Oviedo.",
            score=0.821,
            motivo="nueva",
            estado="abierta",
        ),
        make_fake_match(
            titulo="Premio Proyecto de Voluntariado",
            descripcion="Convocatoria del Premio al mejor proyecto de voluntariado "
                        "desarrollado por entidades del municipio de Oviedo.",
            score=0.756,
            motivo="nueva",
            estado="abierta",
        ),
        make_fake_match(
            titulo="Subvenciones Cooperación al Desarrollo",
            descripcion="Ayudas para proyectos de cooperación internacional "
                        "al desarrollo promovidos por entidades locales.",
            score=0.612,
            motivo="actualizada",
            estado="expirada",
        ),
    ]

    print(f"\n[1/2] Construyendo email HTML de prueba...")
    html = _build_email_html("Usuario de Prueba", matches_prueba)
    
    # Guardamos el HTML localmente para inspección visual en el navegador
    with open("data/email_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  → Email guardado en data/email_preview.html")
    print(f"  → Ábrelo en tu navegador para ver el diseño antes de enviar")

    print(f"\n[2/2] Enviando email de prueba a: {EMAIL_DESTINO}")
    respuesta = input("  ¿Enviar el email ahora? (s/n): ").strip().lower()

    if respuesta == "s":
        asunto = "[Oviedo Ayudas] TEST — 3 convocatorias relevantes para ti"
        success = _send_email(EMAIL_DESTINO, asunto, html)
        if success:
            print("\n  ✓ Email enviado correctamente. Revisa tu bandeja de entrada.")
        else:
            print("\n  ✗ Error al enviar. Revisa el log de arriba para más detalles.")
    else:
        print("\n  → Envío cancelado. Puedes revisar el HTML en data/email_preview.html")

    print("=" * 60)