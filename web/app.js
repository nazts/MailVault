"use strict";

/* ================= config ================= */
const DOMINIOS = {
  "gmail.com": ["imap.gmail.com", "smtp.gmail.com"],
  "outlook.com": ["outlook.office365.com", "smtp-mail.outlook.com"],
  "hotmail.com": ["outlook.office365.com", "smtp-mail.outlook.com"],
  "live.com": ["outlook.office365.com", "smtp-mail.outlook.com"],
  "msn.com": ["outlook.office365.com", "smtp-mail.outlook.com"],
  "yahoo.com": ["imap.mail.yahoo.com", "smtp.mail.yahoo.com"],
  "icloud.com": ["imap.mail.me.com", "smtp.mail.me.com"],
  "aol.com": ["imap.aol.com", "smtp.aol.com"],
  "zoho.com": ["imap.zoho.com", "smtp.zoho.com"],
  "proton.me": ["imap.protonmail.ch", "smtp.protonmail.ch"],
  "protonmail.com": ["imap.protonmail.ch", "smtp.protonmail.ch"],
  "yandex.com": ["imap.yandex.com", "smtp.yandex.com"],
  "gmx.com": ["imap.gmx.com", "mail.gmx.com"],
  "mail.com": ["imap.mail.com", "smtp.mail.com"]
};
const CAMPOS = ["nombre", "correo", "usuario", "contrasena", "servidor", "notas"];

/* ================= estado ================= */
let cuentas = [];
let idEdicion = null;
let ordenCol = "nombre";
let ordenInv = false;
let filtro = "";
let timerBusqueda = null;

const $ = (id) => document.getElementById(id);

/* ================= utilidades ================= */
async function api(ruta, opciones) {
  const res = await fetch(ruta, opciones);
  let datos = {};
  try { datos = await res.json(); } catch (e) { /* sin cuerpo */ }
  if (!res.ok) {
    const err = new Error(datos.error || ("Error " + res.status));
    err.status = res.status;
    throw err;
  }
  return datos;
}

function mostrarToast(msg, ok = true) {
  const t = $("toast");
  t.classList.toggle("error", !ok);
  $("toast-msg").textContent = msg;
  bootstrap.Toast.getOrCreateInstance(t, { delay: 2200 }).show();
}

function botonIcono(icono, titulo, fn) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn btn-sm btn-icono text-secondary";
  b.title = titulo;
  b.innerHTML = `<i class="bi ${icono}"></i>`;
  b.addEventListener("click", fn);
  return b;
}

/* ================= login ================= */
function mostrarLogin(esPrimeraVez) {
  $("vista-app").classList.add("d-none");
  $("vista-login").classList.remove("d-none");
  $("form-crear").classList.toggle("d-none", !esPrimeraVez);
  $("form-entrar").classList.toggle("d-none", esPrimeraVez);
  $("login-subtitulo").textContent = esPrimeraVez
    ? "Primera vez: configura tu clave"
    : "Desbloquea tus cuentas";
  $("error-entrar").classList.add("d-none");
  $("error-crear").classList.add("d-none");
  (esPrimeraVez ? $("clave-nueva") : $("clave-entrar")).focus();
}

function mostrarApp() {
  $("vista-login").classList.add("d-none");
  $("vista-app").classList.remove("d-none");
  render();
  $("campo-buscar").focus();
}

async function entrar() {
  const clave = $("clave-entrar").value;
  if (!clave) return;
  try {
    const datos = await api("/api/desbloquear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clave })
    });
    cuentas = datos.cuentas;
    mostrarApp();
  } catch (e) {
    $("error-entrar").classList.remove("d-none");
    $("clave-entrar").select();
  }
}

async function crearCaja() {
  const clave = $("clave-nueva").value;
  const confirma = $("clave-confirma").value;
  const err = $("error-crear");
  err.classList.add("d-none");
  if (clave.length < 4) {
    err.textContent = "La clave debe tener al menos 4 caracteres.";
    err.classList.remove("d-none");
    return;
  }
  if (clave !== confirma) {
    err.textContent = "Las claves no coinciden.";
    err.classList.remove("d-none");
    return;
  }
  try {
    const datos = await api("/api/crear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clave })
    });
    cuentas = datos.cuentas;
    mostrarApp();
    if (datos.migradas > 0) {
      mostrarToast(`Se importaron ${datos.migradas} cuentas de la versión anterior ✓`);
    } else {
      mostrarToast("Caja creada ✓");
    }
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove("d-none");
  }
}

