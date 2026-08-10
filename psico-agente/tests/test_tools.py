from datetime import datetime, timedelta

import pytest

from app import scheduling, tools
from app.config import Professional

TZ = scheduling.TZ


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduling, "DB_PATH", tmp_path / "test.db")
    scheduling.init_db()


@pytest.fixture(autouse=True)
def fake_professionals(monkeypatch):
    professional = Professional(
        id="carlos-milanes",
        name="Carlos Manuel Milanes",
        email="c.milanes93@gmail.com",
        specialty="Psicología clínica",
        bio="",
        session_duration_minutes=50,
        availability={
            "monday": ["09:00-11:00"],
            "tuesday": ["09:00-11:00"],
            "wednesday": ["09:00-11:00"],
            "thursday": ["09:00-11:00"],
            "friday": ["09:00-11:00"],
            "saturday": [],
            "sunday": [],
        },
    )
    monkeypatch.setattr(tools, "load_professionals", lambda: [professional])
    return professional


def test_list_available_professionals_includes_specialty(fake_professionals):
    result = tools.list_available_professionals()
    assert "Carlos Manuel Milanes" in result
    assert "Psicología clínica" in result


def test_list_available_professionals_filters_by_specialty(fake_professionals):
    result = tools.list_available_professionals(specialty="nutrición")
    assert "No hay profesionales disponibles" in result


def test_book_appointment_sends_email(fake_professionals, monkeypatch):
    sent = {}

    def fake_send(professional, appointment):
        sent["professional"] = professional
        sent["appointment"] = appointment

    monkeypatch.setattr(tools, "send_appointment_email", fake_send)

    future_day = (datetime.now(TZ) + timedelta(days=2)).date()
    result = tools.book_appointment(
        professional_id="carlos-milanes",
        date=future_day.isoformat(),
        time="09:00",
        patient_name="Ana",
        patient_contact="ana@example.com",
    )

    assert "Turno confirmado" in result
    assert "avisó al profesional por mail" in result
    assert sent["appointment"].patient_name == "Ana"

    [row] = scheduling.list_appointments()
    assert row["email_sent"] == 1
    assert row["email_error"] is None


def test_book_appointment_email_failure_keeps_booking(fake_professionals, monkeypatch):
    def fake_send(professional, appointment):
        raise tools.EmailSendError("smtp caído")

    monkeypatch.setattr(tools, "send_appointment_email", fake_send)

    future_day = (datetime.now(TZ) + timedelta(days=2)).date()
    result = tools.book_appointment(
        professional_id="carlos-milanes",
        date=future_day.isoformat(),
        time="09:00",
        patient_name="Ana",
        patient_contact="ana@example.com",
    )

    assert "quedó agendado" in result
    # El detalle técnico del error no se le muestra al paciente...
    assert "smtp caído" not in result

    # ...pero sí queda registrado en la base para que el profesional lo consulte.
    [row] = scheduling.list_appointments(only_failed=True)
    assert row["email_sent"] == 0
    assert row["email_error"] == "smtp caído"


def test_book_appointment_unknown_professional(fake_professionals):
    result = tools.book_appointment(
        professional_id="nope",
        date="2026-01-05",
        time="09:00",
        patient_name="Ana",
        patient_contact="ana@example.com",
    )
    assert "No encontré un profesional" in result
