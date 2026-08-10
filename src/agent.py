"""Loop principal del agente: conversa con Claude y ejecuta tool calls."""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic

from src.tools import TOOL_DEFINITIONS, TOOL_IMPLEMENTATIONS

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
SYSTEM_PROMPT = (
    "Sos un asistente útil y conciso. Cuando una herramienta te puede dar "
    "una respuesta más precisa (cálculos, hora actual, conteo de texto), "
    "usala en vez de adivinar."
)


class Agent:
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 1024) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.messages: list[dict[str, Any]] = []

    def _run_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        implementation = TOOL_IMPLEMENTATIONS.get(name)
        if implementation is None:
            return f"Herramienta desconocida: {name}"
        return implementation(**tool_input)

    def send(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(
                    block.text for block in response.content if block.type == "text"
                )

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._run_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            self.messages.append({"role": "user", "content": tool_results})
