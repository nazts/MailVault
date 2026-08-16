# -*- coding: utf-8 -*-
"""MailVault - servidor local (backend) + API JSON + bot de Telegram.

Iniciar.bat / Iniciar.sh lanzan este servidor en http://127.0.0.1:8610
(solo local, no accesible desde la red) y abren el navegador. Los datos
se guardan cifrados (ChaCha20 capas + PBKDF2) en gestor_datos.enc.

Bot de Telegram:
  - El token del bot y el chat autorizado se configuran en la interfaz web
    (Configuracion -> Telegram) y se guardan cifrados dentro de la boveda.
  - El bot responde SOLO al chat autorizado y funciona mientras la boveda
    este desbloqueada.
  - Comandos: /lista, /ver <texto|id>, /nueva a|b|c|d|e|f, /ayuda

API:
  GET  /api/estado            -> {"vault": bool}
  POST /api/crear             -> {"clave": "..."}        (primera vez)
  POST /api/desbloquear       -> {"clave": "..."}
  POST /api/cerrar
  POST /api/clave             -> {"actual": "...", "nueva": "..."}
  GET  /api/cuentas           (requiere desbloqueo)
  POST /api/cuentas           crear
  PUT  /api/cuentas/<id>      actualizar
  DELETE /api/cuentas/<id>    eliminar
  POST /api/cuentas/<id>/telegram   enviar la cuenta al chat autorizado
  GET  /api/exportar          CSV
  GET  /api/telegram/estado
  POST /api/telegram/config   {"token": "...", "chat_id": "..."}
  POST /api/telegram/probar
"""

import csv
import io
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cifrado

RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(RUTA_BASE, "gestor_datos.enc")
RUTA_DB_VIEJA = os.path.join(RUTA_BASE, "gestor_correos.db")
PUERTO_INICIAL = 8610

