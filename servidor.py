# -*- coding: utf-8 -*-
"""MailVault - servidor local (backend) + API JSON.

Iniciar.bat lanza este servidor en http://127.0.0.1:8610 (solo local,
no accesible desde la red) y abre el navegador. Los datos se guardan
cifrados (ChaCha20 + PBKDF2) en gestor_datos.enc.

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
  GET  /api/exportar          CSV
"""

import csv
import io
import json
import os
import sqlite3
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cifrado

RUTA_BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(RUTA_BASE, "gestor_datos.enc")
RUTA_DB_VIEJA = os.path.join(RUTA_BASE, "gestor_correos.db")
PUERTO_INICIAL = 8610

CAMPOS = ("nombre", "correo", "usuario", "contrasena", "servidor", "notas")

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


class Gestor:
    """Boveda en memoria; se persiste cifrada en cada cambio."""

    def __init__(self):
        self.lock = threading.RLock()
        self.cuentas = []
        self.clave = None

    @property
    def tiene_caja(self):
        return os.path.exists(RUTA_DATOS)

    @property
    def desbloqueado(self):
        return self.clave is not None

    def crear_caja(self, clave):
        with self.lock:
            self.cuentas = self._migrar_sqlite()
            self.clave = clave
            self._guardar()

    def desbloquear(self, clave):
        with self.lock:
            datos = cifrado.descifrar_archivo(RUTA_DATOS, clave)
            self.cuentas = json.loads(datos.decode("utf-8"))
            self.clave = clave

    def cerrar(self):
        with self.lock:
            self.cuentas = []
            self.clave = None

    def cambiar_clave(self, actual, nueva):
        with self.lock:
            cifrado.descifrar_archivo(RUTA_DATOS, actual)  # valida la actual
            self.clave = nueva
            self._guardar()

    def _guardar(self):
        blob = json.dumps(self.cuentas, ensure_ascii=False).encode("utf-8")
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

    def _id_ruta(self, ruta, prefijo):
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
        else:
            self.send_error(404)

    # ---------- PUT / DELETE ----------
    def do_PUT(self):
        ruta = urlparse(self.path).path
        if ruta.startswith("/api/cuentas/"):
            if not self._exigir():
                return
            id_ = self._id_ruta(ruta, "/api/cuentas/")
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
            id_ = self._id_ruta(ruta, "/api/cuentas/")
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
    # Puerto exclusivo: si ya hay otro Gestor corriendo en un puerto,
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
