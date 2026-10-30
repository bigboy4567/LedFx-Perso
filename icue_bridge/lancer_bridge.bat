@echo off
setlocal EnableExtensions
title LedFx iCUE Bridge
cd /d "%~dp0"

rem Find a Python 3 interpreter: the "py" launcher first, then "python".
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3 est introuvable. Installe-le depuis https://www.python.org/downloads/
    echo ^(coche "Add python.exe to PATH" pendant l'installation^).
    pause
    exit /b 1
)

rem Install dependencies on first run (or if they were removed).
%PY% -c "import cuesdk, psutil" >nul 2>nul
if errorlevel 1 (
    echo Installation des dependances...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Echec de l'installation des dependances.
        pause
        exit /b 1
    )
)

rem Extra arguments are forwarded, e.g.: lancer_bridge.bat --mode fusion
%PY% ledfx_icue_bridge.py %*
set "EXIT_CODE=%errorlevel%"

rem Exit code 75 = the bridge restarted itself in a new process: nothing to show here.
if not "%EXIT_CODE%"=="0" if not "%EXIT_CODE%"=="75" (
    echo.
    echo Le bridge s'est arrete avec le code %EXIT_CODE%. Details dans ledfx_icue_bridge.log
    pause
)
exit /b %EXIT_CODE%
