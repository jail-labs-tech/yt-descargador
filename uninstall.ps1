# Desinstala "Contenido a tu disco" (Windows). Uso:
#   irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/uninstall.ps1 | iex
# Variable de pruebas: $env:CTD_HOME (carpeta de instalacion). Solo ASCII a proposito.
$Dest = if ($env:CTD_HOME) { $env:CTD_HOME } else { Join-Path $env:LOCALAPPDATA 'ContenidoATuDisco' }
Write-Host 'Desinstalando Contenido a tu disco...'
Remove-Item -LiteralPath $Dest -Recurse -Force -ErrorAction SilentlyContinue
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
  Remove-Item -LiteralPath (Join-Path $dir 'Contenido a tu disco.lnk') -Force -ErrorAction SilentlyContinue
}
Write-Host '   [OK] Borrados la carpeta y los accesos directos.'
Write-Host 'No se desinstalaron yt-dlp, ffmpeg ni Python (puede que los uses para otras cosas).'
