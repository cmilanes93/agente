"""Envío del mail de aviso al profesional cuando se agenda un turno.

Usa la API HTTP de Resend (https://resend.com) en vez de SMTP directo:
varios hostings (Render incluido) bloquean el tráfico saliente por los
puertos SMTP (465/587) como medida anti-spam, lo que da "Network is
unreachable" o "timed out" sin relación alguna con las credenciales.
Resend funciona sobre HTTPS (puerto 443), que no se bloquea.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from app.config import Professional
from app.scheduling import Appointment, format_datetime_es

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT_SECONDS = 15


class EmailSendError(Exception):
    """No se pudo enviar el mail de aviso."""


def _build_payload(professional: Professional, appointment: Appointment, from_address: str) -> dict:
    when = format_datetime_es(appointment.start_at)

    body = (
        "Se agendó un nuevo turno a través del agente de atención.\n\n"
        f"Paciente: {appointment.patient_name}\n"
        f"Contacto del paciente: {appointment.patient_contact}\n"
        f"Fecha y hora: {when}\n"
        f"Duración: {appointment.duration_minutes} minutos\n"
        f"Motivo de consulta: {appointment.reason or 'No especificado'}\n"
    )

    return {
        "from": from_address,
        "to": [professional.email],
        "subject": f"Nuevo turno agendado: {appointment.patient_name} - {when}",
        "text": body,
    }


def send_appointment_email(professional: Professional, appointment: Appointment) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    from_address = os.environ.get("RESEND_FROM")

    if not api_key or not from_address:
        # RESEND_FROM tiene que ser una dirección de un dominio verificado
        # en Resend (Resend no tiene remitente de pruebas sin dominio
        # propio) — ver README, sección "Crear la API key de Resend".
        missing = "RESEND_API_KEY" if not api_key else "RESEND_FROM"
        message = f"Falta la variable de entorno {missing}."
        logger.error("No se pudo enviar el mail del turno #%s: %s", appointment.id, message)
        raise EmailSendError(message)

    payload = _build_payload(professional, appointment, from_address)
    request = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Sin un User-Agent "normal", Cloudflare (delante de la API de
            # Resend) banea el default de urllib (Python-urllib/x.y) como
            # bot y devuelve HTTP 403 "error code: 1010" antes de que la
            # request llegue a Resend.
            "User-Agent": "psico-agente/1.0 (+https://github.com/cmilanes93/agente)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.exception(
            "Resend rechazó el mail del turno #%s (HTTP %s): %s", appointment.id, exc.code, detail
        )
        raise EmailSendError(f"Resend devolvió {exc.code}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        logger.exception("No se pudo conectar con Resend para el turno #%s", appointment.id)
        raise EmailSendError(f"Error de red enviando el mail: {exc}") from exc
