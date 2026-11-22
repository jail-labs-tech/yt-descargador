# Instalador de "Contenido a tu disco" para Windows (PowerShell 5.1 o superior).
#   Instalar / actualizar: irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.ps1 | iex
#   Desinstalar:           irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/uninstall.ps1 | iex
#
# Variables (solo para pruebas):
#   $env:CTD_SOURCE=ruta   zip local en lugar de descargarlo
#   $env:CTD_HOME=ruta     carpeta de instalacion (por defecto %LOCALAPPDATA%\ContenidoATuDisco)
#   $env:CTD_SKIP_DEPS=1   no revisa ni instala Python, yt-dlp ni ffmpeg
#   $env:CTD_NO_OPEN=1     no abre la app al terminar
#
# Solo ASCII a proposito (sin acentos) para no depender de la codificacion con iex.
# Nunca usa "exit": con "irm | iex" cerraria la ventana de PowerShell del usuario.

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$global:LASTEXITCODE = 0

# Todo dentro de & { } para no dejar variables, funciones ni $ErrorActionPreference en la sesion del usuario.
& {
  $ProgressPreference = 'SilentlyContinue'   # sin esto Invoke-WebRequest es muy lento en PS 5.1
  $ErrorActionPreference = 'Stop'
  $Tmp = $null

  function Test-Cmd($exe, $cmdArgs) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & $exe @cmdArgs 2>&1 | Out-Null; return ($LASTEXITCODE -eq 0) }
    catch { return $false }
    finally { $ErrorActionPreference = $old }
  }
  function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    # el "python" falso de Microsoft Store (WindowsApps) no sirve: el Python real va primero
    $py = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
    if (Test-Path -LiteralPath (Join-Path $py 'python.exe')) { $env:Path = "$py;$py\Scripts;$env:Path" }
  }
  function Install-Dep($name, $exe, $cmdArgs, $id) {
    if (Test-Cmd $exe $cmdArgs) { Write-Host "   [OK] $name"; return }
    Write-Host "   Instalando $name (puede tardar un par de minutos)..."
    & winget install -e --source winget --id $id --accept-source-agreements --accept-package-agreements
    Update-Path
    if (-not (Test-Cmd $exe $cmdArgs)) {
      throw "No pude instalar $name. Cierra esta ventana, abre PowerShell otra vez y pega el comando de nuevo. Si sigue fallando, instala $id a mano."
    }
    Write-Host "   [OK] $name instalado"
  }
  # Devuelve la ruta completa; rechaza la raiz de la unidad y la carpeta personal.
  function Get-SafePath($p) {
    $full = [IO.Path]::GetFullPath($p).TrimEnd('\')
    $root = [IO.Path]::GetPathRoot($full).TrimEnd('\')
    if ($full -eq '' -or $full -ieq $root -or $full -ieq $env:USERPROFILE.TrimEnd('\')) {
      throw "Ruta de instalacion no segura: $p. No borre nada."
    }
    return $full
  }

  try {
    $Dest = Get-SafePath $(if ($env:CTD_HOME) { $env:CTD_HOME } else { Join-Path $env:LOCALAPPDATA 'ContenidoATuDisco' })
    $Bat = Join-Path $Dest 'iniciar-windows.bat'
    $Lnk = 'Contenido a tu disco.lnk'
    # solo se vacia una carpeta que no existe, esta vacia o tiene nuestro marcador .ctd-instalacion
    $Existe = Test-Path -LiteralPath $Dest
    $Nuestra = Test-Path -LiteralPath (Join-Path $Dest '.ctd-instalacion')
    if ($Existe -and -not $Nuestra -and (Get-ChildItem -LiteralPath $Dest -Force | Select-Object -First 1)) {
      throw "$Dest ya existe y no parece una instalacion de Contenido a tu disco (falta .ctd-instalacion). No borre nada."
    }

    Write-Host ''
    Write-Host 'Instalando Contenido a tu disco'

    Write-Host ''
    Write-Host '1. Revisando Python, yt-dlp y ffmpeg'
    if ($env:CTD_SKIP_DEPS -eq '1') {
      Write-Host '   [OK] Omitido (CTD_SKIP_DEPS=1)'
    } else {
      if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'No encontre winget. Abre Microsoft Store, busca "App Installer" (Instalador de aplicacion), instalalo o actualizalo, y vuelve a pegar el comando.'
      }
      Update-Path
      Install-Dep 'Python' 'python' @('-c', 'pass') 'Python.Python.3.12'
      $src = (Get-Command python -ErrorAction SilentlyContinue).Source
      if ($src -like '*\WindowsApps\*') {
        throw 'Windows esta usando el "python" falso de Microsoft Store. Cierra esta ventana, abre PowerShell otra vez y pega el comando de nuevo; si sigue igual, desactiva el alias en Configuracion > Aplicaciones > Configuracion avanzada > Alias de ejecucion de aplicaciones.'
      }
      Install-Dep 'yt-dlp' 'yt-dlp' @('--version') 'yt-dlp.yt-dlp'
      Install-Dep 'ffmpeg' 'ffmpeg' @('-version') 'Gyan.FFmpeg'
    }

    Write-Host ''
    Write-Host '2. Descargando la app'
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ('ctd-' + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Tmp | Out-Null
    $Zip = Join-Path $Tmp 'app.zip'
    if ($env:CTD_SOURCE) {
      if (-not (Test-Path -LiteralPath $env:CTD_SOURCE)) { throw "No existe CTD_SOURCE: $env:CTD_SOURCE" }
      Copy-Item -LiteralPath $env:CTD_SOURCE -Destination $Zip
    } else {
      try {
        Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/jail-labs-tech/contenido-a-tu-disco/zip/refs/heads/main' -OutFile $Zip
      } catch {
        throw 'No pude descargar la app. Revisa tu conexion a internet y vuelve a pegar el comando.'
      }
    }
    Expand-Archive -LiteralPath $Zip -DestinationPath (Join-Path $Tmp 'x') -Force
    $Root = Get-ChildItem -LiteralPath (Join-Path $Tmp 'x') -Directory | Select-Object -First 1
    if (-not $Root -or -not (Test-Path -LiteralPath (Join-Path $Root.FullName 'app.py'))) {
      throw 'El archivo descargado no trae app.py. Vuelve a pegar el comando.'
    }
    Write-Host '   [OK] Descargada'

    Write-Host ''
    Write-Host "3. Instalando en $Dest"
    if ($Nuestra) { Write-Host '   Si la app esta abierta, cierra su ventana negra antes de actualizar (si no, seguira la version vieja).' }
    if (-not $Existe) { New-Item -ItemType Directory -Path $Dest | Out-Null }
    Get-ChildItem -LiteralPath $Dest -Force | Where-Object { $_.Name -ne 'descargador.log' -and $_.Name -ne '.ctd-instalacion' } | Remove-Item -Recurse -Force
    Remove-Item -LiteralPath (Join-Path $Root.FullName 'descargador.log') -Force -ErrorAction SilentlyContinue
    Get-ChildItem -LiteralPath $Root.FullName -Force | Copy-Item -Destination $Dest -Recurse -Force
    New-Item -ItemType File -Force -Path (Join-Path $Dest '.ctd-instalacion') | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $Dest 'app.py')) -or -not (Test-Path -LiteralPath (Join-Path $Dest 'static'))) {
      throw "La copia fallo: no encuentro app.py y static en $Dest. Vuelve a pegar el comando."
    }
    Write-Host '   [OK] Archivos listos'

    Write-Host ''
    Write-Host '4. Creando accesos directos (Escritorio y menu Inicio)'
    $sh = New-Object -ComObject WScript.Shell
    foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
      $l = $sh.CreateShortcut((Join-Path $dir $Lnk))
      $l.TargetPath = $Bat
      $l.WorkingDirectory = $Dest
      $l.Description = 'Contenido a tu disco'
      $l.Save()
      if (-not (Test-Path -LiteralPath (Join-Path $dir $Lnk))) { throw "No pude crear el acceso directo en $dir" }
      Write-Host "   [OK] $dir"
    }

    Write-Host ''
    Write-Host 'Listo! Contenido a tu disco quedo instalado.'
    Write-Host '  Abrir:       doble clic en "Contenido a tu disco" en tu Escritorio (o buscalo en el menu Inicio).'
    Write-Host '  Actualizar:  vuelve a pegar el mismo comando de instalacion.'
    Write-Host '  Desinstalar: irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/uninstall.ps1 | iex'
    if ($env:CTD_NO_OPEN -ne '1') {
      Write-Host ''
      Write-Host 'Abriendo la app...'
      Start-Process -FilePath $Bat -WorkingDirectory $Dest
    }
    $global:LASTEXITCODE = 0
  } catch {
    Write-Host ''
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    $global:LASTEXITCODE = 1
  } finally {
    if ($Tmp -and (Test-Path -LiteralPath $Tmp)) { Remove-Item -LiteralPath $Tmp -Recurse -Force -ErrorAction SilentlyContinue }
  }
}
