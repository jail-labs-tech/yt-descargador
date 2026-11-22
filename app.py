#!/usr/bin/env python3
"""Contenido a tu disco: descargador local (MP3/MP4) de YouTube y los sitios que soporta yt-dlp. Uso: python3 app.py  ->  http://localhost:8765"""
import errno, json, math, logging, os, re, secrets, shutil, signal, subprocess, sys, tempfile, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

TMP = tempfile.TemporaryDirectory(prefix="yt-")  # se borra solo al cerrar el server
PORT = 8765
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
YTDLP = ["yt-dlp"]  # los tests lo cambian por un yt-dlp falso
FFMPEG, FFPROBE = ["ffmpeg"], ["ffprobe"]  # idem
STATIC = Path(__file__).parent / "static"
FILES = {"/": ("index.html", "text/html; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8"),
         "/app.js": ("app.js", "text/javascript; charset=utf-8")}  # lista fija: no se sirve ninguna otra ruta
INSTALL = {"yt-dlp": "brew install yt-dlp  |  winget install yt-dlp.yt-dlp", "ffmpeg": "brew install ffmpeg  |  winget install Gyan.FFmpeg"}
log = logging.getLogger("descargador")
log.addHandler(logging.NullHandler())  # el archivo de log solo se crea al correr app.py
COOKIE_ERR = "failed to decrypt|operation not permitted|permission denied|database is locked"  # "cookie" puede ir antes o después
# (patrón, mensaje, help): se recorre en orden; None = el mensaje original de yt-dlp
ERRORS = [
    (r"FileNotFoundError", "Falta yt-dlp en tu equipo", "falta-ytdlp"),
    (r"failed to load cookies|could not (find \w+ cookies|copy \w+ cookie)|failed to decrypt with dpapi"
     rf"|cookies?\b.*({COOKIE_ERR})|({COOKIE_ERR}).*cookie", "No pude leer las cookies de tu navegador", "cookies"),
    (r"ff(mpeg|probe)\b.*(not found|not installed)", "Falta ffmpeg en tu equipo", "falta-ffmpeg"),
    (r"unsupported url", "Ese sitio no es compatible", "sitio"),
    # textos de yt-dlp: raise_login_required ("This video is only available for registered users"), "Login required",
    # "Requires authentication", "You need to log in to access this content", Instagram "...rate-limit reached or login required"
    (r"not a bot|confirm your age|age-restricted|sign in to confirm|login required|registered users|requires authentication"
     r"|need to log ?in|rate-limit reached", "El sitio pide iniciar sesión", "bot"),
    (r"\b403\b", "El sitio rechazó la descarga; prueba actualizar yt-dlp", "actualizar"),
    (r"video unavailable", "El video no está disponible (privado, borrado o bloqueado en tu país)", None),
    (r"private video", "Es un video privado", None),
]


def explain(err):
    """Mensaje de yt-dlp -> (texto en español, id de ayuda o None)."""
    for pat, msg, hlp in ERRORS:
        if re.search(pat, err, re.I):
            return msg, hlp
    return re.sub(r"^ERROR: ", "", err), "actualizar"


def browser_of(ua):
    """Navegador para --cookies-from-browser según el User-Agent (Edge y Opera también dicen Chrome/)."""
    for key, name in (("Edg/", "edge"), ("OPR/", "opera"), ("Firefox/", "firefox"), ("Chrome/", "chrome")):
        if key in ua:
            return name
    return "safari" if "Safari/" in ua else None


def mp4(h=None):  # siempre H.264 + AAC si existe: AV1/Opus no abren en QuickTime (solo se oye el audio)
    f = f"[height<={h}]" if h else ""
    return ["-f", f"bv*{f}[vcodec^=avc1]+ba[ext=m4a]/bv*{f}[ext=mp4]+ba[ext=m4a]/b{f}[ext=mp4]/bv*{f}+ba/b",
            "--merge-output-format", "mp4"]


AUDIO = ["-f", "ba[ext=m4a]/ba/b"]  # m4a: con recorte sale exacto; en webm/opus el tramo sale hasta ~10 s más largo
MP3 = ["-x", "--audio-format", "mp3", "--audio-quality"]
QUALITY = {
    "mp3": {"best": MP3 + ["0"], "320": MP3 + ["320K"], "192": MP3 + ["192K"], "128": MP3 + ["128K"]},
    "mp4": {"best": mp4(), "1080": mp4(1080), "720": mp4(720), "480": mp4(480), "360": mp4(360)},
}
JOBS = {}  # id -> estado de la descarga
SLOTS = threading.Semaphore(3)  # ponytail: 3 descargas a la vez, el resto espera "En cola"
PROG = "download:PROG %(progress.downloaded_bytes)s %(progress.total_bytes)s %(progress.total_bytes_estimate)s %(progress.speed)s %(progress.eta)s"
POSTPROC = ("[Merger]", "[ExtractAudio]", "[VideoConvertor]", "[VideoRemuxer]", "[Fixup")


