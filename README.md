# Descargador de YouTube (MP3 / MP4)

Página web local para bajar audio o video de YouTube. Corre en tu máquina: el archivo lo descarga tu navegador y el servidor borra su copia temporal en cuanto la entrega (o al cerrarlo). La única petición externa además de YouTube es la tipografía de Google Fonts.

- Pega uno o varios enlaces (uno por línea); cada uno es una descarga con su propia tarjeta de progreso.
- MP3: Máxima (VBR), 320, 192 o 128 kbps.
- MP4: Máxima, 1080p, 720p, 480p o 360p, siempre en H.264 + AAC para que abra en cualquier reproductor.
- Hasta 3 descargas a la vez; el resto espera en cola.
- Un solo archivo de Python, sin dependencias de pip.

## Uso

**Mac:** doble clic en `iniciar-mac.command` (la primera vez: clic derecho → Abrir).
**Windows:** doble clic en `iniciar-windows.bat`.

Ambos revisan e instalan lo que falte (Python, [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org)) con Homebrew o winget, actualizan yt-dlp y abren http://localhost:8765.

**Manual (cualquier sistema):** instala Python 3.8+, yt-dlp y ffmpeg, y corre:

```sh
python3 app.py
```

Si YouTube empieza a fallar, casi siempre se arregla actualizando yt-dlp (`brew upgrade yt-dlp`, `winget upgrade yt-dlp.yt-dlp` o `yt-dlp -U`).

## Seguridad

El servidor solo escucha en `127.0.0.1` y rechaza peticiones cuyo `Host`/`Origin` no sea la propia página, para que otro sitio abierto en tu navegador no pueda usarlo. Solo acepta enlaces de dominios de YouTube y llama a yt-dlp sin shell.

## Pruebas

```sh
python3 -m unittest -v          # sin red, con un yt-dlp falso (se saltan en Windows)
YT_REAL=1 python3 -m unittest   # además descarga un video real corto
```

## Aviso

Úsalo solo con contenido que tengas derecho a descargar. Descargar videos puede ir contra los Términos de Servicio de YouTube o los derechos de autor del contenido; la responsabilidad es de quien lo usa.

## Licencia

MIT
