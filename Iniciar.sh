#!/usr/bin/env bash
# MailVault - lanzador para Linux / macOS
# Uso: doble clic (si el gestor de archivos lo permite) o:
#   chmod +x Iniciar.sh && ./Iniciar.sh
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "MailVault necesita Python 3 y no está instalado."
    echo "Instálalo con tu gestor de paquetes (apt, dnf, pacman, brew...)."
    read -r -p "Enter para salir..."
    exit 1
fi

echo "MailVault - servidor local (127.0.0.1:8610)"
echo "Para DETENERLO: Ctrl+C en esta ventana."
exec "$PY" servidor.py
