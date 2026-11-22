#!/bin/bash
# Doble clic en Finder: revisa/instala Python, yt-dlp y ffmpeg con Homebrew y abre Contenido a tu disco.
cd "$(dirname "$0")"
ok() { "$@" >/dev/null 2>&1; }

# Una Terminal nueva no trae brew en el PATH en Mac con Apple Silicon: cargarlo antes de decidir.
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done

if ! ok brew --version; then
  echo "Instalando Homebrew (te pedirá tu contraseña)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || exit 1
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi

check() { # comando, argumento de prueba, paquete brew
  if ok "$1" "$2"; then echo "✓ $1"; else echo "Instalando $3..."; brew install "$3" || exit 1; fi
}
check python3 --version python
check yt-dlp --version yt-dlp
check ffmpeg -version ffmpeg

echo "Actualizando yt-dlp (los sitios cambian seguido)..."
if brew list yt-dlp >/dev/null 2>&1; then brew upgrade yt-dlp 2>/dev/null; else yt-dlp -U; fi

python3 app.py