CAMPOS = ("nombre", "correo", "usuario", "contrasena", "servidor", "notas")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{metodo}"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class BotTelegram(threading.Thread):
    """Polling de la API de Telegram en segundo plano (long polling)."""

    def __init__(self, gestor):
        super().__init__(daemon=True, name="bot-telegram")
        self.gestor = gestor
        self.detener = threading.Event()
        self.offset = 0
        self.error = None
        self.ultimo_chat = None
        self.ultimo_nombre = None

    def _llamar(self, metodo, datos=None, timeout=35):
        token = (self.gestor.config.get("bot_token") or "").strip()
        url = TELEGRAM_API.format(token=token, metodo=metodo)
        if datos:
            cuerpo = urllib.parse.urlencode(datos).encode()
            req = urllib.request.Request(url, data=cuerpo)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _enviar(self, chat_id, texto):
        try:
            self._llamar("sendMessage",
                         {"chat_id": chat_id, "text": texto}, timeout=15)
            return True
        except Exception:
            return False

    def procesar(self, texto):
        """Comandos del bot -> texto de respuesta (logica pura y testeable)."""
        t = (texto or "").strip()
        if not t:
            return ""
        partes = t.split(None, 1)
        cmd = partes[0].lower()
        resto = (partes[1] if len(partes) > 1 else "").strip()
        g = self.gestor

        if cmd in ("/start", "/ayuda", "/help"):
            return ("MailVault 🔐\n"
                    "/lista — ver tus cuentas\n"
                    "/ver <texto o id> — buscar una cuenta (con contraseña)\n"
                    "/nueva nombre | correo | usuario | contraseña | servidor | notas — guardar")

        if cmd == "/lista":
            cuentas = g.listar()
            if not cuentas:
                return "No hay cuentas guardadas."
            lineas = ["%d. %s (%s)" % (c["id"], c["nombre"] or "?",
                                       c["correo"] or "")
                      for c in cuentas]
            return "\n".join(lineas[:25])

        if cmd == "/ver":
            if not resto:
                return "Uso: /ver <texto o id>"
            cuentas = g.listar()
            if resto.isdigit():
                coinciden = [c for c in cuentas if c["id"] == int(resto)]
            else:
                r = resto.lower()
                coinciden = [c for c in cuentas
                             if r in (c["nombre"] or "").lower()
                             or r in (c["correo"] or "").lower()]
            if not coinciden:
                return "Sin resultados para «%s»." % resto
            if len(coinciden) == 1:
                c = coinciden[0]
                return ("%s\n📧 %s\n👤 %s\n🔑 %s\n🖥 %s\n📝 %s" % (
                    c["nombre"] or "—", c["correo"] or "—",
                    c["usuario"] or "—", c["contrasena"] or "—",
                    c["servidor"] or "—", c["notas"] or "—"))
            lineas = ["Hay %d coincidencias, afina con más texto o usa el id:"
                      % len(coinciden)]
            lineas += ["%d. %s" % (c["id"], c["nombre"] or c["correo"])
                       for c in coinciden[:10]]
            return "\n".join(lineas)

        if cmd == "/nueva":
            campos = [x.strip() for x in resto.split("|")]
            if not campos or not campos[0]:
                return ("Uso: /nueva nombre | correo | usuario | contraseña "
                        "| servidor | notas")
            datos = {}
            for i, campo in enumerate(CAMPOS):
                datos[campo] = campos[i] if i < len(campos) else ""
            if not datos["nombre"] and not datos["correo"]:
                return "Pon al menos el nombre o el correo."
            c = g.crear(datos)
            return "Guardada ✓ (id %d)" % c["id"]

        return "Comando no reconocido. Envía /ayuda."

    def run(self):
        while not self.detener.is_set():
            g = self.gestor
            if not g.desbloqueado or not (g.config.get("bot_token") or ""):
                self.error = None
                self.detener.wait(2)
                continue
            try:
                datos = self._llamar("getUpdates", {
                    "timeout": 30,
                    "offset": self.offset,
                    "allowed_updates": "message",
                })
                self.error = None
                for upd in datos.get("result", []):
                    self.offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    chat = msg.get("chat") or {}
                    chat_id = chat.get("id")
                    if not chat_id:
                        continue
                    self.ultimo_chat = chat_id
                    self.ultimo_nombre = (chat.get("first_name")
                                          or chat.get("username") or "?")
                    texto = msg.get("text") or ""
                    autorizado = str(g.config.get("chat_id") or "").strip()
                    if not autorizado:
                        # onboarding: sin chat autorizado, ensena al dueno el id
                        self._enviar(chat_id, "Tu chat ID es %s. "
                                     "Autorízalo en MailVault → "
                                     "Configuración → Telegram." % chat_id)
                        continue
                    if str(chat_id) != autorizado:
                        continue
                    resp = self.procesar(texto)
                    if resp:
                        self._enviar(chat_id, resp)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self.error = "token inválido (401)"
                elif e.code == 409:
                    self.error = "conflicto: otra instancia del bot ya corre"
                else:
                    self.error = "error HTTP %s" % e.code
                self.detener.wait(10)
            except Exception as e:
                self.error = str(e)
                self.detener.wait(5)

    def detener_bot(self):
        self.detener.set()


