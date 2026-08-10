# agente

Repo de aprendizaje con agentes de IA usando Claude (Anthropic API) en
Python.

- **[`src/`](src/)** — demo mínima de consola con tool use (calculadora,
  hora actual, contador de palabras). Ver instrucciones más abajo.
- **[`psico-agente/`](psico-agente/)** — proyecto concreto: un agente web de
  recepción para un espacio de atención psicológica, que explica los
  servicios, agenda turnos según la disponibilidad real del profesional y
  le avisa por mail. Incluye deploy a producción (Render). Ver el README
  de esa carpeta para instalación, variables de entorno y despliegue.

## Demo de consola (`src/`)

### Requisitos

- Python 3.10+
- Una API key de Anthropic ([console.anthropic.com](https://console.anthropic.com))

### Instalación

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Editá `.env` y agregá tu key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Uso

```bash
python -m src.main
```

Esto abre un chat por consola. Escribí `salir` para terminar.

Ejemplo:

```
Vos: ¿cuánto es 23 * 47 y qué hora es?
Agente: [usa las herramientas calculator y get_current_time]
Agente: 23 * 47 = 1081. La hora actual es 18:42:10.
```

### Estructura

```
src/
  agent.py   # loop principal: manda mensajes a Claude y ejecuta tool calls
  tools.py   # definición e implementación de las herramientas
  main.py    # punto de entrada (chat de consola)
tests/
  test_tools.py
```

### Agregar una herramienta nueva

1. En `src/tools.py`, agregá la definición (nombre, descripción, schema de
   inputs) a `TOOL_DEFINITIONS` y la función que la implementa a
   `TOOL_IMPLEMENTATIONS`.
2. Listo — el agente la va a poder usar automáticamente.

### Próximos pasos

- Agregar más herramientas (búsqueda web, lectura de archivos, APIs externas).
- Persistir el historial de conversación entre ejecuciones.
- Cambiar el modelo o los parámetros en `src/agent.py`.
