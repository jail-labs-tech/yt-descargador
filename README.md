# Contenido a tu disco

**Sin anuncios:** corre en tu equipo, sin ads ni páginas llenas de pop-ups.

Página web local para bajar audio (MP3) o video (MP4). Funciona con YouTube y con los más de 1.800 sitios que soporta [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) (TikTok, Instagram, X, Vimeo, SoundCloud, Twitch, Facebook, etc.). Los servicios con DRM (Netflix, Spotify, Disney+, Prime Video) no funcionan. El archivo lo descarga tu navegador y el servidor borra su copia temporal en cuanto la entrega (o al cerrarlo). La única petición externa además del sitio de origen es la tipografía de Google Fonts.

- Pega uno o varios enlaces (uno por línea); cada uno es una descarga con su propia tarjeta de progreso. En sitios que no son YouTube se baja un solo elemento por enlace.
- Recorte: puedes bajar solo un tramo indicando desde y hasta (en segundos). En video el corte es exacto, por eso tarda un poco más (recodifica el tramo).
- MP3: Máxima (VBR), 320, 192 o 128 kbps.
- MP4: Máxima, 1080p, 720p, 480p o 360p, siempre en H.264 + AAC para que abra en cualquier reproductor.
- Playlists (solo YouTube): pega el enlace de una lista y eliges qué videos bajar (tope de 500 videos); los Mix automáticos de YouTube (`list=RD...`) se bajan como video suelto.
- Mix: une varias canciones en un solo MP3, con recorte por pista y fundido cruzado de 0 a 10 s (hasta 50 pistas; ocupa un cupo de descarga).
- Hasta 3 descargas a la vez; el resto espera en cola.
- Servidor de un solo archivo de Python (`app.py`) más la página en `static/` (HTML, CSS y JS), sin dependencias de pip.

## Instalar

**Mac o Linux:** abre la app Terminal, pega esto y pulsa Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.sh | sh
```

En Mac instala lo que falte (te pedirá tu contraseña la primera vez), crea el ícono **Contenido a tu disco** y abre la app; después lo encuentras con Spotlight (Cmd+Espacio y escribe "Contenido") o en Launchpad. En Linux no instala nada por su cuenta: si falta Python, ffmpeg o yt-dlp, te imprime el comando exacto.

**Windows:** solo hay que pegar un comando una vez.

1. Pulsa la tecla Windows, escribe `PowerShell` y pulsa Enter.
2. En la ventana que se abre, pega este comando (clic derecho dentro de la ventana, o Ctrl+V) y pulsa Enter:

   ```powershell
   irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.ps1 | iex
   ```

3. Espera a que termine (la primera vez puede tardar unos minutos). Si Windows pregunta "¿Quieres permitir que esta aplicación haga cambios?", pulsa **Sí**.

Al terminar se abre la app, junto con una ventana negra: no la cierres mientras uses la app.

**Abrirla después:** doble clic en el ícono **Contenido a tu disco** (en el Escritorio y el menú Inicio en Windows; en Aplicaciones en Mac). En Mac y Linux también sirve el comando `contenido-a-tu-disco`.

**Actualizar:** cierra la app (si está abierta) y vuelve a pegar el mismo comando de instalación. Conserva tu `descargador.log`.

**Desinstalar** (no quita Python, yt-dlp ni ffmpeg):

```sh
curl -fsSL https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.sh | sh -s -- --uninstall
```

```powershell
irm https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/uninstall.ps1 | iex
```

## Instalación manual

**Mac:** doble clic en `iniciar-mac.command` (la primera vez: clic derecho → Abrir).
**Windows:** doble clic en `iniciar-windows.bat`.

Ambos revisan e instalan lo que falte (Python, [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org)) con Homebrew o winget, actualizan yt-dlp (en Mac y en Windows) y abren http://localhost:8765.

**Manual (cualquier sistema):** instala Python 3.8+, yt-dlp y ffmpeg, y corre:

```sh
python3 app.py
```

Si el sitio pide iniciar sesión ("confirma que no eres un bot", restricción de edad, contenido solo para usuarios registrados), la app reintenta una vez con las cookies del navegador en el que abriste la página; para que funcione tienes que tener sesión iniciada ahí en ese sitio. En Mac, el navegador puede pedirte la contraseña del llavero.

Si un sitio empieza a fallar, casi siempre se arregla actualizando yt-dlp (`brew upgrade yt-dlp`, `winget upgrade yt-dlp.yt-dlp` o `yt-dlp -U`).

Los errores se explican en la página y se guardan en `descargador.log` (junto a `app.py`), junto con los avisos de lo que falte instalar.

## Seguridad

El servidor solo escucha en `127.0.0.1` y rechaza peticiones cuyo `Host`/`Origin` no sea la propia página, para que otro sitio abierto en tu navegador no pueda usarlo. Acepta cualquier enlace `http` o `https` (rechaza `file:`, `ftp:`, etc.) y llama a yt-dlp sin shell y con `--` antes de la URL, para que un enlace nunca se interprete como opción.

## Pruebas

```sh
python3 -m unittest -v          # sin red, con un yt-dlp falso (también en Windows)
YT_REAL=1 python3 -m unittest   # además descarga un video real corto
```

## Aviso

Úsalo solo con contenido que tengas derecho a descargar. Descargar videos puede ir contra los Términos de Servicio de YouTube o los derechos de autor del contenido; la responsabilidad es de quien lo usa.

## Licencia

MIT
