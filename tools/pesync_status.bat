@echo off
title PESync - Estado del Backup
cd /d "%~dp0"
cd ..
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py status
) else (
    echo [ERROR] No se encontro el entorno virtual ['.venv'].
    pause
)
