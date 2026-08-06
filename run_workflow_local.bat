@echo off
cd /d C:\apuestas

echo.
echo =====================================
echo EJECUTANDO GT
echo =====================================
python gtleagues_api.py
if errorlevel 1 goto :error

echo.
echo =====================================
echo EJECUTANDO EADRIATIC
echo =====================================
python eadriatic_leagues.py
if errorlevel 1 goto :error

echo.
echo =====================================
echo GROUP ANALYSIS GT
echo =====================================
python group_analysis.py GT
if errorlevel 1 goto :error

echo.
echo =====================================
echo GROUP ANALYSIS EADRIATIC
echo =====================================
python group_analysis.py EADRIATIC
if errorlevel 1 goto :error

echo.
echo =====================================
echo GENERANDO WEB
echo =====================================
python web_tracker\generate_site.py
if errorlevel 1 goto :error

echo.
echo =====================================
echo WORKFLOW LOCAL COMPLETADO
echo =====================================
git status
pause
exit /b 0

:error
echo.
echo =====================================
echo ERROR: PROCESO INTERRUMPIDO
echo =====================================
git status
pause
exit /b 1