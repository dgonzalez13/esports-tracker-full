@echo off
setlocal

cd /d C:\apuestas

REM =========================
REM FECHA A REPARAR
REM =========================

set REPAIR_DATE=%1

echo.
echo =====================================
echo ACTUALIZANDO REPOSITORIO
echo =====================================
echo.

git pull --rebase origin main

if errorlevel 1 (
    echo.
    echo ERROR DURANTE EL REBASE
    pause
    exit /b 1
)

echo.
echo =====================================
echo REPARANDO EADRIATIC
echo =====================================
echo.

if "%REPAIR_DATE%"=="" (
    echo Reparando dia anterior...
    python repair_eadriatic_day.py
    set COMMIT_MSG=Repair Eadriatic previous day
) else (
    echo Reparando fecha %REPAIR_DATE%...
    python repair_eadriatic_day.py %REPAIR_DATE%
    set COMMIT_MSG=Repair Eadriatic %REPAIR_DATE%
)

if errorlevel 1 (
    echo.
    echo ERROR EN REPAIR
    pause
    exit /b 1
)

echo.
echo =====================================
echo ANALIZANDO DATOS
echo =====================================
echo.

python analyze_eadriatic.py

if errorlevel 1 (
    echo.
    echo ERROR EN ANALYZE
    pause
    exit /b 1
)

echo.
echo =====================================
echo GENERANDO WEB
echo =====================================
echo.

python web_tracker\generate_site.py

if errorlevel 1 (
    echo.
    echo ERROR GENERANDO WEB
    pause
    exit /b 1
)

echo.
echo =====================================
echo SUBIENDO CAMBIOS
echo =====================================
echo.

git add .

git diff --cached --quiet

if errorlevel 1 (
    git commit -m "%COMMIT_MSG%"
    git push
) else (
    echo No hay cambios para subir.
)

echo.
echo =====================================
echo FINALIZADO
echo =====================================
echo.

pause