"""Carga de configuración: profesionales/agenda y contenido de servicios."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

APP_DIR = Path(__file__).parent
DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"


@dataclass
class Professional:
    id: str
    name: str
    email: str
    specialty: str
    bio: str
    session_duration_minutes: int
    availability: dict[str, list[str]]


def load_professionals() -> list[Professional]:
    path = Path(os.environ.get("PROFESSIONALS_FILE", APP_DIR / "data" / "professionals.yaml"))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [Professional(**item) for item in data["professionals"]]


def load_services_markdown() -> str:
    path = Path(os.environ.get("SERVICES_MD_FILE", APP_DIR / "content" / "services.md"))
    return path.read_text(encoding="utf-8")
