@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    python cuestionario_ensayo.py
) else (
    py -3 cuestionario_ensayo.py
)
if errorlevel 1 (
    echo Consulta README.md para instalar Python y las dependencias.
    pause
)
