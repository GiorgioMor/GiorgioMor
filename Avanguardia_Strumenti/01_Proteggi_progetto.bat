@echo off
rem AVANGUARDIA - avvia 01_Proteggi_progetto.ps1 (doppio clic). Parametri facoltativi, es: -Progetto G:\Progetto_FPS
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp001_Proteggi_progetto.ps1" %*
echo.
pause
