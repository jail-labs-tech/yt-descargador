#!/bin/sh
# Instalador de "Contenido a tu disco" (Mac y Linux).
#   Instalar / actualizar: curl -fsSL https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.sh | sh
#   Desinstalar:           curl -fsSL .../install.sh | sh -s -- --uninstall
#
# Variables (solo para pruebas):
#   CTD_SOURCE=ruta     tarball local (.tar.gz) en lugar de descargarlo
#   CTD_HOME=ruta       carpeta de instalacion (por defecto ~/.contenido-a-tu-disco)
#   CTD_BIN=ruta        carpeta del comando (por defecto ~/.local/bin)
#   CTD_APPS=ruta       carpeta de la .app en Mac (por defecto ~/Applications)
#   CTD_SKIP_DEPS=1     no revisa ni instala Python, yt-dlp ni ffmpeg
#   CTD_NO_OPEN=1       no abre la app al terminar
#
# Todo va dentro de main() para que, si la descarga se corta, no se ejecute a medias.
set -eu

main() {
  TGZ_URL="https://codeload.github.com/jail-labs-tech/contenido-a-tu-disco/tar.gz/refs/heads/main"
  DEST=${CTD_HOME:-$HOME/.contenido-a-tu-disco}
  BIN=${CTD_BIN:-$HOME/.local/bin}
  APPS=${CTD_APPS:-$HOME/Applications}
  CMD="$BIN/contenido-a-tu-disco"
  APP="$APPS/Contenido a tu disco.app"
  OS=$(uname -s)
  N=0

  say()  { printf '%s\n' "$*"; }
  step() { N=$((N + 1)); printf '\n%s. %s\n' "$N" "$*"; }
  good() { printf '   ✓ %s\n' "$*"; }
  die()  { printf '\n✗ %s\n' "$*" >&2; exit 1; }
  have() { "$@" >/dev/null 2>&1; }

  if [ "${1:-}" = "--uninstall" ]; then
    case "$DEST" in ""|/|"$HOME") die "Ruta de instalacion no segura: '$DEST'" ;; esac
    say "Desinstalando Contenido a tu disco..."
    rm -rf "$DEST" "$CMD" "$APP"
    good "Borrado $DEST, el comando y la app."
    say "No se desinstalaron yt-dlp, ffmpeg ni Python (puede que los uses para otras cosas)."
    return 0
  fi

  say "Instalando Contenido a tu disco"

  # ---- 1. Dependencias ----
  step "Revisando Python, yt-dlp y ffmpeg"
  if [ "${CTD_SKIP_DEPS:-}" = "1" ]; then
    good "Omitido (CTD_SKIP_DEPS=1)"
  elif [ "$OS" = "Darwin" ]; then
    deps_mac
  else
    deps_linux
  fi

  # ---- 2. Descarga ----
  step "Descargando la app"
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  if [ -n "${CTD_SOURCE:-}" ]; then
    [ -f "$CTD_SOURCE" ] || die "No existe CTD_SOURCE: $CTD_SOURCE"
    cp "$CTD_SOURCE" "$TMP/app.tgz"
  else
    curl -fsSL -o "$TMP/app.tgz" "$TGZ_URL" ||
      die "No pude descargar la app. Revisa tu conexion a internet y vuelve a pegar el comando."
  fi
  mkdir "$TMP/x"
  tar -xzf "$TMP/app.tgz" -C "$TMP/x" --strip-components=1 ||
    die "El archivo descargado esta danado. Vuelve a pegar el comando."
  [ -f "$TMP/x/app.py" ] || die "El archivo descargado no trae app.py. Vuelve a pegar el comando."
  good "Descargada"

  # ---- 3. Instalar (reemplaza la app, conserva descargador.log) ----
  step "Instalando en $DEST"
  case "$DEST" in ""|/|"$HOME") die "Ruta de instalacion no segura: '$DEST'" ;; esac
  mkdir -p "$DEST"
  find "$DEST" -mindepth 1 -maxdepth 1 ! -name descargador.log -exec rm -rf {} +
  rm -f "$TMP/x/descargador.log"
  cp -R "$TMP/x/." "$DEST/"
  chmod +x "$DEST/iniciar-mac.command" 2>/dev/null || true
  good "Archivos listos"

  # ---- 4. Comando de terminal ----
  step "Creando el comando contenido-a-tu-disco"
  mkdir -p "$BIN"
  if [ "$OS" = "Darwin" ]; then
    printf '#!/bin/sh\nexec bash "%s/iniciar-mac.command"\n' "$DEST" > "$CMD"
  else
    printf '#!/bin/sh\ncd "%s" && exec python3 app.py\n' "$DEST" > "$CMD"
  fi
  chmod +x "$CMD"
  good "$CMD"
  case ":$PATH:" in
    *":$BIN:"*) ;;
    *) say "   ! $BIN no esta en tu PATH. Para usar el comando, agrega esta linea a tu ~/.zshrc o ~/.bashrc:"
       say "       export PATH=\"$BIN:\$PATH\"" ;;
  esac

  # ---- 5. Icono en Mac ----
  if [ "$OS" = "Darwin" ]; then
    step "Creando el icono en Aplicaciones"
    rm -rf "$APP"
    mkdir -p "$APP/Contents/MacOS"
    # ponytail: sin icono grafico (icono generico de app); se puede agregar un .icns despues.
    cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Contenido a tu disco</string>
  <key>CFBundleDisplayName</key><string>Contenido a tu disco</string>
  <key>CFBundleIdentifier</key><string>com.jail-labs.contenido-a-tu-disco</string>
  <key>CFBundleExecutable</key><string>contenido-a-tu-disco</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
