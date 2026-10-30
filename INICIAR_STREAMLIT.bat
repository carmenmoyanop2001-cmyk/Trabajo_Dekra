@echo off
setlocal
pushd "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    set "SAR_PYTHON=python"
) else (
    set "SAR_PYTHON=py -3"
)
%SAR_PYTHON% -c "import streamlit, lxml" >nul 2>&1
if errorlevel 1 (
    echo Instala primero las dependencias desde esta carpeta:
    echo %SAR_PYTHON% -m pip install -r requirements_streamlit.txt
    pause
    popd
    exit /b 1
)
%SAR_PYTHON% -m streamlit run app_streamlit.py --server.address=127.0.0.1
if errorlevel 1 pause
popd
