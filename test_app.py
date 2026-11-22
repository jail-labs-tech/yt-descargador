"""Pruebas del descargador. Uso: python3 -m unittest -v
Sin red: usan un yt-dlp falso. YT_REAL=1 agrega una descarga real de YouTube."""
import http.client, json, os, shutil, socket, subprocess, sys, tempfile, threading, time, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import app

FAKE = r'''
import json, os, sys
args = sys.argv[1:]
title = os.environ.get("FAKE_TITLE", "Canción de prueba")
mode = os.environ.get("FAKE_MODE", "ok")
if os.environ.get("FAKE_LOG"):
    open(os.environ["FAKE_LOG"], "a", encoding="utf-8").write(" ".join(args) + "\n")
if "--flat-playlist" in args:
    if mode == "fail":
        print("ERROR: [youtube:tab] abc: Video unavailable", file=sys.stderr); sys.exit(1)
    if mode == "basura":
        print("no es json"); sys.exit(0)
    entries = [{"id": f"vid{i}", "title": f"Video {i}", "duration": 60 + i} for i in range(int(os.environ.get("FAKE_N", "3")))]
    entries += [{"id": "priv", "title": "[Private video]"}, {"title": "sin id"}]
    d = {"title": "Mi lista", "entries": entries}
    if "FAKE_COUNT" in os.environ:
        d["playlist_count"] = int(os.environ["FAKE_COUNT"])
    print(json.dumps(d)); sys.exit(0)
out = os.path.dirname(args[args.index("-o") + 1])
cookies = "--cookies-from-browser" in args
if os.environ.get("FAKE_BAD") and os.environ["FAKE_BAD"] in args[-1]:
    print("ERROR: [youtube] abc: Video unavailable"); sys.exit(1)
if mode == "fail":
    print("ERROR: [youtube] abc: Video unavailable"); sys.exit(1)
if mode == "botsiempre" or (mode == "bot" and not cookies):
    print("ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot. Use --cookies-from-browser"); sys.exit(1)
if mode == "cookiesmal":
    print("ERROR: failed to load cookies" if cookies else "ERROR: Sign in to confirm you\u2019re not a bot"); sys.exit(1)
ext = "mp3" if "-x" in args else "mp4"
print(f"[download] Destination: {out}/{title}.f299.mp4", flush=True)
print("PROG 50 100 NA 10 5", flush=True)
print("PROG 100 NA 200 10 0", flush=True)
if mode == "sinprog":
    print("PROG NA NA NA NA NA", flush=True)
if mode == "nofile":
    sys.exit(0)
print(f'[Merger] Merging formats into "{out}/{title}.{ext}"', flush=True)
open(os.path.join(out, f"{title}.{ext}"), "wb").write(b"datos " + ext.encode())
'''

FAKE_FFPROBE = r'''
import os
print(os.environ.get("FAKE_DUR", "10.0"))
'''
FAKE_FFMPEG = r'''
import os, sys
open(os.environ["FAKE_FFLOG"], "a", encoding="utf-8").write("\t".join(sys.argv[1:]) + "\n")
open(sys.argv[-1], "wb").write(b"mix final")
'''


def wait(jid, timeout=10):
    end = time.time() + timeout
    while app.JOBS[jid]["state"] == "running":
        assert time.time() < end, "la descarga no terminó"
        time.sleep(0.05)
    return app.JOBS[jid]


