const chatEl = document.getElementById("chat");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const button = form.querySelector("button");

let history = [];
try {
  const stored = sessionStorage.getItem("psico-agente-history");
  if (stored) history = JSON.parse(stored);
} catch (err) {
  history = [];
}

function saveHistory() {
  try {
    sessionStorage.setItem("psico-agente-history", JSON.stringify(history));
  } catch (err) {
    /* sessionStorage no disponible, seguimos sin persistir */
  }
}

function addBubble(text, who) {
  const div = document.createElement("div");
  div.className = `bubble ${who}`;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function renderStoredHistory() {
  for (const msg of history) {
    if (msg.role === "user" && typeof msg.content === "string") {
      addBubble(msg.content, "patient");
    } else if (msg.role === "assistant" && Array.isArray(msg.content)) {
      const text = msg.content
        .filter((block) => block.type === "text")
        .map((block) => block.text)
        .join("");
      if (text) addBubble(text, "agent");
    }
  }
}

async function send(message, { showPatientBubble = true } = {}) {
  if (showPatientBubble) addBubble(message, "patient");
  const pending = addBubble("Escribiendo...", "agent pending");
  input.disabled = true;
  button.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Error de red");
    }
    const data = await res.json();
    history = data.history;
    saveHistory();
    pending.textContent = data.reply;
    pending.classList.remove("pending");
  } catch (err) {
    pending.textContent = "Uy, hubo un error. Probá de nuevo en un momento.";
    pending.classList.remove("pending");
    console.error(err);
  } finally {
    input.disabled = false;
    button.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  send(text);
});

if (history.length === 0) {
  send("Hola", { showPatientBubble: false });
} else {
  renderStoredHistory();
}
