MAILVAULT
=========

Boveda cifrada para tus cuentas de correo (nombre de cuenta, correo,
usuario, contrasena, servidor y notas).

Es una aplicacion web local: la interfaz usa Bootstrap (iconos
Bootstrap Icons) y Python es el backend. Tus datos se guardan CIFRADOS
(ChaCha20 + PBKDF2, sin dependencias externas) en el archivo
gestor_datos.enc: no se pueden leer a simple vista.

COMO INICIARLO
--------------
Doble clic en Iniciar.bat
  - Se abre una consola minimizada (el servidor local) y el navegador
    con la aplicacion en http://127.0.0.1:8610
  - PRIMERA VEZ: te pedira crear una clave de acceso. Con esa clave se
    cifran tus datos. Si la olvidas, NO hay forma de recuperarlos.
  - Para detener el servidor: cierra la ventana de consola.

SI YA USABAS LA VERSION ANTERIOR
--------------------------------
Al crear la clave por primera vez, la aplicacion importa sola las
cuentas de gestor_correos.db (la base anterior) y la renombra a
gestor_correos.db.bak. Puedes borrar ese .bak cuando quieras.

FUNCIONES
---------
- Tabla con columnas centradas y ordenable (clic en el encabezado)
- Buscador instantaneo (nombre, correo, usuario, servidor, notas)
- Autocompletado de dominios al escribir el correo + relleno automatico
  de usuario y servidor IMAP/SMTP (gmail, outlook, yahoo...)
- Contrasena con ojo para mostrar/ocultar
- Copiar correo, exportar CSV, cambiar clave, bloquear (boton candado)
- Boton de tema claro/oscuro (luna/sol) en la barra superior; se recuerda
  la preferencia (localStorage)

SEGURIDAD
---------
- El servidor solo escucha en 127.0.0.1 (tu PC), no es accesible desde
  la red ni desde otros dispositivos.
- Los datos viajan solo entre tu navegador y tu PC.
- El archivo gestor_datos.enc esta cifrado con tu clave (200.000
  iteraciones PBKDF2 + ChaCha20 + verificacion de integridad HMAC).
- El cifrado usa solo la biblioteca estandar de Python: funciona en
  cualquier PC con Python 3, sin instalar nada.

ARCHIVOS
--------
servidor.py   -> backend (servidor local + API)
cifrado.py    -> cifrado ChaCha20/PBKDF2
web/          -> interfaz (index.html, app.js, app.css)
assets/       -> Bootstrap e iconos (locales, funciona sin internet)
gestor_datos.enc -> tus datos cifrados (se crea la primera vez)

NOTA: si tienes copias en varias carpetas (Documentos y SD), cada
carpeta tiene su propia caja cifrada. Usa una sola como principal.
