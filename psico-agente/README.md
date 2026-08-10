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
                                         (app/email_service.py, API de Resend
                                          por HTTPS — no usa SMTP)
```

## Desarrollo local

Requisitos: Python 3.11+, una API key de Anthropic, y una API key de
[Resend](https://resend.com) para probar el envío real de mails (si no la
tenés todavía, el turno se agenda igual y el chat te avisa que no se pudo
mandar el mail).

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
| `RESEND_API_KEY` | API key de [resend.com](https://resend.com) para mandar el mail de aviso. |
| `RESEND_FROM` | Opcional. Remitente del mail (default `onboarding@resend.dev`, el sandbox de Resend — ver abajo). |
| `DB_PATH` | Dónde se guarda el SQLite con los turnos agendados. |
| `ADMIN_TOKEN` | Token propio (cualquier string largo) para consultar `/api/admin/appointments`. Sin esta variable, el endpoint queda deshabilitado. |

### Por qué Resend y no Gmail/SMTP directo

Probamos primero con Gmail por SMTP (puertos 465 y 587) y ambos fallaron
con errores de red (`Network is unreachable`, `timed out`) al desplegar en
Render — el hosting bloquea el tráfico saliente por esos puertos como
medida anti-spam, algo común en varios proveedores (Render, Heroku,
Railway...). Resend expone una API HTTP normal (HTTPS, puerto 443), que no
se bloquea nunca — el mismo camino que ya usa la llamada a la API de
Claude.

### Crear la API key de Resend

1. Creá una cuenta gratis en [resend.com](https://resend.com) — el free
   tier alcanza de sobra para este uso (100 mails/día). **Registrate con
   la misma dirección que uses como profesional** en
   `professionals.yaml` (`c.milanes93@gmail.com`) — ver por qué abajo.
2. En el dashboard: **API Keys** → **Create API Key**. Copiá el valor
   (empieza con `re_`) — ese es tu `RESEND_API_KEY`.
3. Listo — no hace falta nada más para empezar. `RESEND_FROM` es opcional
   y por default usa `onboarding@resend.dev`, el remitente de sandbox de
   Resend, que no requiere verificar ningún dominio.

**La restricción del sandbox:** sin dominio propio verificado, Resend solo
entrega mails a la dirección con la que te registraste. Como el
profesional que recibe los avisos sos vos mismo, esto no es un problema
mientras uses la misma dirección en ambos lados. Si más adelante agregás
otro profesional con otro mail, para avisarle vas a necesitar verificar un
dominio propio en Resend (**Domains** → **Add Domain**, agregar los
registros DNS que te da) y setear `RESEND_FROM` con una dirección de ese
dominio.

## Si falla el envío de mail (o cualquier otra cosa)

Si `book_appointment` no puede mandar el mail, **el turno igual queda
agendado** — nunca se pierde una reserva por un problema de mail. Al
paciente se le muestra un mensaje genérico ("hubo un problema técnico
avisando al profesional"), sin el detalle técnico. Vos podés ver el motivo
real de dos formas:

### 1. Los logs de Render

Cada error queda logueado con el motivo exacto (código HTTP de Resend,
timeout, variable faltante, etc). En el dashboard de Render: entrá al servicio →
pestaña **Logs**. Buscá líneas que empiecen con `ERROR` — ahí vas a ver
algo como:

```
ERROR app.tools: Turno #3 agendado pero falló el aviso por mail: Resend devolvió 403: {"message":"...","name":"validation_error"}
```

### 2. El endpoint de turnos con mail fallido

`GET /api/admin/appointments?token=TU_ADMIN_TOKEN&only_failed=true`

Te devuelve en JSON los turnos agendados cuyo mail no se pudo mandar, con
el motivo (`email_error`) y los datos del paciente para que lo contactes
manualmente si hace falta. Necesitás configurar `ADMIN_TOKEN` (ver tabla de
variables arriba) — sin esa variable, el endpoint devuelve 401 siempre.

Ejemplo, abriendo la URL directo en el navegador:

```
https://psico-agente.onrender.com/api/admin/appointments?token=tu-token-secreto&only_failed=true
```

### Causas típicas de que Resend rechace el envío

1. **`RESEND_API_KEY` no está seteada** en Render, o tiene un espacio de
   más al copiar/pegar. El log dice explícitamente "Falta la variable de
   entorno RESEND_API_KEY".
2. **El destinatario no es la dirección con la que te registraste en
   Resend** (ver arriba) — sin dominio propio verificado, Resend solo
   entrega a esa dirección. Si el `email` del profesional en
   `professionals.yaml` no coincide con tu cuenta de Resend, lo rechaza.
3. **Si seteaste `RESEND_FROM` manualmente** con una dirección de un
   dominio propio que no está verificado en Resend (Domains → tiene que
   figurar "Verified", no "Pending"). El error en este caso dice
   explícitamente "domain is not verified".
4. **La API key se borró o se regeneró** en el dashboard de Resend después
   de configurarla en Render — generá una nueva y actualizá la variable.

Después de corregir la variable en Render, hacé un **Manual Deploy** (o
esperá el próximo redeploy) para que tome el cambio.

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
   - `RESEND_API_KEY` — ver arriba ("Crear la API key de Resend"). No
     hace falta `RESEND_FROM` para arrancar.
4. Confirmar el deploy. Render te va a dar una URL tipo
   `https://psico-agente.onrender.com` (subdominio gratis).

### Pasos concretos

1. Entrá a Render → **New +** → **Blueprint**.
2. Conectá el repo `cmilanes93/agente` y elegí la rama que quieras
   desplegar (la rama con este código).
3. Render detecta `render.yaml` y te muestra el servicio `psico-agente` a
   crear. Completá las 2 variables secretas del punto anterior.
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
- No hay pantalla de administración visual — hay un endpoint JSON protegido
  (`/api/admin/appointments`, ver arriba) para consultar turnos y errores de
  mail, pero no una interfaz para verlos/cancelarlos con un click.
- No hay autenticación ni protección anti-spam en el chat público. Si en
  algún momento el uso lo justifica, se puede sumar un captcha o rate
  limiting.
- El chat no envía confirmación por mail al paciente, solo al profesional
  (se puede agregar fácil si lo querés).
- Si el mail falla, no hay reintento automático — el turno queda marcado
  como "mail no enviado" en la base y vos lo ves por el endpoint de admin
  o los logs.
