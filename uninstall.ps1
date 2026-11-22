# Desinstala "Contenido a tu disco" (Windows). Uso:
#   irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/uninstall.ps1 | iex
# Variable de pruebas: $env:CTD_HOME (carpeta de instalacion). Solo ASCII a proposito.
$global:LASTEXITCODE = 0
& {
  $ErrorActionPreference = 'Stop'
  try {
    $Dest = [IO.Path]::GetFullPath($(if ($env:CTD_HOME) { $env:CTD_HOME } else { Join-Path $env:LOCALAPPDATA 'ContenidoATuDisco' })).TrimEnd('\')
    $root = [IO.Path]::GetPathRoot($Dest).TrimEnd('\')
    if ($Dest -eq '' -or $Dest -ieq $root -or $Dest -ieq $env:USERPROFILE.TrimEnd('\')) { throw "Ruta no segura: $Dest. No borre nada." }
    $Existe = Test-Path -LiteralPath $Dest
    if ($Existe -and -not (Test-Path -LiteralPath (Join-Path $Dest 'app.py'))) {
      throw "$Dest no parece una instalacion de Contenido a tu disco (no tiene app.py). No borre nada."
    }
    Write-Host 'Desinstalando Contenido a tu disco...'
    $lnks = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) | ForEach-Object { Join-Path $_ 'Contenido a tu disco.lnk' }
    Remove-Item -LiteralPath $Dest -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $lnks -Force -ErrorAction SilentlyContinue
    if ((Test-Path -LiteralPath $Dest) -or ($lnks | Where-Object { Test-Path -LiteralPath $_ })) {
      throw 'No pude borrar todo. Cierra la ventana negra de la app y vuelve a pegar el comando.'
    }
    Write-Host '   [OK] Borrados la carpeta y los accesos directos.'
    Write-Host 'No se desinstalaron yt-dlp, ffmpeg ni Python (puede que los uses para otras cosas).'
  } catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    $global:LASTEXITCODE = 1
  }
}
