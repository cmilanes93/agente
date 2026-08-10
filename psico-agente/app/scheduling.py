"""Cálculo de horarios disponibles y almacenamiento de turnos agendados."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import DEFAULT_TIMEZONE, Professional

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "data" / "appointments.db"))
TZ = ZoneInfo(DEFAULT_TIMEZONE)

_WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

_SPANISH_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def format_datetime_es(dt: datetime) -> str:
    """Formatea una fecha en español, sin depender del locale del sistema."""
    return f"{_SPANISH_WEEKDAYS[dt.weekday()]} {dt.strftime('%d/%m/%Y %H:%M')}"


class SlotUnavailable(Exception):
    """El horario solicitado ya no está disponible."""


@dataclass
class Slot:
    start: datetime
    end: datetime

    def label(self) -> str:
        return format_datetime_es(self.start)


@dataclass
class Appointment:
    id: int
    professional_id: str
    start_at: datetime
    duration_minutes: int
    patient_name: str
    patient_contact: str
    reason: str | None


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professional_id TEXT NOT NULL,
                start_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                patient_name TEXT NOT NULL,
                patient_contact TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(professional_id, start_at)
            )
            """
        )


def _parse_time(value: str) -> time:
    hour, minute = value.strip().split(":")
    return time(int(hour), int(minute))


def _booked_starts(professional_id: str) -> set[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT start_at FROM appointments WHERE professional_id = ?",
            (professional_id,),
        ).fetchall()
    return {row[0] for row in rows}


def generate_available_slots(
    professional: Professional,
    days_ahead: int = 14,
    now: datetime | None = None,
) -> list[Slot]:
    now = now or datetime.now(TZ)
    booked = _booked_starts(professional.id)
    duration = timedelta(minutes=professional.session_duration_minutes)
    slots: list[Slot] = []

    for offset in range(days_ahead):
        day: date = (now + timedelta(days=offset)).date()
        windows = professional.availability.get(_WEEKDAYS[day.weekday()], [])
        for window in windows:
            start_str, end_str = window.split("-")
            window_start = datetime.combine(day, _parse_time(start_str), tzinfo=TZ)
            window_end = datetime.combine(day, _parse_time(end_str), tzinfo=TZ)

            slot_start = window_start
            while slot_start + duration <= window_end:
                if slot_start > now and slot_start.isoformat() not in booked:
                    slots.append(Slot(start=slot_start, end=slot_start + duration))
                slot_start += duration

    return slots


def book_appointment(
    professional: Professional,
    start_at: datetime,
    patient_name: str,
    patient_contact: str,
    reason: str | None = None,
) -> Appointment:
    still_available = any(slot.start == start_at for slot in generate_available_slots(professional))
    if not still_available:
        raise SlotUnavailable("Ese horario ya no está disponible, elegí otro.")

    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO appointments
                    (professional_id, start_at, duration_minutes, patient_name,
                     patient_contact, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    professional.id,
                    start_at.isoformat(),
                    professional.session_duration_minutes,
                    patient_name,
                    patient_contact,
                    reason,
                    datetime.now(TZ).isoformat(),
                ),
            )
            appointment_id = cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise SlotUnavailable("Ese horario se acaba de ocupar, elegí otro.") from exc

    return Appointment(
        id=appointment_id,
        professional_id=professional.id,
        start_at=start_at,
        duration_minutes=professional.session_duration_minutes,
        patient_name=patient_name,
        patient_contact=patient_contact,
        reason=reason,
    )