async function cerrarSesion() {
  try { await fetch("/api/cerrar", { method: "POST" }); } catch (e) { /* noop */ }
  cuentas = [];
  $("clave-entrar").value = "";
  mostrarLogin(false);
}

/* ================= tabla ================= */
function render() {
  const tbody = $("tbody-cuentas");
  tbody.innerHTML = "";
  const t = filtro.toLowerCase();
  let lista = cuentas.filter((c) =>
    !t || CAMPOS.some((k) => String(c[k] || "").toLowerCase().includes(t))
  );
  lista.sort((a, b) => {
    const va = String(a[ordenCol] || "").toLowerCase();
    const vb = String(b[ordenCol] || "").toLowerCase();
    return ordenInv ? vb.localeCompare(va, "es") : va.localeCompare(vb, "es");
  });

  for (const c of lista) {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.className = "text-center";
    td1.textContent = c.nombre || "—";
    const td2 = document.createElement("td");
    td2.className = "text-center";
    td2.textContent = c.correo || "—";
    const td3 = document.createElement("td");
    td3.className = "text-center text-nowrap";
    td3.append(
      botonIcono("bi-pencil", "Editar", () => abrirEditar(c.id)),
      botonIcono("bi-send", "Enviar a Telegram", () => enviarTelegrama(c)),
      botonIcono("bi-copy", "Copiar correo", () => copiarCorreo(c)),
      botonIcono("bi-trash3", "Eliminar", () => eliminarCuenta(c))
    );
    tr.append(td1, td2, td3);
    tbody.appendChild(tr);
  }

  const total = cuentas.length;
  $("lbl-total").textContent = total + (total === 1 ? " cuenta" : " cuentas");
  $("lbl-estado").textContent = lista.length === 0
    ? (t ? "Sin resultados para «" + filtro + "»" : "Aún no hay cuentas. Pulsa «Nueva cuenta».")
    : (t ? lista.length + " resultado(s) de " + total : total + " cuentas guardadas");
  pintarIndicador();
}

function pintarIndicador() {
  document.querySelectorAll("thead th[data-col]").forEach((th) => {
    const ind = th.querySelector(".indicador");
    if (th.dataset.col === ordenCol) {
      ind.textContent = ordenInv ? " ▼" : " ▲";
    } else {
      ind.textContent = "";
    }
  });
}

function ordenar(col) {
  if (ordenCol === col) {
    ordenInv = !ordenInv;
  } else {
    ordenCol = col;
    ordenInv = false;
  }
  render();
}

/* ================= CRUD ================= */
function limpiarFormulario() {
  CAMPOS.forEach((k) => {
    const el = $("campo-" + k);
    if (el) el.value = "";
  });
  idEdicion = null;
  $("titulo-modal").textContent = "Nueva cuenta";
}

function abrirNueva() {
  limpiarFormulario();
  bootstrap.Modal.getOrCreateInstance($("modalCuenta")).show();
  $("campo-nombre").focus();
}

function abrirEditar(id) {
  const c = cuentas.find((x) => x.id === id);
  if (!c) return;
  idEdicion = id;
  CAMPOS.forEach((k) => { $("campo-" + k).value = c[k] || ""; });
  $("titulo-modal").textContent = "Editar cuenta";
  bootstrap.Modal.getOrCreateInstance($("modalCuenta")).show();
  $("campo-nombre").focus();
}

async function guardar() {
  const d = {};
  CAMPOS.forEach((k) => { d[k] = $("campo-" + k).value.trim(); });
  if (!d.nombre && !d.correo) {
    mostrarToast("Pon al menos el nombre o el correo", false);
    return;
  }
  try {
    if (idEdicion === null) {
      await api("/api/cuentas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(d)
      });
      mostrarToast("Guardado ✓");
    } else {
      await api("/api/cuentas/" + idEdicion, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(d)
      });
      mostrarToast("Actualizado ✓");
    }
    cuentas = await api("/api/cuentas");
    bootstrap.Modal.getInstance($("modalCuenta")).hide();
    render();
    limpiarFormulario(); // listo para la siguiente
  } catch (e) {
    mostrarToast(e.message, false);
  }
}

