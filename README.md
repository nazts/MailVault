# MailVault 🔐✉️

Bóveda local y cifrada para tus cuentas de correo: guarda nombre, correo, usuario, contraseña, servidor y notas en un archivo cifrado, con interfaz web amigable.

> **100% local y sin dependencias**: la interfaz es web (Bootstrap 5) pero corre en tu propia PC, servida por Python. No hay nube, no hay servidores externos: tus datos nunca salen de tu máquina.

---

## 📖 Guía de uso

### Requisitos
- **Python 3** instalado (Windows, macOS o Linux). No instala nada más: usa solo la biblioteca estándar.
- Un navegador (Chrome, Edge, Firefox…).

### Primer arranque
1. **Windows**: doble clic en `Iniciar.bat` — se abre una consola minimizada (el servidor) y el navegador con la app.
   **Otros sistemas**: `python servidor.py` desde la carpeta del proyecto.
2. La app abre en `http://127.0.0.1:8610` (solo tu PC; si el puerto está ocupado usa 8611–8615 automáticamente).
3. **Primera vez**: te pide crear una **clave de acceso** (mín. 4 caracteres). Con esa clave se cifran tus datos.
   ⚠️ **Si la olvidas, no hay forma de recuperarlos.** Es la base del diseño: nadie más puede abrir tu bóveda.

### Uso diario
| Acción | Cómo |
|---|---|
| Crear cuenta | Botón **+ Nueva cuenta** → llenas los campos → **Guardar** (el formulario se limpia solo para la siguiente) |
| Editar | Clic en la fila de la tabla (o el lápiz) |
| Eliminar | Icono 🗑 (pide confirmación) |
| Buscar | Escribe en la lupa: busca en nombre, correo, usuario, servidor **y notas** |
| Ordenar | Clic en el encabezado **Cuenta** o **Correo** (segundo clic invierte) |
| Copiar correo | Icono ⧉ de la fila → queda en el portapapeles |
| Ver contraseña | Ojo 👁 en el campo Contraseña |
| **Generar contraseña** | Botón 🎲 de la barra superior (uso suelto) o el 🎲 junto al campo Contraseña (te la aplica directo). Elige longitud y tipos de caracteres, o usa una **plantilla por plataforma** (TikTok, Instagram, Facebook, YouTube, Twitch) que aplica la longitud recomendada según los requisitos de cada una; la configuración se recuerda |
| Exportar | Botón **CSV** → descarga `mis_cuentas.csv` (abre en Excel) |
| Cambiar clave | Icono 🔑 |
| Bloquear | Icono candado → vuelve a pedir la clave |
| Tema claro/oscuro | Botón 🌙/☀️ de la barra (se recuerda la preferencia) |

### Autocompletado inteligente
Escribe un correo con un **dominio conocido** (gmail.com, outlook.com, hotmail.com, yahoo.com, icloud.com, proton.me, zoho.com…) y la app te sugiere el dominio mientras escribes. Al salir del campo, si el dominio es conocido **rellena sola el usuario y el servidor IMAP/SMTP**.

### Detener la app
Cierra la **ventana de consola** del servidor. (El navegador puede quedar abierto; la app deja de responder al cerrar la consola.)

---

## 📦 Qué archivos mover (copiar la app a otra PC / USB)

La app es **portable**: copia la carpeta a una USB/SD y úsala en cualquier PC con Python 3.

### Obligatorios (sin estos no funciona)
| Archivo | Función |
|---|---|
| `servidor.py` | El backend (servidor local + API) |
| `cifrado.py` | El cifrado ChaCha20/PBKDF2 |
| `web/` (carpeta completa) | La interfaz (index.html, app.js, app.css) |
| `assets/` (carpeta completa) | Bootstrap e iconos — **locales**, funciona sin internet |
| `Iniciar.bat` | Lanzador de Windows (opcional en otros sistemas) |

### Se generan solos (no hace falta copiarlos)
| Archivo | Qué es |
|---|---|
| `gestor_datos.enc` | **Tu bóveda cifrada** — se crea la primera vez que pones tu clave |
| `gestor_correos.db.bak` | Respaldo de la versión anterior (si migraste), puedes borrarlo |
| `__pycache__/` | Caché de Python, se regenera, no se copia |

### ¿Y mis datos?
- **Para empezar de cero** en la otra PC: copia solo los obligatorios y crea la bóveda ahí (con tu clave).
- **Para llevar tus cuentas**: copia también `gestor_datos.enc` **y recuerda tu clave** — sin la clave la bóveda es ilegible a propósito.
- Cada carpeta es una **bóveda independiente**: no mezcles `gestor_datos.enc` entre copias distintas.

---

## 🔒 Seguridad

- El servidor solo escucha en **127.0.0.1** (tu PC) — no es accesible desde la red ni desde otros dispositivos.
- Datos cifrados estilo **cebolla v2**: de 3 a 5 capas de **ChaCha20** (RFC 8439, verificado con los vectores oficiales), cada capa con una clave derivada de la anterior y un nonce propio, aplicadas en **orden aleatorio** (la permutación se guarda para pelarlas en orden inverso). La clave maestra se deriva con **PBKDF2-HMAC-SHA256 (200.000 iteraciones)** y un **HMAC** final detecta clave incorrecta o archivo alterado.
- Cada guardado re-cifra con **nuevas capas, nuevos nonces y nuevo orden** — dos archivos de la misma bóveda nunca son iguales.
- El archivo `gestor_datos.enc` no se puede leer a simple vista ni sin tu clave.
- Las cajas creadas con la versión anterior (v1) se migran solas al formato cebolla al abrirlas.
- Cero dependencias externas: el cifrado usa únicamente la biblioteca estándar de Python.

---

## 🛠 Estructura del proyecto

```
MailVault/
├── servidor.py        # Backend: servidor local + API JSON
├── cifrado.py         # Cifrado ChaCha20/PBKDF2 (con vectores RFC 8439 de prueba)
├── web/               # Interfaz (index.html, app.js, app.css)
├── assets/            # Bootstrap 5 e Bootstrap Icons (locales)
├── Iniciar.bat        # Lanzador Windows
├── LICENSE            # MIT
└── README.md
```

---

## ⚖️ Licencia

**MIT License** — libre de usar, modificar y distribuir, incluso comercialmente, siempre que se conserve el aviso de copyright.

Copyright (c) 2026 Luis Martinez · Ver [LICENSE](LICENSE)
