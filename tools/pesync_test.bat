@echo off
title PESync - Prueba de Conexión
cd /d "%~dp0"
cd ..
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py test
) else (
    echo [ERROR] No se encontro el entorno virtual ['.venv'].
    pause
)
