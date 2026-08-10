"""Backend FastAPI: sirve el chat estático y el endpoint del agente."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import Agent
from app.scheduling import init_db, list_appointments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"
MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 60
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")

init_db()

app = FastAPI(title="Agente de atención psicológica")
_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    reply: str
    history: list[dict]


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=400, detail="Mensaje demasiado largo.")
    if len(request.history) > MAX_HISTORY_MESSAGES:
        raise HTTPException(status_code=400, detail="Conversación demasiado larga, reiniciá el chat.")

    try:
        reply, history = get_agent().respond(request.history, message)
    except Exception as exc:  # noqa: BLE001 - boundary de la API, se traduce a 502
        logger.exception("Error inesperado del agente")
        raise HTTPException(status_code=502, detail=f"Error del agente: {exc}") from exc

    return ChatResponse(reply=reply, history=history)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/admin/appointments")
def admin_appointments(token: str, only_failed: bool = False) -> dict[str, Any]:
    """Lista los turnos agendados, con estado del mail de aviso.

    Protegido por ADMIN_TOKEN (variable de entorno) — sin ella, el endpoint
    queda deshabilitado. Uso: /api/admin/appointments?token=...&only_failed=true
    """
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token inválido o ADMIN_TOKEN no configurado.")
    return {"appointments": list_appointments(only_failed=only_failed)}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
