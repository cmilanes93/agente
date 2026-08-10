import socket
import ssl
from unittest.mock import MagicMock

import pytest

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
