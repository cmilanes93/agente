import json
import urllib.error
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app import email_service
from app.config import Professional
from app.scheduling import TZ, Appointment


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


def test_send_appointment_email_missing_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    professional, appointment = _fake_appointment_and_professional()

    with pytest.raises(email_service.EmailSendError, match="RESEND_API_KEY"):
        email_service.send_appointment_email(professional, appointment)


def test_send_appointment_email_success(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    professional, appointment = _fake_appointment_and_professional()

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def read(self):
            return b'{"id": "email_123"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(email_service.urllib.request, "urlopen", fake_urlopen)

    email_service.send_appointment_email(professional, appointment)

    assert captured["url"] == email_service.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["body"]["to"] == ["c.milanes93@gmail.com"]
    assert "Ana" in captured["body"]["subject"]


def test_send_appointment_email_http_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    professional, appointment = _fake_appointment_and_professional()

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            email_service.RESEND_API_URL, 422, "Unprocessable", {}, MagicMock(read=lambda: b'{"message":"bad from"}')
        )

    monkeypatch.setattr(email_service.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(email_service.EmailSendError, match="422"):
        email_service.send_appointment_email(professional, appointment)


def test_send_appointment_email_network_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    professional, appointment = _fake_appointment_and_professional()

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(email_service.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(email_service.EmailSendError, match="timed out"):
        email_service.send_appointment_email(professional, appointment)
