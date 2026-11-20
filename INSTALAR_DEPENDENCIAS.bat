@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    python -m pip install -r requirements.txt
) else (
    py -3 -m pip install -r requirements.txt
)
if errorlevel 1 (
    echo No se han podido instalar las dependencias. Comprueba que Python esta instalado.
) else (
    echo Dependencias instaladas. Abre INICIAR_CUESTIONARIO.bat.
)
pause