class FakeYtDlp(unittest.TestCase):
    """Cambia app.YTDLP por un yt-dlp falso (un script de Python, igual en todos los sistemas)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        script = os.path.join(cls.dir, "fake_ytdlp.py")
        Path(script).write_text(FAKE, encoding="utf-8")
        cls.log = os.path.join(cls.dir, "args.log")
        cls.patches = [mock.patch.object(app, "YTDLP", [sys.executable, script]),
                       mock.patch.dict(os.environ, {"PYTHONIOENCODING": "utf-8", "FAKE_LOG": cls.log})]
        for p in cls.patches:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        shutil.rmtree(cls.dir)

    def setUp(self):
        if os.path.exists(self.log):
            os.remove(self.log)

    def calls(self):  # una línea por ejecución del yt-dlp falso
        return Path(self.log).read_text(encoding="utf-8").splitlines() if os.path.exists(self.log) else []


class Validacion(unittest.TestCase):
    def setUp(self):
        self.run_patch = mock.patch.object(app, "run")  # no arrancar descargas
        self.run_patch.start()

    def tearDown(self):
        self.run_patch.stop()

    def test_acepta_enlaces_de_youtube(self):
        for url in ["https://www.youtube.com/watch?v=x", "http://youtube.com/watch?v=x", "https://youtu.be/x",
                    "https://m.youtube.com/watch?v=x", "https://music.youtube.com/watch?v=x"]:
            self.assertIn(app.start(url, "mp3", "best"), app.JOBS, url)

    def test_acepta_otros_sitios_http(self):
        for url in ["https://example.com/v", "http://vimeo.com/1", "https://youtube.com.evil.com/x",
                    "https://youtube.com@evil.com/x", "https://www.tiktok.com/@u/video/1",
                    "https://x.com/channel/1", "https://soundcloud.com/playlist/x"]:  # reglas de YouTube solo en HOSTS
            self.assertIn(app.start(url, "mp3", "best"), app.JOBS, url)

    def test_rechaza_esquemas_y_trucos(self):
        for url in ["ftp://youtube.com/x", "file:///etc/passwd", "data:text/plain,hola", "javascript:alert(1)",
                    "http:///x", "https://", "--exec=rm", "", "youtube.com/watch", "example.com"]:
            with self.assertRaisesRegex(ValueError, "enlace web", msg=url):
                app.start(url, "mp3", "best")

    def test_selector_mp4_cae_en_cualquier_formato(self):
        self.assertTrue(app.mp4()[1].endswith("/bv*+ba/b"))
        self.assertTrue(app.mp4(720)[1].endswith("/bv*[height<=720]+ba/b"))

    def opts(self, fmt, cut):
        with mock.patch.object(app.threading, "Thread") as t:
            jid = app.start("https://vimeo.com/1", fmt, "best", None, cut)
        return t.call_args.kwargs["args"][2], app.JOBS[jid]["cut"]

    def test_sin_recorte_el_comando_no_cambia(self):
        for cut in [None, (None, None), (None, None, ) ]:
            self.assertEqual(self.opts("mp3", cut), (app.QUALITY["mp3"]["best"], None))
        self.assertEqual(self.opts("mp4", (None, None)), (app.QUALITY["mp4"]["best"], None))

    def test_recorte_mp3_y_mp4(self):
        o, c = self.opts("mp3", (0, 10))
        self.assertEqual((o, c), (app.AUDIO + app.QUALITY["mp3"]["best"] + ["--download-sections", "*0-10"], [None, 10]))
        o, c = self.opts("mp4", (5, 10.5))
        self.assertEqual(o, app.QUALITY["mp4"]["best"] + ["--download-sections", "*5-10.5", "--force-keyframes-at-cuts"])
        self.assertEqual(c, [5, 10.5])

    def test_recorte_solo_inicio_o_solo_fin(self):
        self.assertEqual(self.opts("mp3", (12.5, None))[0][-2:], ["--download-sections", "*12.5-inf"])
        self.assertEqual(self.opts("mp3", (12.5, None))[0][:2], ["-f", "ba[ext=m4a]/ba/b"])  # recorte exacto en MP3
        self.assertEqual(self.opts("mp4", (12.5, None))[0].count("-f"), 1)  # mp4 conserva su selector
        self.assertEqual(self.opts("mp3", (None, 30))[0][-2:], ["--download-sections", "*0-30"])
        self.assertEqual(self.opts("mp4", (None, 30))[0][-3:], ["--download-sections", "*0-30", "--force-keyframes-at-cuts"])
        self.assertEqual(self.opts("mp3", (0.0000001, 86400))[0][-1], "*0-86400")  # sin notación científica
        self.assertEqual(self.opts("mp3", (86400, None))[0][-1], "*86400-inf")

    def test_start_cero_sin_fin_no_es_recorte(self):
        for cut in [(0, None), (0.0, None), (-0.0, None), (0.0004, None)]:
            self.assertEqual(self.opts("mp4", cut), (app.QUALITY["mp4"]["best"], None), cut)
        self.assertEqual(self.opts("mp3", (0, 10))[1], [None, 10])

    def test_recorte_invalido(self):
        for cut in [(None, 0), (None, -0.0), (0.0001, 0.0004), (0, 0.0004), (1, 1.0004), (None, 0.0004), (-1, 5), (5, 5), (10, 5), (0, 86401), (86401, None), ("5", 10), (None, "x"), (True, 10), (0, False),
                    (float("nan"), 5), (0, float("inf")), (float("-inf"), 5), (10**400, None), ([1], None)]:
            with self.assertRaisesRegex(ValueError, "Recorte inválido", msg=cut):
                app.start("https://vimeo.com/1", "mp3", "best", None, cut)

    def test_rechaza_playlists_y_canales(self):
        for url in ["https://www.youtube.com/playlist?list=PL1", "https://www.youtube.com/@canal",
                    "https://www.youtube.com/channel/UC1", "https://www.youtube.com/c/x", "https://www.youtube.com/user/x"]:
            with self.assertRaises(ValueError, msg=url):
                app.start(url, "mp3", "best")
        with self.assertRaisesRegex(ValueError, "elige los videos primero"):
            app.start("https://www.youtube.com/playlist?list=PL1", "mp3", "best")
        app.start("https://www.youtube.com/watch?v=x&list=PL1", "mp3", "best")  # video dentro de lista: solo el video

    def test_formato_y_calidad_en_lista_blanca(self):
        for fmt, q in [("mp3", "1080"), ("mp4", "320"), ("wav", "best"), (None, None), ("mp3", "999")]:
            with self.assertRaises(ValueError):
                app.start("https://youtu.be/x", fmt, q)
        for fmt, qs in app.QUALITY.items():
            for q in qs:
                app.start("https://youtu.be/x", fmt, q)

    def test_mp4_prefiere_h264_y_respeta_altura(self):
        self.assertTrue(app.mp4()[1].startswith("bv*[vcodec^=avc1]+ba[ext=m4a]"))
        self.assertIn("[height<=720]", app.mp4(720)[1])
        self.assertEqual(app.QUALITY["mp3"]["320"][-1], "320K")


class MixValidacion(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(app, "run_mix")  # no arrancar descargas
        p.start()
        self.addCleanup(p.stop)

    def t(self, n=2, **k):
        return [{"url": f"https://youtu.be/v{i}", "start": None, "end": None, **k} for i in range(n)]

    def test_numero_de_pistas(self):
        for tracks in [[], self.t(1), self.t(51), None, "x", {}]:
            with self.assertRaisesRegex(ValueError, "2 a 50"):
                app.mix(tracks, 0)
        for n in (2, 50):
            self.assertIn(app.mix(self.t(n), 0), app.JOBS)

    def test_crossfade_invalido(self):
        for cf in [-1, 10.5, 11, True, False, "2", None, float("nan"), float("inf"), 10**400, [1]]:
            with self.assertRaisesRegex(ValueError, "Fundido inválido", msg=cf):
                app.mix(self.t(), cf)
        for cf in [0, 0.5, 10, 3]:
            app.mix(self.t(), cf)

    def test_pista_invalida_dice_cual(self):
        casos = [("https://www.youtube.com/playlist?list=PL1", "Pista 1: Para listas"),
                 ("https://www.youtube.com/@canal", "Pista 1: Pega el enlace de un video"),
                 ("ftp://x.com/a", "Pista 1: Pega un enlace web"), (None, "Pista 1: Pega un enlace web")]
        for url, msg in casos:
            with self.assertRaisesRegex(ValueError, msg):
                app.mix([{"url": url}, *self.t(1)], 0)
        with self.assertRaisesRegex(ValueError, "Pista 1: Pista inválida"):
            app.mix(["x", *self.t(1)], 0)
        tracks = self.t(3)
        tracks[1].update(start=10, end=5)
        with self.assertRaisesRegex(ValueError, "^Pista 2: Recorte inválido$"):
            app.mix(tracks, 0)

    def test_job_inicial(self):
        job = app.JOBS[app.mix(self.t(3), 1)]
        self.assertEqual((job["format"], job["tracks"], job["track"], job["label"], job["state"]), ("mix", 3, 1, "En cola", "running"))


class MixFiltro(unittest.TestCase):
    pre = "[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}];"

    def norm(self, n):
        return "".join(self.pre.format(i=i) for i in range(n))

    def test_con_fundido(self):
        self.assertEqual(app.mix_filter(2, 2), self.norm(2) + "[a0][a1]acrossfade=d=2:c1=tri:c2=tri[out]")
        self.assertEqual(app.mix_filter(3, 1.5), self.norm(3) + "[a0][a1]acrossfade=d=1.5:c1=tri:c2=tri[x1];"
                         "[x1][a2]acrossfade=d=1.5:c1=tri:c2=tri[out]")

    def test_sin_fundido(self):
        self.assertEqual(app.mix_filter(2, 0), self.norm(2) + "[a0][a1]concat=n=2:v=0:a=1[out]")
        self.assertEqual(app.mix_filter(3, 0), self.norm(3) + "[a0][a1][a2]concat=n=3:v=0:a=1[out]")


class Utilidades(unittest.TestCase):
    def test_num(self):
        self.assertEqual(app.num("12.5"), 12.5)
        self.assertIsNone(app.num("NA"))

    def test_label(self):
        j = {"stage": "download", "format": "mp4", "part": 1}
        self.assertEqual(app.label(j), "Descargando video")
        self.assertEqual(app.label({**j, "part": 2}), "Descargando audio")
        self.assertEqual(app.label({**j, "stage": "convert"}), "Uniendo video y audio")
        self.assertEqual(app.label({**j, "format": "mp3", "stage": "convert"}), "Convirtiendo a MP3")
        self.assertEqual(app.label({"format": "mix", "stage": "convert", "track": 2, "tracks": 3}), "Descargando pista 2 de 3")


class Reintentos(unittest.TestCase):
    def job(self):
        return {"format": "mp4", "stage": "queue", "part": 0}

    def test_el_comando_lleva_un_solo_elemento_y_el_doble_guion(self):
        with mock.patch.object(app, "yt_dlp", return_value=None) as y:
            job = self.job()
            app.run(job, "https://vimeo.com/1", app.QUALITY["mp3"]["best"], tempfile.mkdtemp())
        cmd = y.call_args[0][1]
        self.assertEqual(cmd[-2:], ["--", "https://vimeo.com/1"])
        self.assertEqual(cmd[cmd.index("--no-playlist") + 1:cmd.index("--no-playlist") + 3], ["--playlist-items", "1"])

    def test_reintenta_403_y_termina(self):
        calls = []

        def fake(job, cmd):
            calls.append(1)
            if len(calls) < 3:
                return "ERROR: HTTP Error 403: Forbidden"
            (Path(cmd[cmd.index("-o") + 1]).parent / "v.mp4").write_bytes(b"x")

        with mock.patch.object(app, "yt_dlp", fake):
            job = self.job()
            app.run(job, "u", [], tempfile.mkdtemp())
        self.assertEqual((job["state"], len(calls)), ("done", 3))

    def test_se_rinde_tras_tres_403_y_borra_temporales(self):
        out = tempfile.mkdtemp()
        with mock.patch.object(app, "yt_dlp", return_value="ERROR: HTTP Error 403: Forbidden") as f:
            job = self.job()
            app.run(job, "u", [], out)
        self.assertEqual((job["state"], f.call_count), ("error", 3))
        self.assertFalse(Path(out).exists())

    def test_otros_errores_no_se_reintentan(self):
        with mock.patch.object(app, "yt_dlp", return_value="ERROR: Video unavailable") as f:
            job = self.job()
            app.run(job, "u", [], tempfile.mkdtemp())
        self.assertEqual((job["error"], f.call_count), (app.explain("Video unavailable")[0], 1))

    def test_maximo_tres_a_la_vez(self):
        lock, state = threading.Lock(), {"now": 0, "max": 0}

        def fake(job, cmd):
            with lock:
                state["now"] += 1
                state["max"] = max(state["max"], state["now"])
            time.sleep(0.2)
            with lock:
                state["now"] -= 1
            (Path(cmd[cmd.index("-o") + 1]).parent / "v.mp4").write_bytes(b"x")

        with mock.patch.object(app, "yt_dlp", fake):
            ts = [threading.Thread(target=app.run, args=(self.job(), "u", [], tempfile.mkdtemp())) for _ in range(7)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(state["max"], 3)


class Errores(unittest.TestCase):
    def test_traduccion_y_help(self):
        casos = [("ERROR: [youtube] x: Video unavailable", "no está disponible", None),
                 ("ERROR: [youtube] x: Private video. Sign in", "video privado", None),
                 ("ERROR: Postprocessing: ffprobe and ffmpeg not found. Please install", "Falta ffmpeg", "falta-ffmpeg"),
                 ("ERROR: ffmpeg not found", "Falta ffmpeg", "falta-ffmpeg"),
                 ("ERROR: [youtube] x: Sign in to confirm you\u2019re not a bot", "iniciar sesión", "bot"),
                 ("ERROR: [youtube] x: Sign in to confirm you're not a bot", "iniciar sesión", "bot"),
                 ("ERROR: [youtube] x: Sign in to confirm your age. This video may be inappropriate", "iniciar sesión", "bot"),
                 ("ERROR: This video is age-restricted", "iniciar sesión", "bot"),
                 ("ERROR: failed to load cookies", "cookies", "cookies"),
                 ("ERROR: could not find chrome cookies database in \"/x\"", "cookies", "cookies"),
                 ("ERROR: Failed to decrypt with DPAPI", "cookies", "cookies"),
                 ("ERROR: [Errno 1] Operation not permitted: '/Users/x/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies'",
                  "cookies", "cookies"),
                 ("ERROR: [Instagram] x: Requested content is not available, rate-limit reached or login required",
                  "El sitio pide iniciar sesión", "bot"),
                 ("ERROR: [vimeo] x: This video is only available for registered users. Use --cookies, --cookies-from-browser, "
                  "--username and --password, --netrc-cmd, or --netrc (vimeo) to provide account credentials. See  "
                  "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to manually pass cookies",
                  "El sitio pide iniciar sesión", "bot"),
                 ("ERROR: [twitter] x: NSFW tweet requires authentication. Use --cookies-from-browser or --cookies for the authentication.",
                  "El sitio pide iniciar sesión", "bot"),
                 ("ERROR: [facebook] x: You need to log in to access this content", "El sitio pide iniciar sesión", "bot"),
                 ("ERROR: [x] Login required", "El sitio pide iniciar sesión", "bot"),
                 ("ERROR: Unsupported URL: https://example.com/a", "Ese sitio no es compatible", "sitio"),
                 ("ERROR: HTTP Error 403: Forbidden", "actualizar yt-dlp", "actualizar"),
                 ("ERROR: algo raro de yt-dlp", "algo raro de yt-dlp", "actualizar"),
                 ("FileNotFoundError: yt-dlp", "Falta yt-dlp", "falta-ytdlp")]
        for err, texto, hlp in casos:
            msg, h = app.explain(err)
            self.assertIn(texto, msg, err)
            self.assertEqual(h, hlp, err)
        self.assertEqual(app.explain("ERROR: algo raro")[0], "algo raro")  # sin el prefijo

    def test_sin_ytdlp_instalado(self):
        job = {"format": "mp4", "stage": "queue", "part": 0}
        with mock.patch.object(app, "YTDLP", ["yt-dlp-que-no-existe"]):
            app.run(job, "u", [], tempfile.mkdtemp())
        self.assertEqual((job["state"], job["help"]), ("error", "falta-ytdlp"))
        self.assertEqual(job["error"], "Falta yt-dlp en tu equipo")

    def test_excepcion_inesperada_no_deja_el_job_en_running(self):
        d = tempfile.mkdtemp()
        noexec = os.path.join(d, "no-ejecutable")
        Path(noexec).write_text("hola")  # existe pero no es ejecutable: Popen lanza PermissionError / OSError
        job = {"format": "mp4", "stage": "queue", "part": 0}
        with mock.patch.object(app, "YTDLP", [noexec]):
            app.run(job, "u", [], tempfile.mkdtemp())
        shutil.rmtree(d)
        self.assertEqual(job["state"], "error")
        self.assertTrue(job["error"])

    def test_navegador_por_user_agent(self):
        edge = "Mozilla/5.0 Chrome/120.0 Safari/537.36 Edg/120.0"
        opera = "Mozilla/5.0 Chrome/120.0 Safari/537.36 OPR/105.0"
        firefox = "Mozilla/5.0 (Macintosh) Gecko/20100101 Firefox/121.0"
        chrome = "Mozilla/5.0 Chrome/120.0 Safari/537.36"
        safari = "Mozilla/5.0 (Macintosh) AppleWebKit/605 Version/17.0 Safari/605.1.15"
        for ua, nav in [(edge, "edge"), (opera, "opera"), (firefox, "firefox"), (chrome, "chrome"),
                        (safari, "safari"), ("curl/8.0", None), ("", None)]:
            self.assertEqual(app.browser_of(ua), nav, ua)


class Cookies(FakeYtDlp):
    def run_job(self, mode, browser):
        job = {"format": "mp4", "stage": "queue", "part": 0}
        with mock.patch.dict(os.environ, {"FAKE_MODE": mode}):
            app.run(job, "https://youtu.be/x", [], tempfile.mkdtemp(), browser)
        return job

    def test_reintenta_con_cookies_si_es_bot(self):
        job = self.run_job("bot", "firefox")
        self.assertEqual(job["state"], "done")
        c = self.calls()
        self.assertEqual(len(c), 2)
        self.assertNotIn("--cookies-from-browser", c[0])
        self.assertIn("--cookies-from-browser firefox", c[1])

    def test_sigue_el_bloqueo(self):
        job = self.run_job("botsiempre", "chrome")
        self.assertEqual((job["state"], job["help"]), ("error", "bot"))
        self.assertEqual(len(self.calls()), 2)  # una sola vez con cookies

    def test_cookies_que_fallan(self):
        job = self.run_job("cookiesmal", "chrome")
        self.assertEqual((job["state"], job["help"]), ("error", "cookies"))

    def test_sin_navegador_no_reintenta(self):
        job = self.run_job("botsiempre", None)
        self.assertEqual((job["state"], job["help"]), ("error", "bot"))
        self.assertEqual(len(self.calls()), 1)

    def test_otros_errores_no_usan_cookies(self):
        job = self.run_job("fail", "chrome")
        self.assertNotIn("help", job)
        self.assertEqual(len(self.calls()), 1)


class Mix(FakeYtDlp):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for name, code in (("ffmpeg", FAKE_FFMPEG), ("ffprobe", FAKE_FFPROBE)):
            Path(cls.dir, f"fake_{name}.py").write_text(code, encoding="utf-8")
        cls.fflog = os.path.join(cls.dir, "ffmpeg.log")
        cls.more = [mock.patch.object(app, "FFMPEG", [sys.executable, os.path.join(cls.dir, "fake_ffmpeg.py")]),
                    mock.patch.object(app, "FFPROBE", [sys.executable, os.path.join(cls.dir, "fake_ffprobe.py")]),
                    mock.patch.dict(os.environ, {"FAKE_FFLOG": cls.fflog})]
        for p in cls.more:
            p.start()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        for p in cls.more:
            p.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        if os.path.exists(self.fflog):
            os.remove(self.fflog)

    URLS = [f"https://youtu.be/v{i}" for i in range(3)]
    ITEMS = [(URLS[0], None), (URLS[1], (2, 7)), (URLS[2], (None, 5))]

    def run_mix(self, cf=1, items=None, out=None, **env):
        class Job(dict):  # guarda cada estado intermedio
            def update(self, **k):
                super().update(**k)
                seen.append(dict(self))

        seen = []
        job = Job(app.JOBS[app.new_job("mix", tracks=3, track=1)[0]])
        with mock.patch.dict(os.environ, env):
            app.run_mix(job, items or self.ITEMS, cf, out or tempfile.mkdtemp(dir=app.TMP.name))
        return job, seen

    def test_una_llamada_por_pista_con_sus_argumentos(self):
        job, seen = self.run_mix()
        self.assertEqual(job["state"], "done", job.get("error"))
        c = self.calls()
        self.assertEqual(len(c), 3)
        for line, url in zip(c, self.URLS):
            self.assertIn("-f ba[ext=m4a]/ba/b -x", line)
            self.assertNotIn("--audio-format", line)
            self.assertIn("--no-playlist --playlist-items 1", line)
            self.assertTrue(line.endswith(f"-- {url}"), line)
        self.assertNotIn("--download-sections", c[0])
        self.assertIn("--download-sections *2-7", c[1])
        self.assertIn("--download-sections *0-5", c[2])
        self.assertEqual(len({line.split(" -o ")[1] for line in c}), 3)  # una subcarpeta por pista
        labels = [s["label"] for s in seen]
        for l in ("Descargando pista 1 de 3", "Descargando pista 2 de 3", "Descargando pista 3 de 3", "Uniendo pistas"):
            self.assertIn(l, labels)
        self.assertLess(labels.index("Descargando pista 2 de 3"), labels.index("Uniendo pistas"))
        self.assertEqual((job["label"], job["name"], job["percent"]), ("Listo", "Mix (3 pistas).mp3", 100))
        pcts = [s["percent"] for s in seen if s["state"] == "running" and s["percent"] is not None]
        self.assertEqual(pcts, sorted(pcts))  # el avance total nunca retrocede
        self.assertTrue(all(p <= 90 for p in pcts))
        self.assertIsNone(next(s for s in seen if s["stage"] == "join")["percent"])  # barra indeterminada al unir

    def test_ffmpeg_recibe_filtro_y_salida(self):
        self.run_mix(cf=1)
        args = Path(self.fflog).read_text(encoding="utf-8").strip().split("\t")
        self.assertEqual(args.count("-i"), 3)
        self.assertEqual(args[args.index("-filter_complex") + 1], app.mix_filter(3, 1))
        self.assertEqual(args[args.index("-c:a") + 1:args.index("-c:a") + 5], ["libmp3lame", "-q:a", "0", args[-1]])
        self.run_mix(cf=0)
        self.assertIn("concat=n=3", Path(self.fflog).read_text(encoding="utf-8").splitlines()[-1])

    def test_fundido_se_limita_a_la_mitad_de_la_pista_mas_corta(self):
        self.run_mix(cf=10, FAKE_DUR="4")
        args = Path(self.fflog).read_text(encoding="utf-8").strip().split("\t")
        self.assertIn("acrossfade=d=2:", args[args.index("-filter_complex") + 1])

    def test_error_en_pista_2(self):
        out = tempfile.mkdtemp(dir=app.TMP.name)
        job, _ = self.run_mix(out=out, FAKE_BAD="v1")
        self.assertEqual((job["state"], job["error"]), ("error", "Pista 2: El video no está disponible (privado, borrado o bloqueado en tu país)"))
        self.assertNotIn("help", job)
        self.assertEqual(len(self.calls()), 2)  # la 3 ni se intenta
        self.assertFalse(os.path.exists(self.fflog))
        self.assertFalse(os.path.exists(out))

    def test_excepcion_inesperada_marca_error_y_limpia(self):
        out = tempfile.mkdtemp(dir=app.TMP.name)
        with mock.patch.object(Path, "mkdir", side_effect=PermissionError("sin permiso")):
            job, _ = self.run_mix(out=out)
        self.assertEqual(job["state"], "error")
        self.assertIn("sin permiso", job["error"])
        self.assertFalse(os.path.exists(out))

    def test_duracion_na_usa_el_fundido_pedido(self):
        with mock.patch.dict(os.environ, {"FAKE_DUR": "N/A"}):
            app.join(["a", "b"], 3, os.path.join(self.dir, "m.mp3"))
        self.assertIn("acrossfade=d=3:", Path(self.fflog).read_text(encoding="utf-8"))

    def test_sin_ytdlp_ni_ffmpeg(self):
        with mock.patch.object(app, "YTDLP", ["yt-dlp-que-no-existe"]):
            job, _ = self.run_mix()
        self.assertEqual((job["error"], job["help"]), ("Pista 1: Falta yt-dlp en tu equipo", "falta-ytdlp"))
        with mock.patch.object(app, "FFMPEG", ["ffmpeg-que-no-existe"]):
            job, _ = self.run_mix(cf=0)
        self.assertEqual((job["state"], job["error"], job["help"]), ("error", "Falta ffmpeg en tu equipo", "falta-ffmpeg"))

    def test_ocupa_un_solo_cupo(self):
        slots = mock.MagicMock()
        with mock.patch.object(app, "SLOTS", slots):
            job, _ = self.run_mix()
        self.assertEqual(job["state"], "done")
        self.assertEqual((slots.acquire.call_count, slots.release.call_count), (1, 1))

    def test_reintenta_403_por_pista(self):
        n = []

        def fake(job, cmd):
            n.append(cmd)
            if len(n) == 1:
                return "ERROR: HTTP Error 403: Forbidden"
            Path(cmd[cmd.index("-o") + 1]).parent.joinpath("a.m4a").write_bytes(b"x")

        with mock.patch.object(app, "yt_dlp", fake):
            job, _ = self.run_mix(items=[(self.URLS[0], None), (self.URLS[1], None)])
        self.assertEqual((job["state"], len(n)), ("done", 3))


    def post(self, body, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/mix", body=json.dumps(body), headers={"Host": f"127.0.0.1:{self.port}", **(headers or {})})
        r = c.getresponse()
        body = r.read()
        return r.status, json.loads(body) if r.status == 200 else body

    def test_validaciones_http(self):
        ok = [{"url": "https://youtu.be/a"}, {"url": "https://youtu.be/b"}]
        for body, err in [({"tracks": ok[:1], "crossfade": 0}, "2 a 50"), ({"tracks": ok * 26, "crossfade": 0}, "2 a 50"),
                          ({"tracks": ok, "crossfade": 11}, "Fundido inválido"), ({"tracks": ok, "crossfade": True}, "Fundido inválido"),
                          ({"tracks": [ok[0], {"url": "https://www.youtube.com/playlist?list=PL1"}], "crossfade": 0}, "Pista 2: Para listas"),
                          ({"tracks": [ok[0], {**ok[1], "start": 9, "end": 3}], "crossfade": 0}, "Pista 2: Recorte inválido")]:
            s, res = self.post(body)
            self.assertEqual((s, res["ok"]), (200, False), body)
            self.assertIn(err, res["error"])
        self.assertEqual(self.calls(), [])

    def test_bloquea_otros_sitios(self):
        self.assertEqual(self.post({"tracks": [], "crossfade": 0}, {"Origin": "https://evil.com"})[0], 403)

    def test_flujo_completo_y_archivo_de_un_solo_uso(self):
        tracks = [{"url": u, "start": s, "end": e} for u, (s, e) in zip(self.URLS, [(None, None), (2, 7), (0, 5)])]
        s, res = self.post({"tracks": tracks, "crossfade": 1})
        self.assertTrue(res["ok"], res)
        jid = res["id"]
        wait(jid)
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", f"/status/{jid}", headers={"Host": f"127.0.0.1:{self.port}"})
        st = json.loads(c.getresponse().read())
        self.assertEqual((st["state"], st["format"], st["tracks"], st["name"], st["percent"]), ("done", "mix", 3, "Mix (3 pistas).mp3", 100))
        self.assertNotIn("file", st)
        folder = Path(app.JOBS[jid]["file"]).parent
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", f"/file/{jid}", headers={"Host": f"127.0.0.1:{self.port}"})
        r = c.getresponse()
        self.assertEqual((r.status, r.read()), (200, b"mix final"))
        for _ in range(50):
            if not folder.exists():
                break
            time.sleep(0.02)
        self.assertFalse(folder.exists())
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", f"/file/{jid}", headers={"Host": f"127.0.0.1:{self.port}"})
        self.assertEqual(c.getresponse().status, 404)


class PuertoOcupado(unittest.TestCase):
    def test_avisa_abre_el_navegador_y_sale(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen()
            with mock.patch.object(app, "PORT", s.getsockname()[1]), mock.patch.object(app.webbrowser, "open") as op, \
                    mock.patch("builtins.print") as pr:
                app.main()
        op.assert_called_once()
        self.assertIn("Contenido a tu disco ya está abierto", pr.call_args[0][0])


class Progreso(FakeYtDlp):
    def test_parsea_progreso_titulo_y_conversion(self):
        out = tempfile.mkdtemp()
        seen = []

        class Job(dict):  # guarda cada estado intermedio
            def update(self, **k):
                super().update(**k)
                seen.append(dict(self))

        job = Job(format="mp4", stage="start", part=0)
        err = app.yt_dlp(job, [*app.YTDLP, "-o", f"{out}/%(title)s.%(ext)s", "--", "u"])
        self.assertIsNone(err)
        self.assertEqual(job["title"], "Canción de prueba")  # sin ".f299.mp4"
        self.assertIn(50.0, [s.get("percent") for s in seen])
        last_dl = [s for s in seen if s.get("downloaded") == 100][0]
        self.assertEqual(last_dl["total"], 200)  # usa total_bytes_estimate cuando total es NA
        self.assertEqual((job["stage"], job["percent"], job["label"]), ("convert", None, "Uniendo video y audio"))
        shutil.rmtree(out)

    def test_sin_porcentaje_no_rompe(self):  # con --download-sections yt-dlp usa ffmpeg y puede no dar progreso
        job = {"format": "mp3", "stage": "start", "part": 0}
        with mock.patch.dict(os.environ, {"FAKE_MODE": "sinprog"}):
            self.assertIsNone(app.yt_dlp(job, [*app.YTDLP, "-o", f"{tempfile.mkdtemp()}/%(title)s.%(ext)s", "--", "u"]))
        self.assertEqual(job["percent"], None)  # tras convertir; antes fue 0 sin total
        self.assertIsNone(job["total"])

    def test_devuelve_error_de_ytdlp(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "fail"}):
            err = app.yt_dlp({"format": "mp4", "stage": "start", "part": 0}, [*app.YTDLP, "-o", "/x/y", "--", "u"])
        self.assertEqual(err, "ERROR: [youtube] abc: Video unavailable")

    def test_sin_archivo_da_error_claro(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "nofile"}):
            job = {"format": "mp4", "stage": "start", "part": 0}
            app.run(job, "u", [], tempfile.mkdtemp())
        self.assertEqual(job["state"], "error")
        self.assertIn("no generó", job["error"])


class Servidor(FakeYtDlp):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        super().tearDownClass()

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        c.request(method, path, body=json.dumps(body) if isinstance(body, dict) else body, headers=h)
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def download(self, fmt="mp3", quality="best"):
        s, _, b = self.req("POST", "/download", {"url": "https://youtu.be/x", "format": fmt, "quality": quality})
        res = json.loads(b)
        self.assertTrue(res["ok"], res)
        return res["id"]

    def test_pagina(self):
        s, h, b = self.req("GET", "/")
        self.assertEqual(s, 200)
        self.assertEqual(b, (Path(app.__file__).parent / "static" / "index.html").read_bytes())
        self.assertEqual(h["Content-Type"], "text/html; charset=utf-8")

    def test_estaticos_y_rutas_desconocidas(self):
        for path, ctype in [("/styles.css", "text/css"), ("/app.js", "text/javascript")]:
            s, h, b = self.req("GET", path)
            self.assertEqual(s, 200, path)
            self.assertTrue(h["Content-Type"].startswith(ctype), path)
            self.assertTrue(b)
        for path in ["/../app.py", "/app.py", "/static/app.js", "/%2e%2e/app.py", "/otra"]:
            self.assertEqual(self.req("GET", path)[0], 404, path)

    def test_deps(self):
        with mock.patch.object(app.shutil, "which", side_effect=lambda n: "/x/ffmpeg" if n == "ffmpeg" else None):
            s, _, b = self.req("GET", "/deps")
        self.assertEqual((s, json.loads(b)), (200, {"yt-dlp": False, "ffmpeg": True}))

    def test_transferencia_cortada_deja_el_archivo_disponible(self):
        jid = self.download()
        wait(jid)
        folder = Path(app.JOBS[jid]["file"]).parent
        with mock.patch.object(app.shutil, "copyfileobj", side_effect=BrokenPipeError):
            try:
                self.req("GET", f"/file/{jid}")
            except (http.client.HTTPException, OSError):
                pass  # el server cortó la conexión a medias
        for _ in range(50):
            if jid in app.JOBS:
                break
            time.sleep(0.02)
        self.assertTrue(folder.exists())
        self.assertEqual(app.JOBS[jid]["state"], "done")
        s, _, b = self.req("GET", f"/file/{jid}")  # el botón "Guardar archivo" lo vuelve a pedir
        self.assertEqual((s, b), (200, b"datos mp3"))
        for _ in range(50):
            if not folder.exists():
                break
            time.sleep(0.02)
        self.assertFalse(folder.exists())
        self.assertEqual(self.req("GET", f"/file/{jid}")[0], 404)

    def test_cookies_segun_user_agent_del_post(self):
        ua = {"User-Agent": "Mozilla/5.0 Chrome/120.0 Safari/537.36"}
        with mock.patch.dict(os.environ, {"FAKE_MODE": "bot"}):
            s, _, b = self.req("POST", "/download", {"url": "https://youtu.be/x", "format": "mp3"}, ua)
            st = wait(json.loads(b)["id"])
        self.assertEqual(st["state"], "done")
        self.assertIn("--cookies-from-browser chrome", self.calls()[-1])

    def test_flujo_completo_y_archivo_de_un_solo_uso(self):
        jid = self.download("mp4", "720")
        wait(jid)
        s, _, b = self.req("GET", f"/status/{jid}")
        st = json.loads(b)
        self.assertEqual((st["state"], st["name"], st["percent"]), ("done", "Canción de prueba.mp4", 100))
        self.assertNotIn("file", st)  # no expone rutas del disco
        folder = Path(app.JOBS[jid]["file"]).parent
        s, h, b = self.req("GET", f"/file/{jid}")
        self.assertEqual((s, b), (200, b"datos mp4"))
        self.assertIn("filename*=UTF-8''Canci%C3%B3n%20de%20prueba.mp4", h["Content-Disposition"])
        for _ in range(50):  # el server borra justo después de enviar
            if not folder.exists():
                break
            time.sleep(0.02)
        self.assertFalse(folder.exists())  # no guarda nada
        self.assertEqual(self.req("GET", f"/file/{jid}")[0], 404)

    def test_nombre_con_comillas_no_rompe_cabecera(self):
        # Windows no permite comillas en nombres de archivo: ahí solo se prueban ñ y acentos
        title, ascii_name = ('Hola "mundo" ñ', "Hola 'mundo' ?") if os.name != "nt" else ("Canción ñandú", "Canci?n ?and?")
        with mock.patch.dict(os.environ, {"FAKE_TITLE": title}):
            jid = self.download()
            wait(jid)
        s, h, _ = self.req("GET", f"/file/{jid}")
        self.assertEqual(s, 200)
        self.assertIn(f'filename="{ascii_name}.mp3"', h["Content-Disposition"])

    def playlist(self, url, **env):
        with mock.patch.dict(os.environ, env):
            s, _, b = self.req("POST", "/playlist", {"url": url})
        self.assertEqual(s, 200)
        return json.loads(b)

    def test_playlist_filtra_y_da_el_formato_del_contrato(self):
        for url in ["https://www.youtube.com/playlist?list=PL1", "https://www.youtube.com/watch?v=x&list=PL1",
                    "https://music.youtube.com/playlist?list=RDCLAK5uy_x"]:  # RDCLAK = álbum de YT Music, no es Mix
            res = self.playlist(url, FAKE_COUNT="5")  # 5 = 3 videos + 1 privado + 1 sin id
            self.assertEqual((res["ok"], res["title"], res["count"], res["truncated"]), (True, "Mi lista", 5, False), url)
            self.assertEqual([e["id"] for e in res["entries"]], ["vid0", "vid1", "vid2"])
            self.assertEqual(res["entries"][1], {"id": "vid1", "title": "Video 1", "duration": 61,
                                                 "url": "https://www.youtube.com/watch?v=vid1",
                                                 "thumb": "https://i.ytimg.com/vi/vid1/mqdefault.jpg"})
        self.assertEqual(self.playlist("https://www.youtube.com/playlist?list=PL1")["count"], 3)  # sin playlist_count

    def test_playlist_truncada(self):
        url = "https://www.youtube.com/playlist?list=PL1"
        self.assertTrue(self.playlist(url, FAKE_COUNT="1200")["truncated"])  # la lista real es más grande
        self.assertTrue(self.playlist(url, FAKE_N="498")["truncated"])  # 500 entradas = se llegó al tope

    def test_playlist_pasa_los_argumentos_seguros(self):
        url = "https://www.youtube.com/playlist?list=PL1"
        self.playlist(url)
        c = self.calls()[-1]
        for flag in ["--yes-playlist", "--flat-playlist", "--playlist-end 500", "-J"]:
            self.assertIn(flag, c)
        self.assertTrue(c.endswith(f"-- {url}"), c)

    def test_playlist_rechaza_lo_que_no_es_lista_o_no_es_youtube(self):
        for url in ["https://youtu.be/x", "https://www.youtube.com/watch?v=x", "https://www.youtube.com/watch?v=x&list=RDx",
                    "https://www.youtube.com/playlist?list=RDabc", "https://www.youtube.com/playlist?list="]:
            res = self.playlist(url)
            self.assertEqual((res["ok"], res["error"]), (False, "Ese enlace no es una lista de reproducción"), url)
        for url in ["https://evil.com/playlist?list=PL1", "ftp://youtube.com/playlist?list=PL1",
                    "https://youtube.com.evil.com/playlist?list=PL1", ""]:
            res = self.playlist(url)
            self.assertEqual((res["ok"], res["error"]), (False, "Solo enlaces de YouTube"), url)
        self.assertEqual(self.calls(), [])  # ni siquiera llamó a yt-dlp

    def test_playlist_errores_traducidos(self):
        url = "https://www.youtube.com/playlist?list=PL1"
        res = self.playlist(url, FAKE_MODE="fail")
        self.assertFalse(res["ok"])
        self.assertIn("no está disponible", res["error"])
        self.assertNotIn("help", res)
        self.assertEqual(self.playlist(url, FAKE_MODE="basura")["ok"], False)  # JSON inválido
        self.assertEqual(self.playlist(url, FAKE_N="0")["error"], "La lista está vacía o es privada")
        with mock.patch.object(app, "YTDLP", ["yt-dlp-que-no-existe"]):
            res = self.playlist(url)
        self.assertEqual((res["ok"], res["help"]), (False, "falta-ytdlp"))

    def test_playlist_bloquea_otros_sitios(self):
        s, _, _ = self.req("POST", "/playlist", {"url": "https://www.youtube.com/playlist?list=PL1"}, {"Origin": "https://evil.com"})
        self.assertEqual(s, 403)

    def test_error_llega_al_status(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "fail"}):
            jid = self.download()
            st = wait(jid)
        self.assertEqual(st["state"], "error")
        self.assertIn("no está disponible", st["error"])
        self.assertNotIn("help", st)

    def test_peticiones_invalidas(self):
        self.assertEqual(self.req("GET", "/status/nope")[0], 404)
        self.assertEqual(self.req("GET", "/file/nope")[0], 404)
        self.assertEqual(self.req("POST", "/otra", {})[0], 404)
        for body in ["no es json", {"url": "ftp://evil.com", "format": "mp3"},
                     {"url": "https://youtu.be/x", "format": "mp3", "start": -1},
                     '{"url": "https://youtu.be/x", "format": "mp3", "start": NaN}',
                     '{"url": "https://youtu.be/x", "format": "mp3", "end": Infinity}']:
            s, _, b = self.req("POST", "/download", body)
            self.assertFalse(json.loads(b)["ok"])
        s, _, b = self.req("POST", "/download", {"url": "https://youtu.be/x", "format": "mp3", "start": 5, "end": 2})
        self.assertEqual(json.loads(b), {"ok": False, "error": "Recorte inválido"})

    def test_recorte_llega_al_status_y_al_comando(self):
        s, _, b = self.req("POST", "/download", {"url": "https://youtu.be/x", "format": "mp3", "start": 1, "end": 2.5})
        jid = json.loads(b)["id"]
        wait(jid)
        self.assertEqual(json.loads(self.req("GET", f"/status/{jid}")[2])["cut"], [1, 2.5])
        self.assertIn("--download-sections *1-2.5", self.calls()[-1])
        jid = self.download()
        wait(jid)
        self.assertIsNone(json.loads(self.req("GET", f"/status/{jid}")[2])["cut"])
        self.assertNotIn("--download-sections", self.calls()[-1])

    def test_bloquea_otros_sitios(self):
        good = {"url": "https://youtu.be/x", "format": "mp3"}
        self.assertEqual(self.req("POST", "/download", good, {"Origin": "https://evil.com"})[0], 403)
        self.assertEqual(self.req("GET", "/", headers={"Host": "evil.com"})[0], 403)  # DNS rebinding
        s, _, b = self.req("POST", "/download", good, {"Origin": f"http://localhost:{self.port}",
                                                       "Host": f"localhost:{self.port}"})
        self.assertTrue(json.loads(b)["ok"])
        wait(json.loads(b)["id"])


@unittest.skipUnless(os.environ.get("YT_REAL"), "YT_REAL=1 para probar contra YouTube de verdad")
class Real(unittest.TestCase):
    def test_descarga_real_mp3_y_mp4(self):
        for fmt, q in [("mp3", "128"), ("mp4", "360")]:
            jid = app.start("https://youtu.be/jNQXAC9IVRw", fmt, q)  # "Me at the zoo", 19 s
            st = wait(jid, timeout=180)
            self.assertEqual(st["state"], "done", st.get("error"))
            self.assertGreater(os.path.getsize(st["file"]), 10_000)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "falta ffmpeg")
    def test_recortes_y_mix_reales(self):
        def dur(f):
            return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                        capture_output=True, text=True).stdout)

        url = "https://youtu.be/jNQXAC9IVRw"
        st = wait(app.start(url, "mp3", "best", None, (2, 7)), timeout=180)
        self.assertEqual(st["state"], "done", st.get("error"))
        self.assertAlmostEqual(dur(st["file"]), 5, delta=1)  # sin -f m4a salían ~10 s de más
        jid = app.mix([{"url": url, "start": 2, "end": 7}, {"url": url, "start": 10, "end": 15}], 1)
        st = wait(jid, timeout=240)
        self.assertEqual(st["state"], "done", st.get("error"))
        self.assertAlmostEqual(dur(st["file"]), 9, delta=1.5)  # 5 + 5 - 1 s de fundido


if __name__ == "__main__":
    unittest.main()
