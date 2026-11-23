@echo off
rem AVANGUARDIA - avvia 02_Crea_Maestrale.ps1 (doppio clic). Parametri facoltativi, es: -Progetto G:\Progetto_FPS
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp002_Crea_Maestrale.ps1" %*
echo.
pause
