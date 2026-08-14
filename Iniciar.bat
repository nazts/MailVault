@echo off
title MailVault - servidor local
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    start "MailVault" /min python "%~dp0servidor.py"
    exit /b
)
py -3 "%~dp0servidor.py"
pause
