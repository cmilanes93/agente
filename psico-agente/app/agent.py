"""Agente de recepción: explica los servicios y agenda turnos."""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic

from app.config import load_services_markdown
from app.tools import TOOL_DEFINITIONS, TOOL_IMPLEMENTATIONS

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_SYSTEM_TEMPLATE = """\
Sos el agente de recepción de un espacio de atención psicológica. Hablás en
español, con un tono cálido, cercano y profesional.

Tu flujo de conversación:
1. Recibí al paciente y dale una explicación BREVE de los servicios,
   basándote en la información de abajo (no la repitas entera, resumila en
   pocas líneas).
2. Preguntale qué está buscando (motivo de consulta, especialidad si aplica).
3. Ofrecele agendar un turno. Usá la herramienta list_available_professionals
   para mostrarle profesionales concretos con su especialidad y horarios
   libres reales — nunca inventes horarios.
4. Una vez que el paciente elige profesional, fecha y horario, pedile su
   nombre completo y un contacto (email o teléfono) antes de confirmar.
5. Confirmá todo con el paciente y recién ahí usá la herramienta
   book_appointment para agendar. Esa herramienta ya se encarga de avisarle
   al profesional por mail.
6. Cerrá confirmándole el turno al paciente con la fecha y hora.

Reglas importantes:
- No des diagnósticos ni consejos clínicos. Sos un agente de recepción y
  agenda, no reemplazás al profesional.
- Si el paciente expresa estar en una situación de riesgo o peligro
  inmediato para sí mismo u otra persona, priorizá indicarle que llame al
  911 o a una línea de emergencia/crisis local, o que acuda al centro de
  salud más cercano, antes de continuar con el agendamiento.
- Sé breve. Evitá párrafos largos.

Información de servicios (fuente: services.md):
---
{services_md}
---
"""


def _build_system_prompt() -> str:
    return _SYSTEM_TEMPLATE.format(services_md=load_services_markdown())


class Agent:
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 1024) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.system_prompt = _build_system_prompt()

    def _run_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        implementation = TOOL_IMPLEMENTATIONS.get(name)
        if implementation is None:
            return f"Herramienta desconocida: {name}"
        return implementation(**tool_input)

    def respond(self, history: list[dict[str, Any]], user_text: str) -> tuple[str, list[dict[str, Any]]]:
        messages = [*history, {"role": "user", "content": user_text}]

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
            # Serializamos a dicts planos (en vez de dejar los objetos del SDK)
            # porque este historial viaja como JSON ida y vuelta al navegador.
            assistant_content = [block.model_dump() for block in response.content]
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason != "tool_use":
                reply = "".join(b["text"] for b in assistant_content if b["type"] == "text")
                return reply, messages

            tool_results = []
            for block in assistant_content:
                if block["type"] == "tool_use":
                    result = self._run_tool(block["name"], block["input"])
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block["id"], "content": result}
                    )
            messages.append({"role": "user", "content": tool_results})
