"""Definición e implementación de las herramientas del agente."""

from __future__ import annotations

import ast
import operator
from datetime import datetime
from typing import Any, Callable

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "calculator",
        "description": (
            "Evalúa una expresión aritmética (+, -, *, /, **, %, paréntesis) "
            "y devuelve el resultado numérico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expresión matemática, ej: '23 * 47 + 1'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Devuelve la fecha y hora actual del sistema.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "word_count",
        "description": "Cuenta las palabras y caracteres de un texto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a analizar"}
            },
            "required": ["text"],
        },
    },
]

_ALLOWED_OPERATORS: dict[type, Callable[..., float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](
            _eval_node(node.left), _eval_node(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Expresión no soportada: {ast.dump(node)}")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
        return str(result)
    except Exception as exc:
        return f"Error evaluando la expresión: {exc}"


def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def word_count(text: str) -> str:
    words = len(text.split())
    chars = len(text)
    return f"{words} palabras, {chars} caracteres"


TOOL_IMPLEMENTATIONS: dict[str, Callable[..., str]] = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "word_count": word_count,
}