class Gestor:
    """Boveda en memoria; se persiste cifrada en cada cambio."""

    def __init__(self):
        self.lock = threading.RLock()
        self.cuentas = []
        self.config = {"bot_token": "", "chat_id": ""}
        self.clave = None
        self.bot = BotTelegram(self)

    @property
    def tiene_caja(self):
        return os.path.exists(RUTA_DATOS)

    @property
    def desbloqueado(self):
        return self.clave is not None

    def _arrancar_bot(self):
        if not self.bot.is_alive():
            self.bot.start()

    def crear_caja(self, clave):
        with self.lock:
            self.cuentas = self._migrar_sqlite()
            self.config = {"bot_token": "", "chat_id": ""}
            self.clave = clave
            self._guardar()
            self._arrancar_bot()

    def desbloquear(self, clave):
        with self.lock:
            datos = cifrado.descifrar_archivo(RUTA_DATOS, clave)
            obj = json.loads(datos.decode("utf-8"))
            viejo_formato = isinstance(obj, list)  # formato viejo: solo cuentas
            if viejo_formato:
                obj = {"cuentas": obj, "config": {"bot_token": "", "chat_id": ""}}
            self.cuentas = obj.get("cuentas") or []
            self.config = obj.get("config") or {"bot_token": "", "chat_id": ""}
            self.clave = clave
            # migrar a formato nuevo y/o a cifrado cebolla v2
            if viejo_formato or cifrado.formato_archivo(RUTA_DATOS) != "v2":
                self._guardar()
            self._arrancar_bot()

    def cerrar(self):
        with self.lock:
            self.cuentas = []
            self.config = {"bot_token": "", "chat_id": ""}
            self.clave = None

    def cambiar_clave(self, actual, nueva):
        with self.lock:
            cifrado.descifrar_archivo(RUTA_DATOS, actual)  # valida la actual
            self.clave = nueva
            self._guardar()

    def _guardar(self):
        blob = json.dumps({"cuentas": self.cuentas, "config": self.config},
                          ensure_ascii=False).encode("utf-8")
        cifrado.cifrar_archivo(RUTA_DATOS, blob, self.clave)

    def _migrar_sqlite(self):
        """Importa la base de la version anterior (gestor_correos.db), si existe."""
        if not os.path.exists(RUTA_DB_VIEJA):
            return []
        try:
            conn = sqlite3.connect(RUTA_DB_VIEJA)
            filas = conn.execute("SELECT * FROM cuentas").fetchall()
            conn.close()
        except Exception:
            return []
        cuentas = []
        for f in filas:
            if len(f) >= 7:
                id_, nombre, correo, usuario, contrasena, servidor, notas = f[:7]
            else:  # version vieja sin columna de contrasena
                id_, nombre, correo, usuario, servidor, notas = f[:6]
                contrasena = ""
            cuentas.append({"id": id_, "nombre": nombre or "",
                            "correo": correo or "", "usuario": usuario or "",
                            "contrasena": contrasena or "",
                            "servidor": servidor or "", "notas": notas or ""})
        if filas:
            try:
                os.rename(RUTA_DB_VIEJA, RUTA_DB_VIEJA + ".bak")
            except OSError:
                pass
        return cuentas

    def listar(self):
        with self.lock:
            return list(self.cuentas)

    def crear(self, d):
        with self.lock:
            nuevo = {"id": max((c["id"] for c in self.cuentas), default=0) + 1}
            for campo in CAMPOS:
                valor = d.get(campo) or ""
                nuevo[campo] = valor.strip() if campo != "contrasena" else valor
            self.cuentas.append(nuevo)
            self._guardar()
            return nuevo

    def actualizar(self, id_, d):
        with self.lock:
            for c in self.cuentas:
                if c["id"] == id_:
                    for campo in CAMPOS:
                        valor = d.get(campo) or ""
                        c[campo] = valor.strip() if campo != "contrasena" else valor
                    self._guardar()
                    return c
        return None

    def eliminar(self, id_):
        with self.lock:
            antes = len(self.cuentas)
            self.cuentas = [c for c in self.cuentas if c["id"] != id_]
            if len(self.cuentas) != antes:
                self._guardar()
                return True
        return False

    # ---------- Telegram ----------
    def estado_telegram(self):
        token = (self.config.get("bot_token") or "").strip()
        return {
            "token_configurado": bool(token),
            "token_mostrado": ("•••" + token[-4:]) if token else "",
            "chat_id": str(self.config.get("chat_id") or "").strip(),
            "activo": bool(token) and self.desbloqueado,
            "ultimo_chat": self.bot.ultimo_chat,
            "ultimo_nombre": self.bot.ultimo_nombre,
            "error": self.bot.error,
        }

    def config_telegram(self, token=None, chat_id=None):
        with self.lock:
            if token:
                self.config["bot_token"] = token.strip()
            if chat_id is not None:
                self.config["chat_id"] = str(chat_id).strip()
            self._guardar()
            self._arrancar_bot()
            return self.estado_telegram()

    def probar_telegram(self):
        chat = str(self.config.get("chat_id") or "").strip()
        if not chat:
            return False, "primero configura el chat autorizado"
        token = (self.config.get("bot_token") or "").strip()
        if not token:
            return False, "primero configura el token del bot"
        ok = self.bot._enviar(chat, "✅ MailVault conectado. Prueba OK.")
        return ok, ("" if ok else "no se pudo enviar (revisa token y chat)")

    def enviar_telegram(self, id_):
        c = next((x for x in self.cuentas if x["id"] == id_), None)
        if c is None:
            return False, "cuenta no encontrada"
        chat = str(self.config.get("chat_id") or "").strip()
        if not chat:
            return False, "primero configura el chat autorizado"
        token = (self.config.get("bot_token") or "").strip()
        if not token:
            return False, "primero configura el token del bot"
        texto = ("%s\n📧 %s\n👤 %s\n🔑 %s\n🖥 %s\n📝 %s" % (
            c["nombre"] or "—", c["correo"] or "—", c["usuario"] or "—",
            c["contrasena"] or "—", c["servidor"] or "—", c["notas"] or "—"))
        ok = self.bot._enviar(chat, texto)
        return ok, ("" if ok else "no se pudo enviar")