async function eliminarCuenta(c) {
  if (!confirm(`¿Eliminar la cuenta «${c.nombre || c.correo}»?`)) return;
  try {
    await api("/api/cuentas/" + c.id, { method: "DELETE" });
    cuentas = await api("/api/cuentas");
    render();
    mostrarToast("Cuenta eliminada");
  } catch (e) {
    mostrarToast(e.message, false);
  }
}

async function copiarCorreo(c) {
  const correo = c.correo || $("campo-correo").value.trim();
  if (!correo) { mostrarToast("No hay correo que copiar", false); return; }
  try {
    await navigator.clipboard.writeText(correo);
    mostrarToast("Correo copiado: " + correo);
  } catch (e) {
    mostrarToast("No se pudo copiar", false);
  }
}

function exportar() {
  window.location = "/api/exportar";
}

/* ================= clave ================= */
async function cambiarClave() {
  const actual = $("clave-actual").value;
  const nueva = $("clave-nueva2").value;
  const confirma = $("clave-confirma2").value;
  const err = $("error-clave");
  err.classList.add("d-none");
  if (nueva.length < 4) {
    err.textContent = "La nueva clave debe tener al menos 4 caracteres.";
    err.classList.remove("d-none");
    return;
  }
  if (nueva !== confirma) {
    err.textContent = "Las claves no coinciden.";
    err.classList.remove("d-none");
    return;
  }
  try {
    await api("/api/clave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actual, nueva })
    });
    bootstrap.Modal.getInstance($("modalClave")).hide();
    $("clave-actual").value = $("clave-nueva2").value = $("clave-confirma2").value = "";
    mostrarToast("Clave cambiada ✓");
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove("d-none");
  }
}

/* ================= autocompletado / autorelleno ================= */
function actualizarDatalist() {
  const v = $("campo-correo").value;
  const dl = $("lista-dominios");
  dl.innerHTML = "";
  const opciones = v.includes("@")
    ? Object.keys(DOMINIOS).map((d) => v.split("@")[0] + "@" + d)
    : Object.keys(DOMINIOS).filter((d) => d.includes(v.toLowerCase()));
  for (const opc of opciones) {
    const op = document.createElement("option");
    op.value = opc;
    dl.appendChild(op);
  }
}

function autorellenar() {
  const correo = $("campo-correo").value.trim();
  if (!correo.includes("@")) return;
  const [usuario, dominio] = correo.split("@");
  const par = DOMINIOS[dominio.toLowerCase()];
  if (usuario && !$("campo-usuario").value.trim()) {
    $("campo-usuario").value = usuario;
  }
  if (par && !$("campo-servidor").value.trim()) {
    $("campo-servidor").value = "imap: " + par[0] + " · smtp: " + par[1];
  }
}

/* ================= generador de contrasenas ================= */
const GEN_DEFAULT = { largo: 16, mayus: true, minus: true, nums: true,
                      simbolos: true, sinAmbiguos: false, plataforma: "" };
const AMBIGUOS = new Set("0O1lI|".split(""));

// Plantillas por plataforma: longitud recomendada + reglas de cada una
const PLATAFORMAS = {
  tiktok: {
    largo: 14,
    info: "Requisitos TikTok: 8–20 caracteres · al menos una letra y un número",
  },
  instagram: {
    largo: 12,
    info: "Requisitos Instagram: mínimo 6 caracteres · al menos una letra y un número",
  },
  facebook: {
    largo: 12,
    info: "Requisitos Facebook: mínimo 6 caracteres",
  },
  youtube: {
    largo: 14,
    info: "Requisitos YouTube (cuenta Google): mínimo 8 caracteres",
  },
  twitch: {
    largo: 12,
    info: "Requisitos Twitch: 8–30 caracteres · no debe contener tu nombre de usuario",
  },
};

