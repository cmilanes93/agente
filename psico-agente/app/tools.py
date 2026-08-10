"""Definición e implementación de las herramientas del agente de turnos."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.config import Professional, load_professionals
from app.email_service import EmailSendError, send_appointment_email
from app.scheduling import TZ, SlotUnavailable, format_datetime_es, generate_available_slots
from app.scheduling import book_appointment as _book_appointment

MAX_SLOTS_PER_PROFESSIONAL = 8

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_available_professionals",
        "description": (
            "Lista los profesionales disponibles con su especialidad y los "
            "próximos horarios libres en su agenda. Usala para ofrecerle "
            "turnos concretos al paciente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": "Especialidad buscada, si el paciente la mencionó (opcional).",
                }
            },
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Agenda un turno con un profesional en un horario puntual y le "
            "envía un mail de aviso. Usala solo después de confirmar con el "
            "paciente el profesional, la fecha y el horario exactos, y de "
            "haber pedido su nombre y un contacto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "professional_id": {
                    "type": "string",
                    "description": "Id del profesional, ej: 'carlos-milanes'.",
                },
                "date": {"type": "string", "description": "Fecha en formato YYYY-MM-DD."},
                "time": {"type": "string", "description": "Hora en formato HH:MM (24hs)."},
                "patient_name": {"type": "string", "description": "Nombre completo del paciente."},
                "patient_contact": {
                    "type": "string",
                    "description": "Email o teléfono de contacto del paciente.",
                },
                "reason": {
                    "type": "string",
                    "description": "Motivo de consulta, si el paciente lo compartió (opcional).",
                },
            },
            "required": ["professional_id", "date", "time", "patient_name", "patient_contact"],
        },
    },
]


def _professionals_by_id() -> dict[str, Professional]:
    return {p.id: p for p in load_professionals()}


def list_available_professionals(specialty: str | None = None) -> str:
    professionals = load_professionals()
    if specialty:
        needle = specialty.strip().lower()
        professionals = [p for p in professionals if needle in p.specialty.lower()]

    if not professionals:
        return "No hay profesionales disponibles con esa especialidad."

    lines: list[str] = []
    for professional in professionals:
        slots = generate_available_slots(professional)[:MAX_SLOTS_PER_PROFESSIONAL]
        lines.append(f"- {professional.name} (id: {professional.id}) - {professional.specialty}")
        if not slots:
            lines.append("  Sin horarios disponibles en los próximos 14 días.")
            continue
        for slot in slots:
            lines.append(f"  * {slot.start.strftime('%Y-%m-%d')} {slot.start.strftime('%H:%M')} - {slot.label()}")
    return "\n".join(lines)


def book_appointment(
    professional_id: str,
    date: str,
    time: str,
    patient_name: str,
    patient_contact: str,
    reason: str | None = None,
) -> str:
    professional = _professionals_by_id().get(professional_id)
    if professional is None:
        return f"No encontré un profesional con id '{professional_id}'."

    try:
        start_at = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return "Formato de fecha/hora inválido. Usá date=YYYY-MM-DD y time=HH:MM."

    try:
        appointment = _book_appointment(
            professional=professional,
            start_at=start_at,
            patient_name=patient_name,
            patient_contact=patient_contact,
            reason=reason,
        )
    except SlotUnavailable as exc:
        return str(exc)

    try:
        send_appointment_email(professional, appointment)
        email_status = "Se avisó al profesional por mail."
    except EmailSendError as exc:
        email_status = f"El turno quedó agendado, pero no se pudo avisar por mail ({exc})."

    when = format_datetime_es(appointment.start_at)
    return f"Turno confirmado con {professional.name} el {when}. {email_status}"


TOOL_IMPLEMENTATIONS: dict[str, Callable[..., str]] = {
    "list_available_professionals": list_available_professionals,
    "book_appointment": book_appointment,
}
