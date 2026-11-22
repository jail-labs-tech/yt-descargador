@echo off
rem Doble clic: revisa/instala Python, yt-dlp y ffmpeg con winget y abre Contenido a tu disco.
chcp 65001 >nul
cd /d "%~dp0"

rem El "python" falso de Microsoft Store (WindowsApps) no sirve: preferimos el Python real.
set "PYD=%LOCALAPPDATA%\Programs\Python\Python312"
if exist "%PYD%\python.exe" set "PATH=%PYD%;%PYD%\Scripts;%PATH%"

where winget >nul 2>&1
if errorlevel 1 (
  echo No encontre winget. Instala "App Installer" desde Microsoft Store y vuelve a abrir este archivo.
  pause
  exit /b 1
)

call :check python "-c pass" Python.Python.3.12
call :check yt-dlp "--version" yt-dlp.yt-dlp
call :check ffmpeg "-version" Gyan.FFmpeg

echo Actualizando yt-dlp (los sitios cambian seguido)...
winget list -e --id yt-dlp.yt-dlp --accept-source-agreements >nul 2>&1
if errorlevel 1 (
  yt-dlp -U
) else (
  winget upgrade -e --id yt-dlp.yt-dlp --accept-source-agreements --accept-package-agreements
)
rem si falla (sin internet) seguimos: arranca con la version que ya tienes

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
winget install -e --source winget --id %3 --accept-source-agreements --accept-package-agreements
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
if exist "%PYD%\python.exe" set "PATH=%PYD%;%PYD%\Scripts;%PATH%"
exit /b
