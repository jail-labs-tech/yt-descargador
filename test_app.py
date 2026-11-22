"""Pruebas del descargador. Uso: python3 -m unittest -v
Sin red: usan un yt-dlp falso. YT_REAL=1 agrega una descarga real de YouTube."""
import http.client, json, os, shutil, stat, sys, tempfile, threading, time, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import app

FAKE = r'''#!PYTHON
import os, sys
args = sys.argv[1:]
out = os.path.dirname(args[args.index("-o") + 1])
title = os.environ.get("FAKE_TITLE", "Canción de prueba")
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "fail":
    print("ERROR: [youtube] abc: Video unavailable"); sys.exit(1)
ext = "mp3" if "-x" in args else "mp4"
print(f"[download] Destination: {out}/{title}.f299.mp4", flush=True)
print("PROG 50 100 NA 10 5", flush=True)
print("PROG 100 NA 200 10 0", flush=True)
if mode == "nofile":
    sys.exit(0)
print(f'[Merger] Merging formats into "{out}/{title}.{ext}"', flush=True)
open(os.path.join(out, f"{title}.{ext}"), "wb").write(b"datos " + ext.encode())
'''


def wait(jid, timeout=10):
    end = time.time() + timeout
    while app.JOBS[jid]["state"] == "running":
        assert time.time() < end, "la descarga no terminó"
        time.sleep(0.05)
    return app.JOBS[jid]


@unittest.skipIf(os.name == "nt", "el yt-dlp falso es un script POSIX")
class FakeYtDlp(unittest.TestCase):
    """Pone un yt-dlp falso al frente del PATH."""

    @classmethod
    def setUpClass(cls):
        cls.bin = tempfile.mkdtemp()
        exe = Path(cls.bin) / "yt-dlp"
        exe.write_text(FAKE.replace("PYTHON", sys.executable), encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
        cls.env = mock.patch.dict(os.environ, {"PATH": cls.bin + os.pathsep + os.environ["PATH"]})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        shutil.rmtree(cls.bin)


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

    def test_rechaza_otros_sitios_y_trucos(self):
        for url in ["https://example.com", "ftp://youtube.com/x", "https://youtube.com.evil.com/x",
                    "https://youtube.com@evil.com/x", "file:///etc/passwd", "--exec=rm", "", "youtube.com/watch"]:
            with self.assertRaises(ValueError, msg=url):
                app.start(url, "mp3", "best")

    def test_rechaza_playlists_y_canales(self):
        for url in ["https://www.youtube.com/playlist?list=PL1", "https://www.youtube.com/@canal",
                    "https://www.youtube.com/channel/UC1", "https://www.youtube.com/c/x", "https://www.youtube.com/user/x"]:
            with self.assertRaises(ValueError, msg=url):
                app.start(url, "mp3", "best")
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


class Reintentos(unittest.TestCase):
    def job(self):
        return {"format": "mp4", "stage": "queue", "part": 0}

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
        self.assertEqual((job["error"], f.call_count), ("ERROR: Video unavailable", 1))

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


class Progreso(FakeYtDlp):
    def test_parsea_progreso_titulo_y_conversion(self):
        out = tempfile.mkdtemp()
        seen = []

        class Job(dict):  # guarda cada estado intermedio
            def update(self, **k):
                super().update(**k)
                seen.append(dict(self))

        job = Job(format="mp4", stage="start", part=0)
        err = app.yt_dlp(job, ["yt-dlp", "-o", f"{out}/%(title)s.%(ext)s", "--", "u"])
        self.assertIsNone(err)
        self.assertEqual(job["title"], "Canción de prueba")  # sin ".f299.mp4"
        self.assertIn(50.0, [s.get("percent") for s in seen])
        last_dl = [s for s in seen if s.get("downloaded") == 100][0]
        self.assertEqual(last_dl["total"], 200)  # usa total_bytes_estimate cuando total es NA
        self.assertEqual((job["stage"], job["percent"], job["label"]), ("convert", None, "Uniendo video y audio"))
        shutil.rmtree(out)

    def test_devuelve_error_de_ytdlp(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "fail"}):
            err = app.yt_dlp({"format": "mp4", "stage": "start", "part": 0}, ["yt-dlp", "-o", "/x/y", "--", "u"])
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
        self.assertIn(b"<textarea", b)

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
        with mock.patch.dict(os.environ, {"FAKE_TITLE": 'Hola "mundo" ñ'}):
            jid = self.download()
            wait(jid)
        s, h, _ = self.req("GET", f"/file/{jid}")
        self.assertEqual(s, 200)
        self.assertIn("filename=\"Hola 'mundo' ?.mp3\"", h["Content-Disposition"])

    def test_error_llega_al_status(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "fail"}):
            jid = self.download()
            st = wait(jid)
        self.assertEqual(st["state"], "error")
        self.assertIn("Video unavailable", st["error"])

    def test_peticiones_invalidas(self):
        self.assertEqual(self.req("GET", "/status/nope")[0], 404)
        self.assertEqual(self.req("GET", "/file/nope")[0], 404)
        self.assertEqual(self.req("POST", "/otra", {})[0], 404)
        for body in ["no es json", {"url": "https://evil.com", "format": "mp3"}]:
            s, _, b = self.req("POST", "/download", body)
            self.assertFalse(json.loads(b)["ok"])

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


if __name__ == "__main__":
    unittest.main()