gestor = Gestor()


class Handler(BaseHTTPRequestHandler):
    server_version = "MailVault/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.address_string(), fmt % args), flush=True)

    # ---------- helpers ----------
    def _json(self, codigo, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _cuerpo(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0:
            return {}
        return json.loads(self.rfile.read(largo).decode("utf-8"))

    def _archivo(self, ruta):
        try:
            with open(ruta, "rb") as f:
                b = f.read()
        except OSError:
            self.send_error(404, "No encontrado")
            return
        ext = os.path.splitext(ruta)[1].lower()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _exigir(self):
        if not gestor.desbloqueado:
            self._json(401, {"error": "bloqueado"})
            return False
        return True

    def _id_ruta(self, ruta):
        try:
            return int(ruta.split("/")[-1])
        except (ValueError, IndexError):
            return None

    # ---------- GET ----------
    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            self._archivo(os.path.join(RUTA_BASE, "web", "index.html"))
        elif ruta == "/app.js":
            self._archivo(os.path.join(RUTA_BASE, "web", "app.js"))
        elif ruta == "/app.css":
            self._archivo(os.path.join(RUTA_BASE, "web", "app.css"))
        elif ruta.startswith("/assets/"):
            self._archivo(os.path.join(RUTA_BASE, ruta.lstrip("/")))
        elif ruta == "/api/estado":
            self._json(200, {"vault": gestor.tiene_caja})
        elif ruta == "/api/cuentas":
            if self._exigir():
                self._json(200, gestor.listar())
        elif ruta == "/api/exportar":
            self._exportar()
        elif ruta == "/api/telegram/estado":
            if self._exigir():
                self._json(200, gestor.estado_telegram())
        else:
            self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        ruta = urlparse(self.path).path
        try:
            cuerpo = self._cuerpo()
        except Exception:
            self._json(400, {"error": "JSON invalido"})
            return

        if ruta == "/api/crear":
            clave = (cuerpo.get("clave") or "").strip()
            if len(clave) < 4:
                self._json(400, {"error": "la clave debe tener al menos 4 caracteres"})
                return
            if gestor.tiene_caja:
                self._json(409, {"error": "la caja ya existe"})
                return
            gestor.crear_caja(clave)
            self._json(200, {"cuentas": gestor.listar()})
        elif ruta == "/api/desbloquear":
            clave = (cuerpo.get("clave") or "").strip()
            try:
                gestor.desbloquear(clave)
                self._json(200, {"cuentas": gestor.listar()})
            except Exception:
                self._json(401, {"error": "clave incorrecta"})
        elif ruta == "/api/cerrar":
            gestor.cerrar()
            self._json(200, {"ok": True})
        elif ruta == "/api/cuentas":
            if self._exigir():
                self._json(201, gestor.crear(cuerpo))
        elif ruta == "/api/clave":
            if self._exigir():
                try:
                    gestor.cambiar_clave(cuerpo.get("actual", ""),
                                         cuerpo.get("nueva", ""))
                    self._json(200, {"ok": True})
                except Exception:
                    self._json(401, {"error": "clave actual incorrecta"})
        elif ruta == "/api/telegram/config":
            if self._exigir():
                self._json(200, gestor.config_telegram(
                    token=cuerpo.get("token"),
                    chat_id=cuerpo.get("chat_id")))
        elif ruta == "/api/telegram/probar":
            if self._exigir():
                ok, err = gestor.probar_telegram()
                self._json(200, {"ok": ok, "error": err})
        elif ruta.startswith("/api/cuentas/") and ruta.endswith("/telegram"):
            if self._exigir():
                try:
                    id_ = int(ruta.split("/")[-2])  # /api/cuentas/<id>/telegram
                except (ValueError, IndexError):
                    id_ = None
                if id_ is None:
                    self._json(400, {"error": "id invalido"})
                    return
                ok, err = gestor.enviar_telegram(id_)
                self._json(200 if ok else 400, {"ok": ok, "error": err})
        else:
            self.send_error(404)

    # ---------- PUT / DELETE ----------
    def do_PUT(self):
        ruta = urlparse(self.path).path
        if ruta.startswith("/api/cuentas/") and not ruta.endswith("/telegram"):
            if not self._exigir():
                return
            id_ = self._id_ruta(ruta)
            if id_ is None:
                self._json(400, {"error": "id invalido"})
                return
            try:
                c = gestor.actualizar(id_, self._cuerpo())
            except Exception:
                self._json(400, {"error": "JSON invalido"})
                return
            if c:
                self._json(200, c)
            else:
                self._json(404, {"error": "no existe"})
        else:
            self.send_error(404)

    def do_DELETE(self):
        ruta = urlparse(self.path).path
        if ruta.startswith("/api/cuentas/"):
            if not self._exigir():
                return
            id_ = self._id_ruta(ruta)
            if id_ is None:
                self._json(400, {"error": "id invalido"})
                return
            if gestor.eliminar(id_):
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "no existe"})
        else:
            self.send_error(404)

    # ---------- exportar ----------
    def _exportar(self):
        if not self._exigir():
            return
        salida = io.StringIO()
        w = csv.writer(salida)
        w.writerow(["Nombre", "Correo", "Usuario", "Contraseña", "Servidor", "Notas"])
        for c in gestor.listar():
            w.writerow([c["nombre"], c["correo"], c["usuario"], c["contrasena"],
                        c["servidor"], c["notas"]])
        b = ("\ufeff" + salida.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition",
                         'attachment; filename="mis_cuentas.csv"')
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


class ServidorLocal(ThreadingHTTPServer):
    # Puerto exclusivo: si ya hay otro MailVault corriendo en un puerto,
    # este no se cuela encima (evita respuestas mezcladas / 404).
    allow_reuse_address = False


def main():
    puerto = None
    servidor = None
    for p in range(PUERTO_INICIAL, PUERTO_INICIAL + 6):
        try:
            servidor = ServidorLocal(("127.0.0.1", p), Handler)
            puerto = p
            break
        except OSError:
            continue
    if servidor is None:
        print("No se pudo abrir un puerto libre (8610-8615).")
        print("Cierra otro servidor y vuelve a intentar.")
        input("Enter para salir...")
        return

    url = "http://127.0.0.1:%d" % puerto
    print("=" * 50)
    print("  MailVault (servidor local)")
    print("  Abre el navegador en: %s" % url)
    print("  Solo accesible desde esta PC (127.0.0.1).")
    print("  Para DETENER el servidor cierra esta ventana.")
    print("=" * 50, flush=True)

    if not os.environ.get("GESTOR_NO_BROWSER"):
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