def num(x):
    try:
        return float(x)
    except ValueError:
        return None  # "NA"


def label(job):
    if job["format"] == "mix":
        return f"Descargando pista {job['track']} de {job['tracks']}"
    if job["stage"] == "convert":
        return "Convirtiendo a MP3" if job["format"] == "mp3" else "Uniendo video y audio"
    if job["stage"] == "download":
        return "Descargando video" if job["format"] == "mp4" and job["part"] == 1 else "Descargando audio"
    return "Preparando..."


def fetch(job, url, opts, out, browser=None):
    """yt-dlp con reintentos de 403 y, si el sitio pide sesión, con cookies del navegador. Devuelve None o el error."""
    pre = [*YTDLP, "--no-playlist", "--playlist-items", "1", "--encoding", "utf-8", "--newline", "--progress-template", PROG, *opts]
    post = ["-o", str(Path(out) / "%(title)s.%(ext)s"), "--", url]
    for attempt in range(1, 4):  # YouTube a veces da 403 a un enlace; reintentar saca enlaces nuevos
        err = yt_dlp(job, pre + post)
        if not err or "403" not in err or attempt == 3:
            break
        log.info("[intento %s] %s: %s", attempt, url, err)
    if err and browser and explain(err)[1] == "bot":  # cookies solo si el sitio lo pide (en Mac piden el llavero)
        log.info("%s: El sitio pide sesión, reintento con cookies de %s", url, browser)
        err = yt_dlp(job, pre + ["--cookies-from-browser", browser] + post)
    return err


def run(job, url, opts, out, browser=None):
    SLOTS.acquire()
    job.update(stage="start", label="Preparando...")
    try:
        f = None
        try:
            err = fetch(job, url, opts, out, browser)
            if not err:
                f = next((f for f in Path(out).iterdir() if f.suffix == "." + job["format"]), None)
        except Exception as e:  # FileNotFoundError, PermissionError...: el job nunca se queda en "running"
            err = f"{type(e).__name__}: {e}"
        if err:
            msg, hlp = explain(err)
            log.error("Falló %s | error: %s | help: %s | yt-dlp: %s", url, msg, hlp, err)
            job.update(state="error", error=msg, **({"help": hlp} if hlp else {}))
            shutil.rmtree(out, ignore_errors=True)
            return
        if not f:
            log.error("Falló %s | yt-dlp terminó pero no generó el archivo", url)
            job.update(state="error", error="yt-dlp terminó pero no generó el archivo")
            shutil.rmtree(out, ignore_errors=True)
            return
        job.update(state="done", percent=100, file=str(f), name=f.name, label="Listo")
    finally:
        SLOTS.release()


def mix_filter(n, crossfade):
    """Filtro de ffmpeg que une n entradas (0..n-1) en [out], con fundido cruzado de `crossfade` s (0 = corte directo)."""
    norm = "".join(f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];" for i in range(n))
    if crossfade <= 0:
        return norm + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    prev, chain = "a0", ""
    for i in range(1, n):
        cur = "out" if i == n - 1 else f"x{i}"
        chain += f"[{prev}][a{i}]acrossfade=d={crossfade:g}:c1=tri:c2=tri[{cur}];"
        prev = cur
    return norm + chain.rstrip(";")


