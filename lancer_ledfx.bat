@echo off
setlocal
title LedFx (sources)
pushd "%~dp0"

rem Config de dev separee : ne touche jamais a %APPDATA%\.ledfx (LedFx 2.1.9)
set "CONFIG_DIR=%~dp0dev_config"
rem 8888 est pris par LedFx 2.1.9
set "PORT=8899"
rem Port HTTPS pour le telephone (Pinceau LED) ; 8443 est pris par ThermoDash
set "PORT_S=8900"

if not exist ".venv\Scripts\python.exe" (
    echo [ERREUR] Environnement .venv introuvable dans %~dp0
    echo Il faut d'abord installer les dependances ^(uv sync^).
    pause
    exit /b 1
)

rem Passerelle iCUE (icue_bridge\) : envoie les effets aux peripheriques Corsair.
rem Elle demarre dans sa propre fenetre, sauf si elle tourne deja (port du clavier pris).
rem START_BRIDGE=0 pour lancer LedFx seul ; BRIDGE_MODE : unique, group ou fusion.
set "START_BRIDGE=1"
set "BRIDGE_MODE=unique"
set "BRIDGE_PORT=6477"
if "%START_BRIDGE%"=="1" (
    netstat -ano -p UDP | findstr /C:":%BRIDGE_PORT% " >nul
    if errorlevel 1 (
        echo Lancement de la passerelle iCUE ^(mode %BRIDGE_MODE%^)...
        start "LedFx iCUE Bridge" /min cmd /c ""%~dp0icue_bridge\lancer_bridge.bat" --mode %BRIDGE_MODE%"
    ) else (
        echo La passerelle iCUE tourne deja.
    )
)

rem Deja lance (double-clic de trop) : on ouvre juste l'interface au lieu d'un 2e LedFx
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo LedFx tourne deja sur le port %PORT% : ouverture de l'interface web.
    start "" "http://localhost:%PORT%"
    popd
    exit /b 0
)

rem Sans argument : ouvre l'interface web. Avec arguments : ils remplacent --open-ui
rem   ex. lancer_ledfx.bat -v          (logs detailles)
rem       lancer_ledfx.bat --pause-all (demarre sans effets actifs)
set "ARGS=--open-ui"
if not "%~1"=="" set "ARGS=%*"

rem Certificat HTTPS du telephone : les capteurs de mouvement exigent HTTPS.
rem Ne change rien s'il est a jour ; le reemet si l'adresse IP du PC a change.
".venv\Scripts\python.exe" tools\phone_cert.py "%CONFIG_DIR%"
if errorlevel 1 echo [ATTENTION] Certificat HTTPS non cree : le telephone n'aura que le mode Glisser.
set "LAN_IP="
rem "call" : sinon cmd retire le premier guillemet d'une commande for /f qui commence par un guillemet
for /f "usebackq delims=" %%i in (`call ".venv\Scripts\python.exe" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('192.168.0.1', 9)); print(s.getsockname()[0])"`) do set "LAN_IP=%%i"

echo Lancement de LedFx depuis les sources
echo   Config : %CONFIG_DIR%
echo   Web    : http://localhost:%PORT%
if defined LAN_IP echo   Phone  : https://%LAN_IP%:%PORT_S%/phone
echo   Ctrl+C pour arreter
echo.

rem --offline : pas de rapports Sentry vers LedFx ni de verification de mise a jour
".venv\Scripts\python.exe" -m ledfx -c "%CONFIG_DIR%" -p %PORT% --port_secure %PORT_S% --offline %ARGS%
set "CODE=%ERRORLEVEL%"

popd
if not "%CODE%"=="0" (
    echo.
    echo LedFx s'est arrete avec le code %CODE%. Journal : %CONFIG_DIR%\ledfx.log
    pause
)
exit /b %CODE%