</dict>
</plist>
PLIST
    printf '#!/bin/sh\nexec open "%s/iniciar-mac.command"\n' "$DEST" > "$APP/Contents/MacOS/contenido-a-tu-disco"
    chmod +x "$APP/Contents/MacOS/contenido-a-tu-disco"
    good "$APP"
  fi

  say ""
  say "¡Listo! Contenido a tu disco quedó instalado."
  if [ "$OS" = "Darwin" ]; then
    say "  Abrir:         el icono \"Contenido a tu disco\" en $APPS, o el comando: contenido-a-tu-disco"
  else
    say "  Abrir:         contenido-a-tu-disco   (luego entra a http://localhost:8765)"
  fi
  say "  Actualizar:    vuelve a pegar el mismo comando de instalacion."
  say "  Desinstalar:   curl -fsSL https://raw.githubusercontent.com/jail-labs-tech/contenido-a-tu-disco/main/install.sh | sh -s -- --uninstall"

  if [ "$OS" = "Darwin" ] && [ "${CTD_NO_OPEN:-}" != "1" ]; then
    say ""
    say "Abriendo la app..."
    open "$APP"
  fi
}

deps_mac() {
  load_brew() {
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
    done
    return 1
  }
  if ! have brew --version && ! load_brew; then
    say "   Homebrew no esta instalado; lo instalo ahora. Te pedira la contraseña de tu Mac."
    (: </dev/tty) 2>/dev/null ||
      die "No hay terminal disponible para pedir la contraseña. Abre la app Terminal y pega el comando alli."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty ||
      die "Fallo la instalacion de Homebrew. Mas informacion en https://brew.sh"
    load_brew || die "Homebrew se instalo pero no lo encuentro. Cierra y abre Terminal y vuelve a pegar el comando."
  fi
  for pair in python3:python yt-dlp:yt-dlp ffmpeg:ffmpeg; do
    cmd=${pair%%:*}; pkg=${pair#*:}
    if have "$cmd" --version || { [ "$cmd" = ffmpeg ] && have ffmpeg -version; }; then
      good "$cmd"
    else
      say "   Instalando $pkg con Homebrew..."
      brew install "$pkg" </dev/null || die "No pude instalar $pkg. Prueba a mano: brew install $pkg"
      good "$pkg instalado"
    fi
  done
}

deps_linux() {
  missing=""
  have python3 --version || missing="$missing python3"
  have ffmpeg -version || missing="$missing ffmpeg"
  have yt-dlp --version || missing="$missing yt-dlp"
  if [ -z "$missing" ]; then good "python3, ffmpeg y yt-dlp"; return 0; fi
  say "   Falta:$missing"
  say "   Instalalo con el comando de tu distribucion y vuelve a pegar el de instalacion:"
  if have apt-get --version; then say "     sudo apt install python3 python3-pip ffmpeg"
  elif have dnf --version; then say "     sudo dnf install python3 python3-pip ffmpeg-free"
  elif have pacman --version; then say "     sudo pacman -S python python-pip ffmpeg"
  else say "     (instala python3 y ffmpeg con el gestor de paquetes de tu distribucion)"; fi
  case "$missing" in *yt-dlp*)
    say "     python3 -m pip install --user -U yt-dlp     (o: pipx install yt-dlp)" ;;
  esac
  die "Faltan dependencias; no uso sudo por mi cuenta."
}

main "$@"