def join(files, crossfade, dest):
    """Une los audios en un MP3. El fundido no puede pasar de la mitad de la pista más corta (si se conocen las duraciones)."""
    if crossfade:
        durs = []
        for f in files:
            out = subprocess.run([*FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                 capture_output=True, text=True, check=True).stdout
            try:
                durs.append(float(out))
            except ValueError:  # "N/A": duración desconocida
                pass
        if durs:
            crossfade = round(min(crossfade, min(durs) / 2), 3)
    cmd = [*FFMPEG, "-y", "-v", "error", *[a for f in files for a in ("-i", str(f))],
           "-filter_complex", mix_filter(len(files), crossfade), "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "0", str(dest)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(next((l for l in reversed(p.stderr.splitlines()) if l.strip()), "ffmpeg falló"))


def run_mix(job, items, crossfade, out, browser=None):
    """Un mix ocupa un solo cupo: baja las pistas una por una (cada una en su subcarpeta) y las une al final."""
    n, out = len(items), Path(out)
    SLOTS.acquire()
    try:
        err = hlp = None
        try:
            files = []
            for i, (url, cut) in enumerate(items, 1):
                job["track"] = i
                job.update(stage="start", label=f"Descargando pista {i} de {n}", percent=pct(job, 0),
                           downloaded=None, total=None, speed=None, eta=None)
                d = out / str(i)
                d.mkdir()
                try:
                    e = fetch(job, url, AUDIO + ["-x"] + (["--download-sections", sections(*cut)] if cut else []), d, browser)
                except Exception as x:
                    e = f"{type(x).__name__}: {x}"
                f = None if e else next(d.iterdir(), None)
                if e or not f:
                    msg, hlp = explain(e) if e else ("yt-dlp terminó pero no generó el archivo", None)
                    err = f"Pista {i}: {msg}"
                    log.error("Falló mix en %s | error: %s | help: %s | yt-dlp: %s", url, err, hlp, e)
                    break
                files.append(f)
            if not err:
                job.update(stage="join", label="Uniendo pistas", percent=None, downloaded=None, total=None, speed=None, eta=None)
                dest = out / f"Mix ({n} pistas).mp3"
                try:
                    join(files, crossfade, dest)
                except FileNotFoundError:
                    err, hlp = "Falta ffmpeg en tu equipo", "falta-ffmpeg"
                except Exception as x:
                    err = f"No pude unir las pistas: {x}"
                if err:
                    log.error("Falló la unión del mix | %s | help: %s", err, hlp)
        except Exception as x:  # mkdir, preparar pista...: el job nunca se queda en "running"
            err, hlp = explain(f"{type(x).__name__}: {x}")
            log.error("Falló el mix | error: %s | help: %s", err, hlp)
        if err:
            job.update(state="error", error=err, **({"help": hlp} if hlp else {}))
            shutil.rmtree(out, ignore_errors=True)
            return
        for i in range(1, n + 1):
            shutil.rmtree(out / str(i), ignore_errors=True)
        job.update(state="done", percent=100, file=str(dest), name=dest.name, label="Listo")
    finally:
        SLOTS.release()


def pct(job, p):
    """Porcentaje de la descarga en curso; en un mix, su parte del 0-90 % del total (la unión ocupa el resto)."""
    if p is None or job["format"] != "mix":
        return p
    return round(((job["track"] - 1) * 100 + p) * 0.9 / job["tracks"], 1)


def yt_dlp(job, cmd):
    """Corre yt-dlp actualizando el progreso de job. Devuelve None si salió bien o el mensaje de error."""
    err = "yt-dlp falló"
    job["part"] = 0
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as p:
        for line in p.stdout:
            if line.startswith("PROG "):
                done, total, est, speed, eta = map(num, line.split()[1:6])
                total = total or est
                job.update(downloaded=done, total=total, speed=speed, eta=eta,
                           percent=pct(job, round(min(done / total, 1) * 100, 1) if done and total else 0))
            elif line.startswith("[download] Destination:"):
                job["title"] = re.sub(r"(\.f\d+)?\.\w+$", "", Path(line.split(": ", 1)[1].strip()).name)
                job.update(stage="download", part=job["part"] + 1, percent=pct(job, 0), speed=None, eta=None)
            elif line.startswith(POSTPROC):
                job.update(stage="convert", percent=pct(job, 100 if job["format"] == "mix" else None), speed=None, eta=None)
            elif line.startswith("ERROR:"):
                err = line.strip()
            job["label"] = label(job)
    return err if p.returncode else None


def youtube(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or u.hostname not in HOSTS:
        raise ValueError("Solo enlaces de YouTube")
    return u


def playlist(url):
    """Lista los videos de una playlist (tope 500) sin descargarlos. Los Mix automáticos (list=RD...) son infinitos: no cuentan; RDCLAK (álbumes de YouTube Music) sí."""
    u = youtube(url)
    lid = parse_qs(u.query).get("list", [""])[0]
    if not lid or (lid.startswith("RD") and not lid.startswith("RDCLAK")):
        raise ValueError("Ese enlace no es una lista de reproducción")
    cmd = [*YTDLP, "--yes-playlist", "--flat-playlist", "--playlist-end", "500", "-J", "--encoding", "utf-8", "--", url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        err = next((l.strip() for l in reversed(p.stderr.splitlines()) if l.startswith("ERROR:")), "yt-dlp falló") if p.returncode else None
        data = None if err else json.loads(p.stdout)
        raw = data.get("entries") or [] if data else []
        entries = [{"id": e["id"], "title": e.get("title") or e["id"], "duration": e.get("duration"),
                    "url": f"https://www.youtube.com/watch?v={e['id']}", "thumb": f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg"}
                   for e in raw if e and re.fullmatch(r"[\w-]+", str(e.get("id") or ""))
                   and e.get("title") not in ("[Private video]", "[Deleted video]")]
    except subprocess.TimeoutExpired:
        err = "ERROR: yt-dlp tardó más de 120 s en leer la lista"
    except Exception as e:  # FileNotFoundError, JSON inválido...
        err = f"{type(e).__name__}: {e}"
    if err:
        msg, hlp = explain(err)
        log.error("Falló lista %s | error: %s | help: %s | yt-dlp: %s", url, msg, hlp, err)
        return {"ok": False, "error": msg, **({"help": hlp} if hlp else {})}
    if not entries:
        return {"ok": False, "error": "La lista está vacía o es privada"}
    count = data.get("playlist_count") or len(entries)
    # ponytail: "truncated" compara con lo que devolvió yt-dlp (con privados), no con lo que queda tras filtrar
    return {"ok": True, "title": data.get("title") or "Lista", "count": count, "entries": entries,
            "truncated": count > len(raw) or len(raw) >= 500}


def secs(x, top=86400):
    """Segundos: None o número finito entre 0 y top (24 h por defecto); un bool no cuenta."""
    if x is None:
        return None
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("Recorte inválido")
    try:
        ok = math.isfinite(x) and 0 <= x <= top
    except OverflowError:  # entero gigante
        ok = False
    if not ok:
        raise ValueError("Recorte inválido")
    return x


def trim(cut):
    """cut = (inicio, fin) en segundos, cualquiera puede ser None. Devuelve None (sin recorte) o (inicio, fin): inicio 0 pasa a None."""
    a, b = (None if x is None else round(secs(x), 3) for x in cut or (None, None))  # redondear antes de comparar
    if b is not None and b <= (a or 0):
        raise ValueError("Recorte inválido")
    a = a or None
    return None if a is None and b is None else (a, b)


def sections(a, b):
    f = lambda x: f"{x:.3f}".rstrip("0").rstrip(".")
    return f"*{f(a or 0)}-{'inf' if b is None else f(b)}"


def check_url(url):
    u = urlparse(url if isinstance(url, str) else "")
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("Pega un enlace web (http o https)")
    if u.hostname in HOSTS:  # reglas propias de YouTube; en otros sitios se baja un solo elemento (--no-playlist)
        if u.path.startswith("/playlist"):
            raise ValueError("Para listas, elige los videos primero")
        if u.path.startswith(("/@", "/channel/", "/c/", "/user/")):
            raise ValueError("Pega el enlace de un video, no de una lista o canal")


def new_job(fmt, cut=None, **extra):
    jid = secrets.token_urlsafe(16)
    JOBS[jid] = job = {"state": "running", "format": fmt, "stage": "queue", "part": 0, "label": "En cola", "title": None,
                       "percent": 0, "cut": cut, "downloaded": None, "total": None, "speed": None, "eta": None, **extra}
    return jid, job


def start(url, fmt, quality, browser=None, cut=None):
    """cut = (inicio, fin) en segundos; cualquiera puede ser None."""
    check_url(url)
    opts = QUALITY.get(fmt, {}).get(quality)
    if not opts:
        raise ValueError("Formato o calidad inválidos")
    cut = trim(cut)
    if cut:
        opts = opts + ["--download-sections", sections(*cut)]
        if fmt == "mp4":
            opts.append("--force-keyframes-at-cuts")  # corte exacto: recodifica el tramo
        else:
            opts = AUDIO + opts
        cut = list(cut)
    jid, job = new_job(fmt, cut)
    threading.Thread(target=run, args=(job, url, opts, tempfile.mkdtemp(dir=TMP.name), browser), daemon=True).start()
    return jid


def mix(tracks, crossfade, browser=None):
    """tracks = [{"url", "start", "end"}, ...]: de 2 a 50 pistas unidas en un MP3, con fundido cruzado de 0 a 10 s."""
    if not isinstance(tracks, list) or not 2 <= len(tracks) <= 50:
        raise ValueError("Un mix lleva de 2 a 50 pistas")
    try:
        if crossfade is None:
            raise ValueError
        crossfade = secs(crossfade, 10)
    except ValueError:
        raise ValueError("Fundido inválido: de 0 a 10 segundos") from None
    items = []
    for i, t in enumerate(tracks, 1):
        try:
            if not isinstance(t, dict):
                raise ValueError("Pista inválida")
            check_url(t.get("url"))
            items.append((t["url"], trim((t.get("start"), t.get("end")))))
        except ValueError as e:
            raise ValueError(f"Pista {i}: {e}") from None
    jid, job = new_job("mix", tracks=len(items), track=1)
    threading.Thread(target=run_mix, args=(job, items, crossfade, tempfile.mkdtemp(dir=TMP.name), browser), daemon=True).start()
    return jid


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # sin spam de /status cada segundo
        pass

    def trusted(self):
        """Solo esta misma página: bloquea que otro sitio abierto en tu navegador use el server (CSRF / DNS rebinding)."""
        port = self.server.server_address[1]
        allowed = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        if self.headers.get("Host") in allowed and (origin is None or origin.split("://", 1)[-1] in allowed):
            return True
        self.send(403, "Prohibido", "text/plain; charset=utf-8")
        return False

    def do_GET(self):
        if not self.trusted():
            return
        path = self.path.split("?")[0]
        if path in FILES:
            name, ctype = FILES[path]
            try:
                return self.send(200, (STATIC / name).read_bytes(), ctype)
            except OSError:
                return self.send(404, "No encontrado", "text/plain; charset=utf-8")
        if path == "/deps":
            return self.send(200, json.dumps({k: bool(shutil.which(k)) for k in INSTALL}), "application/json")
        if self.path.startswith("/status/"):
            job = JOBS.get(self.path[8:])
            if not job:
                return self.send(404, '{"state": "error", "error": "No existe"}', "application/json")
            return self.send(200, json.dumps({k: v for k, v in job.items() if k != "file"}), "application/json")
        jid = self.path[6:]
        if not self.path.startswith("/file/") or JOBS.get(jid, {}).get("state") != "done":
            return self.send(404, "No encontrado", "text/plain; charset=utf-8")
        job = JOBS.pop(jid, None)  # un solo uso
        if not job:  # otra petición ganó la carrera
            return self.send(404, "No encontrado", "text/plain; charset=utf-8")
        path = job["file"]
        try:
            name = Path(path).name
            ascii_name = name.encode("ascii", "replace").decode().replace('"', "'")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(path)))
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}")
            self.end_headers()
            with open(path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        except OSError as e:  # el navegador se desconectó a medias: que "Guardar archivo" pueda volver a pedirlo
            JOBS[jid] = job
            log.warning("Transferencia cortada de %s: %s", path, e)
        else:
            shutil.rmtree(Path(path).parent, ignore_errors=True)  # no se guarda nada

    def do_POST(self):
        if not self.trusted():
            return
        if self.path not in ("/download", "/playlist", "/mix"):
            return self.send(404, "{}", "application/json")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if self.path == "/playlist":
                res = playlist(req.get("url", ""))
            elif self.path == "/mix":
                res = {"ok": True, "id": mix(req.get("tracks"), req.get("crossfade", 0), browser_of(self.headers.get("User-Agent", "")))}
            else:
                res = {"ok": True, "id": start(req.get("url", ""), req.get("format"), req.get("quality", "best"),
                                                    browser_of(self.headers.get("User-Agent", "")),
                                                    (req.get("start"), req.get("end")))}
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        self.send(200, json.dumps(res), "application/json")


class Server(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"  # en Windows SO_REUSEADDR deja abrir dos servidores en el mismo puerto


def main():
    url = f"http://localhost:{PORT}"
    try:
        srv = Server(("127.0.0.1", PORT), H)  # solo tu máquina
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        print(f"Contenido a tu disco ya está abierto en {url}")
        webbrowser.open(url)
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(Path(__file__).parent / "descargador.log", encoding="utf-8"),
                                  logging.StreamHandler()])
    for dep, cmd in INSTALL.items():
        if not shutil.which(dep):
            log.warning("Falta %s. Instálalo con: %s", dep, cmd)
    log.info("Contenido a tu disco abierto en %s", url)
    print(f"Contenido a tu disco: abierto en {url}")
    webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    for sig in ("SIGHUP", "SIGTERM"):  # cerrar la terminal también borra los temporales
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), lambda *a: sys.exit(0))
    main()
