import socket
import ssl
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app import email_service
from app.config import Professional
from app.scheduling import TZ, Appointment
from app.email_service import _IPv4SMTP_SSL


def test_ipv4_smtp_ssl_forces_af_inet_and_falls_back(monkeypatch):
    seen_family = {}

    def fake_getaddrinfo(host, port, family, socktype):
        seen_family["value"] = family
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.1.1.1", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("2.2.2.2", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    failing_socket = MagicMock()
    failing_socket.connect.side_effect = OSError("Network is unreachable")
    working_socket = MagicMock()
    sockets = iter([failing_socket, working_socket])
    monkeypatch.setattr(socket, "socket", lambda *a, **k: next(sockets))

    instance = _IPv4SMTP_SSL.__new__(_IPv4SMTP_SSL)
    instance.context = ssl.create_default_context()
    instance._host = "smtp.gmail.com"
    monkeypatch.setattr(
        instance.context,
        "wrap_socket",
        lambda sock, server_hostname: ("wrapped", sock, server_hostname),
    )

    result = instance._get_socket("smtp.gmail.com", 465, 10)

    assert seen_family["value"] == socket.AF_INET
    failing_socket.close.assert_called_once()
    assert result == ("wrapped", working_socket, "smtp.gmail.com")


def test_ipv4_smtp_ssl_raises_when_every_address_fails(monkeypatch):
    def fake_getaddrinfo(host, port, family, socktype):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.1.1.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    failing_socket = MagicMock()
    failing_socket.connect.side_effect = OSError("Network is unreachable")
    monkeypatch.setattr(socket, "socket", lambda *a, **k: failing_socket)

    instance = _IPv4SMTP_SSL.__new__(_IPv4SMTP_SSL)
    instance.context = ssl.create_default_context()
    instance._host = "smtp.gmail.com"

    with pytest.raises(OSError, match="Network is unreachable"):
        instance._get_socket("smtp.gmail.com", 465, 10)


def _fake_appointment_and_professional():
    professional = Professional(
        id="carlos-milanes",
        name="Carlos Manuel Milanes",
        email="c.milanes93@gmail.com",
        specialty="Psicología clínica",
        bio="",
        session_duration_minutes=50,
        availability={},
    )
    appointment = Appointment(
        id=1,
        professional_id="carlos-milanes",
        start_at=datetime.now(TZ),
        duration_minutes=50,
        patient_name="Ana",
        patient_contact="ana@example.com",
        reason=None,
    )
    return professional, appointment


class _FakeServer:
    def __init__(self):
        self.starttls_called = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self):
        self.starttls_called = True

    def login(self, user, password):
        pass

    def send_message(self, message):
        pass


def test_send_appointment_email_uses_starttls_on_port_587(monkeypatch):
    professional, appointment = _fake_appointment_and_professional()
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "c.milanes93@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")

    fake_server = _FakeServer()
    monkeypatch.setattr(email_service, "_IPv4SMTP", lambda *a, **k: fake_server)
    monkeypatch.setattr(
        email_service,
        "_IPv4SMTP_SSL",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debería usar SSL en el puerto 587")),
    )

    email_service.send_appointment_email(professional, appointment)

    assert fake_server.starttls_called is True


def test_send_appointment_email_uses_ssl_on_port_465(monkeypatch):
    professional, appointment = _fake_appointment_and_professional()
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "c.milanes93@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")

    fake_server = _FakeServer()
    monkeypatch.setattr(email_service, "_IPv4SMTP_SSL", lambda *a, **k: fake_server)
    monkeypatch.setattr(
        email_service,
        "_IPv4SMTP",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debería usar STARTTLS en el puerto 465")),
    )

    email_service.send_appointment_email(professional, appointment)

    assert fake_server.starttls_called is False
