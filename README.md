# MailVault 🔐✉️

Bóveda local y cifrada para tus cuentas de correo: guarda nombre, correo, usuario, contraseña, servidor y notas en un archivo cifrado, con interfaz web amigable.

## Características

- **Interfaz web** con Bootstrap 5 + Bootstrap Icons (assets 100% locales, funciona sin internet)
- **Backend Python** solo con biblioteca estándar — cero dependencias, corre en cualquier PC con Python 3
- **Cifrado real**: ChaCha20 (RFC 8439) + PBKDF2 (200.000 iteraciones) + HMAC de integridad
- Tabla con columnas centradas y **ordenable** (clic en el encabezado)
- **Búsqueda instantánea** con autocompletado en el buscador
- **Autocompletado de dominios** al escribir el correo (gmail, outlook, yahoo…) con relleno automático de usuario y servidor IMAP/SMTP
- Contraseña con ojo para mostrar/ocultar
- Copiar correo, exportar CSV, cambiar clave, bloquear
- **Modo claro/oscuro** (se recuerda la preferencia)
- El servidor solo escucha en `127.0.0.1` — no accesible desde la red

## Cómo usarlo

1. `python servidor.py` (en Windows: doble clic en `Iniciar.bat`)
2. Se abre el navegador en `http://127.0.0.1:8610`
3. La primera vez creas tu **clave de acceso** — con ella se cifran tus datos. ⚠️ Si la olvidas no hay recuperación (así de seguro es).

## Seguridad

- Tus datos viven cifrados en `gestor_datos.enc` (no se leen a simple vista)
- Clave derivada con PBKDF2-HMAC-SHA256 (200.000 iteraciones), cifrado ChaCha20 verificado contra los vectores oficiales del RFC 8439
- El servidor solo escucha en localhost (127.0.0.1:8610)
- Sin dependencias externas: el cifrado usa únicamente la biblioteca estándar de Python

## Estructura

| Archivo | Función |
|---|---|
| `servidor.py` | Backend: servidor local + API JSON |
| `cifrado.py` | Cifrado ChaCha20/PBKDF2 (incluye vectores de prueba RFC 8439) |
| `web/` | Interfaz (HTML, CSS, JS) |
| `assets/` | Bootstrap e iconos (locales) |
| `Iniciar.bat` | Lanzador para Windows |

## Portabilidad

Copia la carpeta a una USB/SD y llévate tus cuentas a cualquier PC con Python 3. Cada carpeta es una bóveda independiente.
