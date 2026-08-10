from datetime import datetime, time, timedelta

import pytest

from app import scheduling
from app.config import Professional

TZ = scheduling.TZ

ALL_DAYS_WINDOW = {
    day: ["09:00-11:00"]
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduling, "DB_PATH", tmp_path / "test.db")
    scheduling.init_db()


@pytest.fixture
def professional():
    return Professional(
        id="test-pro",
        name="Test Pro",
        email="pro@example.com",
        specialty="Psicología clínica",
        bio="",
        session_duration_minutes=50,
        availability=ALL_DAYS_WINDOW,
    )


@pytest.fixture
def future_day():
    return (datetime.now(TZ) + timedelta(days=2)).date()


def test_generates_slots_within_window(professional, future_day):
    now = datetime.combine(future_day, time(7, 0), tzinfo=TZ)
    slots = scheduling.generate_available_slots(professional, days_ahead=1, now=now)
    assert [s.start.strftime("%H:%M") for s in slots] == ["09:00", "09:50"]


def test_booking_removes_slot_from_availability(professional, future_day):
    now = datetime.combine(future_day, time(7, 0), tzinfo=TZ)
    start = datetime.combine(future_day, time(9, 0), tzinfo=TZ)

    scheduling.book_appointment(professional, start, "Ana", "ana@example.com")

    slots = scheduling.generate_available_slots(professional, days_ahead=1, now=now)
    assert start not in {s.start for s in slots}


def test_double_booking_raises(professional, future_day):
    start = datetime.combine(future_day, time(9, 0), tzinfo=TZ)
    scheduling.book_appointment(professional, start, "Ana", "ana@example.com")

    with pytest.raises(scheduling.SlotUnavailable):
        scheduling.book_appointment(professional, start, "Beto", "beto@example.com")


def test_booking_invalid_slot_raises(professional, future_day):
    start = datetime.combine(future_day, time(9, 5), tzinfo=TZ)
    with pytest.raises(scheduling.SlotUnavailable):
        scheduling.book_appointment(professional, start, "Ana", "ana@example.com")
