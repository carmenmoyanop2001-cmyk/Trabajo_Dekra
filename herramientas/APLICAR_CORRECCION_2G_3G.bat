@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python actualizar_programa_2g3g.py
) else (
    py -3 actualizar_programa_2g3g.py
)
echo.
pause
