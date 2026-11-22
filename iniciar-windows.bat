@echo off
rem Doble clic: revisa/instala Python, yt-dlp y ffmpeg con winget y abre el descargador.
chcp 65001 >nul
cd /d "%~dp0"

where winget >nul 2>&1
if errorlevel 1 (
  echo No encontre winget. Instala "App Installer" desde Microsoft Store y vuelve a abrir este archivo.
  pause
  exit /b 1
)

call :check python "-c pass" Python.Python.3.12
call :check yt-dlp "--version" yt-dlp.yt-dlp
call :check ffmpeg "-version" Gyan.FFmpeg

echo Actualizando yt-dlp (YouTube cambia seguido)...
yt-dlp -U

python app.py
pause
exit /b

:check
%1 %~2 >nul 2>&1
if not errorlevel 1 (
  echo [OK] %1
  exit /b
)
echo Instalando %1...
winget install -e --id %3 --accept-source-agreements --accept-package-agreements
call :refresh
%1 %~2 >nul 2>&1
if errorlevel 1 (
  echo No pude instalar %1. Cierra esta ventana y vuelve a abrir el archivo; si sigue fallando instala %3 a mano.
  pause
  exit 1
)
exit /b

:refresh
rem winget cambia el PATH en el registro, no en esta ventana: lo recargamos.
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%p"
exit /b
