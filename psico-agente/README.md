# psico-agente

Agente de recepción para un espacio de atención psicológica. Recibe al
paciente por un chat web, le explica brevemente los servicios (desde
`app/content/services.md`), le ofrece profesionales disponibles según su
especialidad y agenda, agenda el turno y le avisa al profesional por mail.

Empieza con un solo profesional: **Carlos Manuel Milanes** (Psicología
clínica, `c.milanes93@gmail.com`), configurado en
`app/data/professionals.yaml`.

## Cómo funciona

```
Paciente (navegador)
   │  chat en static/index.html
   ▼
FastAPI /api/chat (app/main.py)
   │  historial de la conversación va y viene como JSON
   ▼
Agent (app/agent.py) ── llama a Claude (Anthropic API) con tools
   │
   ├── list_available_professionals  → app/scheduling.py (calcula horarios
   │                                    libres a partir de la agenda menos
   │                                    los turnos ya guardados en SQLite)
   └── book_appointment               → guarda el turno + envía mail
                                         (app/email_service.py, SMTP)
```

## Desarrollo local

Requisitos: Python 3.11+, una API key de Anthropic, y una contraseña de
aplicación de Gmail (para probar el envío real de mails; si no la tenés
todavía, el turno se agenda igual y el chat te avisa que no se pudo mandar
el mail).

```bash
cd psico-agente
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completá las variables, ver más abajo
```

Cargá las variables y corré el servidor:

```bash
set -a; source .env; set +a
uvicorn app.main:app --reload
```

Abrí `http://localhost:8000`.

Tests:

```bash
pytest
```

## Variables de entorno

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` | Autenticar con la API de Claude. |
| `ANTHROPIC_MODEL` | Modelo a usar (default `claude-sonnet-5`). |
| `SMTP_HOST` / `SMTP_PORT` | Servidor SMTP (default Gmail: `smtp.gmail.com` / `465`). |
| `SMTP_USER` | Cuenta de Gmail que envía el mail (`c.milanes93@gmail.com`). |
| `SMTP_PASSWORD` | Contraseña de aplicación de Gmail (no tu contraseña normal). |
| `DB_PATH` | Dónde se guarda el SQLite con los turnos agendados. |

### Generar la contraseña de aplicación de Gmail

1. Activá la verificación en 2 pasos en tu cuenta de Google (si no la
   tenés activada, `myaccount.google.com/security`).
2. Andá a `myaccount.google.com/apppasswords`.
3. Creá una contraseña de aplicación (nombre libre, ej: "psico-agente").
   Google te da un código de 16 caracteres — ese es tu `SMTP_PASSWORD`.

## Agregar más profesionales

Editá `app/data/professionals.yaml` y agregá otro bloque bajo
`professionals:` con `id`, `name`, `email`, `specialty`,
`session_duration_minutes` y `availability` (por día de la semana, en
horario 24hs). No hace falta tocar código.

## Despliegue en Render

El repo ya incluye `render.yaml` en la raíz (`/render.yaml`), un
"Blueprint" que Render lee automáticamente para crear el servicio.

### Lo que necesito de vos

1. **Cuenta en Render** — creála gratis en [render.com](https://render.com)
   (podés entrar con tu cuenta de GitHub).
2. **Dar acceso de Render a tu repo de GitHub** `cmilanes93/agente` — Render
   te lo pide al crear el Blueprint (New + → Blueprint → elegís el repo).
3. Cuando Render lea `render.yaml` va a pedirte completar estas variables
   (son secretas, se cargan directo en el panel de Render, **nunca me las
   pases a mí por chat**):
   - `ANTHROPIC_API_KEY` — la generás en
     [console.anthropic.com](https://console.anthropic.com) → API Keys.
   - `SMTP_USER` — `c.milanes93@gmail.com`
   - `SMTP_PASSWORD` — la contraseña de aplicación de Gmail (ver arriba).
4. Confirmar el deploy. Render te va a dar una URL tipo
   `https://psico-agente.onrender.com` (subdominio gratis).

### Pasos concretos

1. Entrá a Render → **New +** → **Blueprint**.
2. Conectá el repo `cmilanes93/agente` y elegí la rama que quieras
   desplegar (la rama con este código).
3. Render detecta `render.yaml` y te muestra el servicio `psico-agente` a
   crear. Completá las 3 variables secretas del punto anterior.
4. Click en **Apply** / **Create Blueprint**. El primer build tarda unos
   minutos (arma la imagen Docker).
5. Cuando termine, entrá a la URL que te dio Render y probá el chat.

### Importante sobre los turnos agendados

El plan **free** de Render no tiene disco persistente: si Render reinicia
o redeployá el servicio, la base de turnos (SQLite) se reinicia vacía.
Para arrancar y probar está bien. Cuando quieras que los turnos queden
guardados de forma permanente:

1. En Render, cambiá el plan del servicio a **Starter** (~7 USD/mes).
2. En `render.yaml`, descomentá el bloque `disk:` (ya está en el archivo,
   comentado, listo para usar).
3. Redeployá.

### Otras limitaciones de esta primera versión

- Un solo profesional cargado (vos). Agregar más es editar un YAML.
- No hay pantalla de administración para ver/cancelar turnos — se
  consultan directo en la base SQLite o por mail (cada turno te llega por
  mail).
- No hay autenticación ni protección anti-spam en el chat público. Si en
  algún momento el uso lo justifica, se puede sumar un captcha o rate
  limiting.
- El chat no envía confirmación por mail al paciente, solo al profesional
  (se puede agregar fácil si lo querés).
