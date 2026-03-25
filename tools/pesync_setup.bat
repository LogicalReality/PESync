@echo off
title PESync - Asistente de Configuración
cd /d "%~dp0"
cd ..
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py setup
) else (
    echo [ERROR] No se encontro el entorno virtual ['.venv'].
    pause
)