let configGen = { ...GEN_DEFAULT };
let modoGenerador = "solo"; // "cuenta" si se abrio desde el formulario

function cargarConfigGen() {
  try {
    const guardado = JSON.parse(localStorage.getItem("genConfig") || "null");
    if (guardado) configGen = { ...GEN_DEFAULT, ...guardado };
  } catch (e) { /* valores por defecto */ }
}

function guardarConfigGen() {
  localStorage.setItem("genConfig", JSON.stringify(configGen));
}

function randInt(max) {
  const a = new Uint32Array(1);
  crypto.getRandomValues(a);
  return a[0] % max;
}

function generarPassword() {
  let conjuntos = [];
  if (configGen.mayus) conjuntos.push("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
  if (configGen.minus) conjuntos.push("abcdefghijklmnopqrstuvwxyz");
  if (configGen.nums) conjuntos.push("0123456789");
  if (configGen.simbolos) conjuntos.push("!@#$%^&*()-_=+[]{};:,.<>?");
  if (configGen.sinAmbiguos) {
    conjuntos = conjuntos
      .map((s) => s.split("").filter((c) => !AMBIGUOS.has(c)).join(""))
      .filter((s) => s.length > 0);
  }
  if (!conjuntos.length) return "";
  const todos = conjuntos.join("");
  const pwd = conjuntos.map((c) => c[randInt(c.length)]); // uno de cada tipo
  while (pwd.length < configGen.largo) {
    pwd.push(todos[randInt(todos.length)]);
  }
  for (let i = pwd.length - 1; i > 0; i--) { // mezcla
    const j = randInt(i + 1);
    [pwd[i], pwd[j]] = [pwd[j], pwd[i]];
  }
  return pwd.join("");
}

function tamanoCharset() {
  let s = "";
  if (configGen.mayus) s += "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  if (configGen.minus) s += "abcdefghijklmnopqrstuvwxyz";
  if (configGen.nums) s += "0123456789";
  if (configGen.simbolos) s += "!@#$%^&*()-_=+[]{};:,.<>?";
  if (configGen.sinAmbiguos) {
    s = s.split("").filter((c) => !AMBIGUOS.has(c)).join("");
  }
  return s.length;
}

function leerControlesGen() {
  configGen.largo = parseInt($("gen-largo").value, 10) || 16;
  configGen.mayus = $("gen-mayus").checked;
  configGen.minus = $("gen-minus").checked;
  configGen.nums = $("gen-nums").checked;
  configGen.simbolos = $("gen-simbolos").checked;
  configGen.sinAmbiguos = $("gen-ambiguos").checked;
}

function aplicarConfigGenAControles() {
  $("gen-largo").value = configGen.largo;
  $("gen-largo-valor").textContent = configGen.largo;
  $("gen-mayus").checked = configGen.mayus;
  $("gen-minus").checked = configGen.minus;
  $("gen-nums").checked = configGen.nums;
  $("gen-simbolos").checked = configGen.simbolos;
  $("gen-ambiguos").checked = configGen.sinAmbiguos;
  pintarPlataforma();
}

function pintarPlataforma() {
  $("gen-plataforma").value = configGen.plataforma || "";
  const p = configGen.plataforma && PLATAFORMAS[configGen.plataforma];
  $("gen-info-plataforma").textContent = p ? p.info : "";
}

function aplicarPreset() {
  const id = $("gen-plataforma").value;
  configGen.plataforma = id;
  if (id && PLATAFORMAS[id]) {
    const p = PLATAFORMAS[id];
    configGen.largo = p.largo;
    configGen.mayus = configGen.minus = configGen.nums = configGen.simbolos = true;
    aplicarConfigGenAControles();
  }
  refrescarGenerador();
}

function refrescarGenerador(manual = false) {
  leerControlesGen();
  if (manual && configGen.plataforma) {
    configGen.plataforma = ""; // el usuario ajusto algo a mano: sale de la plantilla
  }
  guardarConfigGen(); // recuerda la configuracion
  const pwd = generarPassword();
  $("gen-resultado").value = pwd;
  const tam = tamanoCharset();
  const bits = tam > 0 ? Math.round(configGen.largo * Math.log2(tam)) : 0;
  $("gen-entropia").textContent = bits > 0 ? "≈ " + bits + " bits de entropía" : "";
  pintarPlataforma();
}

function abrirGenerador(modo) {
  modoGenerador = modo || "solo";
  aplicarConfigGenAControles();
  refrescarGenerador();
  bootstrap.Modal.getOrCreateInstance($("modalGenerador")).show();
}

/* ================= Telegram ================= */
async function enviarTelegrama(c) {
  try {
    const r = await api("/api/cuentas/" + c.id + "/telegram", { method: "POST" });
    mostrarToast("Enviado a Telegram ✓");
  } catch (e) {
    mostrarToast(e.message || "No se pudo enviar", false);
  }
}

async function cargarEstadoTelegram() {
  try {
    const e = await api("/api/telegram/estado");
    $("tg-token").value = "";
    $("tg-token").placeholder = e.token_mostrado || "123456789:AAH...";
    $("tg-chat").value = e.chat_id || "";
    const estado = $("tg-estado");
    if (e.error) {
      estado.className = "alert alert-danger small py-1 mb-1";
      estado.textContent = "Estado: error — " + e.error;
    } else if (e.activo) {
      estado.className = "alert alert-success small py-1 mb-1";
      estado.textContent = "Estado: bot activo ✓";
    } else if (e.token_configurado) {
      estado.className = "alert alert-warning small py-1 mb-1";
      estado.textContent = "Estado: token guardado, bot en espera de desbloqueo";
    } else {
      estado.className = "alert alert-info small py-1 mb-1";
      estado.textContent = "Estado: sin configurar";
    }
    const hint = $("tg-ultimo-chat");
    if (e.ultimo_chat) {
      hint.textContent = "Último chat que escribió al bot: " +
        (e.ultimo_nombre || "?") + " (" + e.ultimo_chat + ")";
      $("tg-autorizar").disabled = false;
    } else {
      hint.textContent = "Sin mensajes recibidos todavía. Escríbele algo a tu bot y aparecerá aquí su chat.";
      $("tg-autorizar").disabled = true;
    }
  } catch (e) {
    mostrarToast(e.message, false);
  }
}

async function guardarConfigTelegram() {
  const body = { chat_id: $("tg-chat").value.trim() };
  if ($("tg-token").value.trim()) {
    body.token = $("tg-token").value.trim();
  }
  try {
    await api("/api/telegram/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    mostrarToast("Configuración guardada ✓");
    cargarEstadoTelegram();
  } catch (e) {
    mostrarToast(e.message, false);
  }
}

async function probarTelegram() {
  try {
    const r = await api("/api/telegram/probar", { method: "POST" });
    if (r.ok) {
      mostrarToast("Mensaje de prueba enviado ✓");
    } else {
      mostrarToast(r.error || "No se pudo enviar", false);
    }
  } catch (e) {
    mostrarToast(e.message, false);
  }
}

function usarChatDetectado() {
  // el id detectado se pide al servidor: reutilizamos el estado ya cargado
  api("/api/telegram/estado").then((est) => {
    if (est.ultimo_chat) {
      $("tg-chat").value = String(est.ultimo_chat);
      guardarConfigTelegram();
    } else {
      mostrarToast("Aún no hay chat detectado: escríbele a tu bot", false);
    }
  }).catch((err) => mostrarToast(err.message, false));
}

/* ================= tema claro/oscuro ================= */
function temaActual() {
  return document.documentElement.getAttribute("data-bs-theme") || "light";
}

function aplicarTema(tema) {
  document.documentElement.setAttribute("data-bs-theme", tema);
  localStorage.setItem("tema", tema);
  $("btn-tema").innerHTML =
    tema === "dark" ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
}

/* ================= eventos ================= */
function conectarEventos() {
  $("btn-entrar").addEventListener("click", entrar);
  $("btn-crear").addEventListener("click", crearCaja);
  $("btn-nueva").addEventListener("click", abrirNueva);
  $("btn-guardar").addEventListener("click", guardar);
  $("btn-exportar").addEventListener("click", exportar);
  $("btn-clave").addEventListener("click", () => {
    bootstrap.Modal.getOrCreateInstance($("modalClave")).show();
  });
  $("btn-cambiar-clave").addEventListener("click", cambiarClave);
  $("btn-cerrar").addEventListener("click", cerrarSesion);
  $("btn-config").addEventListener("click", () => {
    bootstrap.Modal.getOrCreateInstance($("modalConfig")).show();
    cargarEstadoTelegram();
  });
  $("tg-guardar").addEventListener("click", guardarConfigTelegram);
  $("tg-probar").addEventListener("click", probarTelegram);
  $("tg-autorizar").addEventListener("click", usarChatDetectado);
  $("btn-tema").addEventListener("click", () => {
    aplicarTema(temaActual() === "dark" ? "light" : "dark");
  });

  // Generador de contrasenas
  $("btn-gen-nav").addEventListener("click", () => abrirGenerador("solo"));
  $("btn-generador").addEventListener("click", () => abrirGenerador("cuenta"));
  $("gen-plataforma").addEventListener("change", aplicarPreset);
  ["gen-largo", "gen-mayus", "gen-minus", "gen-nums", "gen-simbolos", "gen-ambiguos"]
    .forEach((id) => $(id).addEventListener("input", () => refrescarGenerador(true)));
  $("gen-otra").addEventListener("click", refrescarGenerador);
  $("gen-copiar").addEventListener("click", async () => {
    const pwd = $("gen-resultado").value;
    if (!pwd) return;
    await navigator.clipboard.writeText(pwd);
    mostrarToast("Contraseña copiada ✓");
  });
  $("gen-usar").addEventListener("click", () => {
    const pwd = $("gen-resultado").value;
    if (!pwd) return;
    if (modoGenerador === "cuenta") {
      $("campo-contrasena").value = pwd;
      bootstrap.Modal.getInstance($("modalGenerador")).hide();
      mostrarToast("Contraseña aplicada a la cuenta ✓");
    } else {
      navigator.clipboard.writeText(pwd)
        .then(() => mostrarToast("Contraseña copiada ✓"))
        .catch(() => mostrarToast("No se pudo copiar", false));
    }
  });
  $("btn-ver-clave").addEventListener("click", () => {
    const i = $("campo-contrasena");
    const ver = i.type === "password";
    i.type = ver ? "text" : "password";
    $("btn-ver-clave").innerHTML = `<i class="bi ${ver ? "bi-eye-slash" : "bi-eye"}"></i>`;
  });

  // Enter en el login
  $("clave-entrar").addEventListener("keydown", (e) => {
    if (e.key === "Enter") entrar();
  });
  $("clave-confirma").addEventListener("keydown", (e) => {
    if (e.key === "Enter") crearCaja();
  });
  // Enter en el modal de cuenta
  $("modalCuenta").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.target.matches("textarea")) {
      e.preventDefault();
      guardar();
    }
  });

  // Busqueda con retardo (sin parpadeo)
  $("campo-buscar").addEventListener("input", () => {
    filtro = $("campo-buscar").value;
    clearTimeout(timerBusqueda);
    timerBusqueda = setTimeout(render, 180);
  });

  // Ordenar al hacer clic en el encabezado
  document.querySelectorAll("thead th[data-col]").forEach((th) => {
    th.addEventListener("click", () => ordenar(th.dataset.col));
  });

  // Autocompletado de dominios + autorelleno
  $("campo-correo").addEventListener("input", actualizarDatalist);
  $("campo-correo").addEventListener("blur", autorellenar);
}

/* ================= arranque ================= */
async function init() {
  conectarEventos();
  cargarConfigGen(); // configuración recordada del generador
  aplicarTema(temaActual()); // deja el icono del boton segun el tema guardado
  try {
    const est = await api("/api/estado");
    mostrarLogin(!est.vault);
  } catch (e) {
    $("login-subtitulo").textContent = "No se pudo conectar con el servidor local.";
    $("form-entrar").classList.add("d-none");
    $("form-crear").classList.add("d-none");
  }
}

document.addEventListener("DOMContentLoaded", init);
