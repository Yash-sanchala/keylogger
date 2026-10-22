"use strict";
const el = id => document.getElementById(id);
let connecting = false;
let socket = null;
let connected = false;

function showError(message) {
  el("error").textContent = message;
  el("error").hidden = !message;
}

function disconnected(message) {
  connected = false;
  el("status").textContent = "Disconnected — monitoring stopped";
  el("status").classList.remove("active");
  el("connection").textContent = message;
  for (const name of ["start", "stop", "clear"]) el(name).disabled = true;
  el("reconnect").hidden = false;
  el("key").textContent = "—";
  el("held").textContent = "None";
}

function render(state) {
  const active = state.phase === "active";
  const busy = ["starting", "active", "stopping"].includes(state.phase);
  el("status").textContent = ({active:"Monitoring active", starting:"Starting…", stopping:"Stopping…", error:"Stopped — listener unavailable"})[state.phase] || "Stopped";
  el("status").classList.toggle("active", active);
  el("connection").textContent = "Connected to your local service";
  el("start").disabled = !connected || busy;
  el("stop").disabled = !connected || !["active", "starting"].includes(state.phase);
  el("clear").disabled = !connected;
  el("key").textContent = state.key || "—";
  el("held").textContent = state.held.length ? state.held.join(" + ") : "None";
  el("preview").textContent = state.preview;
  el("placeholder").hidden = state.preview.length > 0;
  el("length").textContent = `${Array.from(state.preview).length} / 48`;
  showError(state.error || "");
}

async function connect() {
  if (connecting || (socket && [WebSocket.CONNECTING, WebSocket.OPEN].includes(socket.readyState))) return;
  connecting = true;
  el("reconnect").hidden = true;
  el("status").textContent = "Connecting…";
  showError("");
  try {
    const response = await fetch("/session", {method: "POST", headers: {"X-Keyboard-Lab": "viewer"}, cache: "no-store"});
    if (!response.ok) throw new Error("Connection refused");
    const {token} = await response.json();
    socket = new WebSocket(`ws://${location.host}/live?token=${encodeURIComponent(token)}`);
  } catch (_error) {
    disconnected("Start the local service in CMD, then click Reconnect.");
    return;
  } finally {
    connecting = false;
  }
  socket.addEventListener("open", () => { connected = true; });
  socket.addEventListener("message", event => {
    const state = JSON.parse(event.data);
    if (state.type === "state") render(state);
  });
  socket.addEventListener("close", event => disconnected(`Connection closed (${event.code}${event.reason ? ": " + event.reason : ""}). Keep the console service open, close other viewer tabs, then reconnect. Click Start to resume.`));
  socket.addEventListener("error", () => showError("Cannot connect. Keep the console service running and use only one viewer tab."));
}

for (const action of ["start", "stop", "clear"]) {
  el(action).addEventListener("click", () => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({action}));
  });
}
el("reconnect").addEventListener("click", connect);
window.addEventListener("pagehide", () => socket?.close(1000, "Page closed"));
window.addEventListener("pageshow", event => { if (event.persisted) connect(); });
// Keep navigation within the viewer.



connect();
