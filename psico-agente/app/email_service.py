"""Envío del mail de aviso al profesional cuando se agenda un turno."""

from __future__ import annotations

import logging
import os
import smtplib
import socket
from email.message import EmailMessage

from app.config import Professional
from app.scheduling import Appointment, format_datetime_es

logger = logging.getLogger(__name__)

# Algunos hostings tardan mucho (minutos) en tirar el connect si el puerto
# está bloqueado en vez de rechazado. Con un timeout corto, la falla se ve
# rápido en vez de colgar el chat.
_CONNECT_TIMEOUT_SECONDS = 15


class EmailSendError(Exception):
    """No se pudo enviar el mail de aviso."""


def _ipv4_connect(host: str, port: int, timeout: float) -> socket.socket:
    """Conecta por TCP forzando IPv4, con fallback entre direcciones.

    Algunos hostings (Render incluido) resuelven smtp.gmail.com a una
    dirección IPv6 sin tener una ruta de salida IPv6 funcional, lo que da
    "OSError: [Errno 101] Network is unreachable" al conectar — nada que
    ver con el usuario/contraseña.
    """
    addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    last_error: OSError | None = None

    for family, socktype, proto, _, sockaddr in addr_info:
        raw_socket = socket.socket(family, socktype, proto)
        try:
            raw_socket.settimeout(timeout)
            raw_socket.connect(sockaddr)
            return raw_socket
        except OSError as exc:
            last_error = exc
            raw_socket.close()

    raise last_error or OSError("No se pudo resolver una dirección IPv4 para el servidor SMTP.")


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    """SMTP_SSL (puerto 465, TLS implícito) forzando IPv4."""

    def _get_socket(self, host, port, timeout):
        raw_socket = _ipv4_connect(host, port, _CONNECT_TIMEOUT_SECONDS)
        return self.context.wrap_socket(raw_socket, server_hostname=self._host)


class _IPv4SMTP(smtplib.SMTP):
    """SMTP con STARTTLS (puerto 587 típicamente) forzando IPv4."""

    def _get_socket(self, host, port, timeout):
        return _ipv4_connect(host, port, _CONNECT_TIMEOUT_SECONDS)


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
    use_starttls = smtp_port != 465

    try:
        if use_starttls:
            with _IPv4SMTP(smtp_host, smtp_port, timeout=_CONNECT_TIMEOUT_SECONDS) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(email_message)
        else:
            with _IPv4SMTP_SSL(smtp_host, smtp_port, timeout=_CONNECT_TIMEOUT_SECONDS) as server:
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
