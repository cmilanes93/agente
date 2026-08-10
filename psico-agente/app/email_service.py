"""Envío del mail de aviso al profesional cuando se agenda un turno."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from app.config import Professional
from app.scheduling import Appointment, format_datetime_es

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """No se pudo enviar el mail de aviso."""


def _build_message(professional: Professional, appointment: Appointment) -> EmailMessage:
    from_email = os.environ["SMTP_USER"]
    when = format_datetime_es(appointment.start_at)

    msg = EmailMessage()
    msg["Subject"] = f"Nuevo turno agendado: {appointment.patient_name} - {when}"
    msg["From"] = from_email
    msg["To"] = professional.email
    msg.set_content(
        "Se agendó un nuevo turno a través del agente de atención.\n\n"
        f"Paciente: {appointment.patient_name}\n"
        f"Contacto del paciente: {appointment.patient_contact}\n"
        f"Fecha y hora: {when}\n"
        f"Duración: {appointment.duration_minutes} minutos\n"
        f"Motivo de consulta: {appointment.reason or 'No especificado'}\n"
    )
    return msg


def send_appointment_email(professional: Professional, appointment: Appointment) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not smtp_user or not smtp_password:
        message = "Faltan las variables de entorno SMTP_USER / SMTP_PASSWORD."
        logger.error("No se pudo enviar el mail del turno #%s: %s", appointment.id, message)
        raise EmailSendError(message)

    email_message = _build_message(professional, appointment)

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(email_message)
    except (smtplib.SMTPException, OSError) as exc:
        # OSError además de SMTPException: cubre fallos de red/DNS/timeout
        # al conectar, que smtplib no envuelve en una excepción propia.
        logger.exception(
            "No se pudo enviar el mail del turno #%s a %s (%s:%s)",
            appointment.id, professional.email, smtp_host, smtp_port,
        )
        raise EmailSendError(f"Error enviando el mail: {exc}") from exc
