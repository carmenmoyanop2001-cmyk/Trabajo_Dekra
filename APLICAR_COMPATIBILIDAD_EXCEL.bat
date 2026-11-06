@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    python compatibilidad_excel2016.py
) else (
    py -3 compatibilidad_excel2016.py
)
if errorlevel 1 (
    echo No se ha podido ejecutar la herramienta. Utiliza el Python con el que ejecutas el cuestionario.
    pause
)
