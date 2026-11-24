"""ACR MOD RECORDS: interfaz privada en localhost y captura local de solo lectura."""
import ctypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import re
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs

from records.capture import Recorder, SharedMemory
from records.inspect_save import InvalidSave, inspect
from records.match_result import match
from records.online import Online, publication_payload, request_json, SITE

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ACR_RECORDS_DATA", str(ROOT / "app-data")))
SAVE = Path(os.environ.get("LOCALAPPDATA", "")) / "acr/Saved/SaveGames/PlayerDataSaveSlot.sav"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_shared_file(path):
    """Handle breve, solo lectura y compartiendo lectura/escritura/borrado."""
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                               ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    api.CreateFileW.restype = ctypes.c_void_p
    api.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    api.ReadFile.restype = ctypes.c_int
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    api.CloseHandle.restype = ctypes.c_int
    handle = api.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer = ctypes.create_string_buffer(65536)
        count = ctypes.c_uint32()
        chunks, total = [], 0
        while True:
            if not api.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not count.value:
                return b"".join(chunks)
            total += count.value
            if total > 32 * 1024 * 1024:
                raise ValueError("El guardado excede el limite de lectura")
            chunks.append(buffer.raw[:count.value])
    finally:
        api.CloseHandle(handle)


class SaveWatch:
    def __init__(self, path=SAVE):
        self.path = path
        self.done = None

    def poll(self):
        before = self.path.stat()
        signature = (before.st_mtime_ns, before.st_size, before.st_ino)
        if signature == self.done or time.time() - before.st_mtime < 10:
            return None
        data = read_shared_file(self.path)
        after = self.path.stat()
        if signature != (after.st_mtime_ns, after.st_size, after.st_ino):
            return None
        report = inspect(data)
        self.done = signature
        return report


def stage_catalog():
    catalog = {}
    countries = {"gr": "Grecia", "ke": "Kenya", "es": "España", "be": "Bélgica", "mx": "México",
                 "pt": "Portugal", "it": "Italia", "fi": "Finlandia", "se": "Suecia", "hr": "Croacia",
                 "jp": "Japón", "nz": "Nueva Zelanda", "mc": "Montecarlo", "ee": "Estonia"}
    bundled = ROOT / "stages.json"
    if bundled.exists():
        return {item["id"].casefold(): {"name": item["name"], "country": item["country"], "slug": item["slug"]}
                for item in read_json(bundled)}
    for path in (ROOT.parent / "custom/data/stage_builds").glob("*.json"):
        try:
            item = read_json(path)
            game_id = item.get("variant_row")
            if game_id:
                catalog[game_id.casefold()] = {"name": item.get("stage_name") or item.get("track_name") or path.stem,
                                              "country": countries.get(path.stem[:2], path.stem[:2].upper()),
                                              "slug": path.stem}
        except (OSError, ValueError, TypeError):
            continue
    return catalog


def history(catalog, capture_dirs):
    results = {}
    for folder in capture_dirs:
        for path in sorted(folder.rglob("*.json")):
            try:
                attempt = read_json(path)
                if attempt.get("official_time_ms") is None or not attempt.get("trace_file"):
                    continue
                game_id = attempt.get("stage_game_id") or attempt.get("save_evidence", {}).get("stage_game_id", "")
                if game_id and game_id.casefold() not in catalog:
                    continue
                info = catalog.get(game_id.casefold(), {})
                if not info:
                    info = next((value for value in catalog.values() if value["slug"] == attempt.get("stage_id")), {})
                car = attempt["identity"][0]
                started = attempt.get("started_utc")
                if not started:
                    started = datetime.strptime(attempt["trace_file"].split("-")[0], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc).isoformat()
                results[attempt["trace_file"]] = {
                    "id": attempt.get("save_evidence", {}).get("result_id") or path.stem,
                    "stage": info.get("name", game_id or attempt.get("stage_id", "Tramo")),
                    "country": info.get("country", "Mapa mod"), "stage_game_id": game_id,
                    "car": car, "player": attempt["identity"][2],
                    "raw_time_ms": attempt["raw_time_ms"], "penalty_ms": attempt["penalty_ms"],
                    "official_time_ms": attempt["official_time_ms"], "started_utc": started,
                    "start_observed": attempt.get("start_observed"), "source": "local",
                    "can_publish": attempt.get("start_observed") is True and attempt.get("capture_status") == "closed" and bool(attempt.get("save_evidence", {}).get("result_id")),
                    "publication_status": attempt.get("publication", {}).get("status"),
                    "validation_reason": (attempt.get("publication", {}).get("validation") or {}).get("reason"),
                    "screen_confirmed": attempt.get("screenshot_evidence", {}).get("total_matches_save", False),
                }
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return sorted(results.values(), key=lambda row: row["started_utc"], reverse=True)


class Engine:
    def __init__(self, data=DATA, monitor=True):
        self.data = data
        data.mkdir(parents=True, exist_ok=True)
        self.catalog = stage_catalog()
        self.lock = threading.RLock()
        self.online = Online(data)
        self.stop = threading.Event()
        self.settings = {"auto_capture": True, "language": "en"}
        if (data / "settings.json").exists():
            self.settings.update(read_json(data / "settings.json"))
        if self.settings["language"] not in ("en", "es"):
            self.settings["language"] = "en"
        self.recorder = Recorder(data / "captures", "pendiente_de_identificar")
        self.watch = SaveWatch()
        self.report = None
        self.report_path = None
        self.live = None
        self.error = None
        self.window_closed_at = None
        self.items = history(self.catalog, [ROOT / "captures", data / "captures"])
        self.monitor = monitor
        self.thread = None

    def start(self):
        if self.monitor:
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def refresh_history(self):
        self.items = history(self.catalog, [ROOT / "captures", self.data / "captures"])

    def poll_save(self):
        try:
            report = self.watch.poll()
        except FileNotFoundError:
            self.error = "Todavía no encontramos un guardado de ACR."
            return
        except (OSError, InvalidSave, ValueError) as error:
            self.error = "No se pudo leer el resultado del juego; se reintentará."
            print("Guardado:", repr(error), flush=True)
            return
        if report is None:
            return
        directory = self.data / "save-reports"
        directory.mkdir(exist_ok=True)
        path = directory / (report["source_sha256"] + ".json")
        if not path.exists():
            write_json(path, report)
        self.report, self.report_path = report, path
        self.error = None

    def reconcile(self):
        if self.report is None:
            return
        for path in (self.data / "captures").glob("*.json"):
            attempt = read_json(path)
            baseline_file = attempt.get("baseline_report_file")
            if not baseline_file or attempt.get("official_time_ms") is not None:
                continue
            if attempt.get("result_status") == "unsupported_stage" and attempt.get("stage_game_id", "").casefold() not in self.catalog:
                continue
            if attempt.get("capture_status") != "closed":
                continue
            try:
                baseline = read_json(self.data / "save-reports" / baseline_file)
                result = match(baseline, self.report, attempt)
            except ValueError:
                continue
            if result["stage_game_id"].casefold() not in self.catalog:
                attempt.update(result_status="unsupported_stage", stage_game_id=result["stage_game_id"])
                write_json(path, attempt)
                continue
            result.pop("result_status", None)
            result_id = result["save_evidence"]["result_id"]
            if any(item["id"] == result_id for item in self.items):
                continue
            write_json(path, result)
            self.refresh_history()

    def tick(self, sample, now):
        with self.lock:
            self.live = sample
            if self.settings["auto_capture"] and self.report is not None:
                previous_path = self.recorder.path if self.recorder.active else None
                self.recorder.feed(sample, now)
                if self.recorder.active and self.recorder.path != previous_path:
                    self.recorder.active["baseline_report_file"] = self.report_path.name
                    self.recorder.checkpoint()
            elif self.recorder.active:
                self.recorder.close("capture_paused")

    def run(self):
        memory = SharedMemory()
        next_save_check = 0
        try:
            while not self.stop.is_set():
                now = time.monotonic()
                self.tick(memory.sample(), now)
                if now >= next_save_check:
                    with self.lock:
                        if self.recorder.active and self.recorder.candidate:
                            self.recorder.checkpoint()
                        self.poll_save()
                        if self.recorder.active and self.recorder.candidate and self.report:
                            attempt = dict(self.recorder.active, capture_status="closed")
                            baseline_file = attempt.get("baseline_report_file")
                            if baseline_file:
                                try:
                                    match(read_json(self.data / "save-reports" / baseline_file), self.report, attempt)
                                except ValueError:
                                    pass
                                else:
                                    self.recorder.close("result_saved")
                        self.reconcile()
                    next_save_check = now + 2
                if self.window_closed_at and now - self.window_closed_at > 3:
                    self.stop.set()
                self.stop.wait(0.2)
        except Exception as error:
            self.error = "La captura se detuvo por un error. Reinicia la aplicación."
            print("Motor:", repr(error), flush=True)
        finally:
            with self.lock:
                self.recorder.close("app_closed")
                self.reconcile()

    def state(self):
        with self.lock:
            active = self.recorder.active
            if not self.settings["auto_capture"]:
                status = "paused"
            elif self.error:
                status = "attention"
            elif self.report is None:
                status = "preparing"
            elif active:
                status = "waiting_result" if self.recorder.candidate else "recording"
            else:
                status = "ready" if self.live is not None else "game_closed"
            return {"app": "ACR MOD RECORDS", "version": "0.8.2", "status": status,
                    "connected": self.live is not None, "auto_capture": bool(self.settings["auto_capture"]),
                    "language": self.settings["language"],
                    "error": self.error, "live": None if self.live is None else {
                        key: self.live[key] for key in ("clock_ms", "car", "track_label", "speed_kmh", "player")},
                    "start_observed": active.get("start_observed") if active else None,
                    "history": list(self.items), "online_available": True, "account": self.online.status()}

    def publish(self, result_id):
        with self.lock:
            if not any(item["id"] == result_id and item["can_publish"] for item in self.items):
                raise ValueError("La pasada no tiene una captura completa publicable.")
            path = None
            for candidate in (self.data / "captures").glob("*.json"):
                if read_json(candidate).get("save_evidence", {}).get("result_id") == result_id:
                    path = candidate
                    break
            if path is None:
                raise ValueError("No encontramos la captura original en esta app.")
        payload = publication_payload(path)
        # La red no se ejecuta bajo el bloqueo del capturador.
        receipt = self.online.publish(payload)
        if receipt.get("status") not in ("pending", "accepted"):
            raise ValueError("El servidor no confirmó la pasada.")
        with self.lock:
            attempt = read_json(path)
            attempt["publication"] = receipt
            write_json(path, attempt)
            self.refresh_history()
        return receipt

    def set_language(self, language):
        if language not in ("en", "es"):
            raise ValueError("Invalid language")
        with self.lock:
            self.settings["language"] = language
            write_json(self.data / "settings.json", self.settings)

    def set_auto(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("auto_capture debe ser booleano")
        with self.lock:
            self.settings["auto_capture"] = enabled
            write_json(self.data / "settings.json", self.settings)
            if not enabled:
                self.recorder.close("capture_paused")

    def sync_publications(self):
        with self.lock:
            candidates=[]
            for path in (self.data / "captures").glob("*.json"):
                try:
                    publication=read_json(path).get("publication",{})
                    if publication.get("status")=="pending" and publication.get("id"):
                        candidates.append((path,publication["id"]))
                except (OSError,ValueError,TypeError):
                    continue
        updated=0
        for path,run_id in candidates[:20]:
            receipt=self.online.revalidate(run_id)
            if receipt.get("id")!=run_id or receipt.get("status") not in ("accepted","pending","rejected"):
                raise ValueError("El servidor no confirmó el estado del envío.")
            with self.lock:
                attempt=read_json(path)
                attempt["publication"]=receipt
                write_json(path,attempt)
                self.refresh_history()
                updated+=1
        return {"updated":updated}


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, engine):
        super().__init__(address, Handler)
        self.engine = engine
        self.token = os.urandom(24).hex()
        self.origin = "http://127.0.0.1:" + str(self.server_port)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, data, content_type="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == "127.0.0.1:" + str(self.server.server_port)

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, {"error": "Host no permitido"})
        path = urlsplit(self.path).path
        if path.startswith("/auth/callback/"):
            try:
                query = parse_qs(urlsplit(self.path).query)
                self.server.engine.online.callback(path.removeprefix("/auth/callback/"), query.get("code", [None])[0])
                message = ("Sesión iniciada. Ya puedes volver a ACR LAPS ONLINE y cerrar esta pestaña."
                           if self.server.engine.settings["language"] == "es" else
                           "Signed in. You can return to ACR LAPS ONLINE and close this tab.")
                code = 200
            except ValueError as error:
                message, code = str(error), 400
            return self.send(code, message.encode("utf-8"), "text/plain; charset=utf-8")
        if path.startswith("/api/"):
            if self.headers.get("X-App-Token") != self.server.token:
                return self.send(403, {"error": "Sesión no autorizada"})
            if path == "/api/state":
                self.server.engine.window_closed_at = None
                return self.send(200, self.server.engine.state())
            if path == "/api/account":
                try:
                    return self.send(200, self.server.engine.online.account())
                except ValueError as error:
                    return self.send(400, {"error": str(error)})
            if path == "/api/leaderboard":
                stage = parse_qs(urlsplit(self.path).query).get("stage", [""])[0]
                if not re.fullmatch(r"(?:Wrcg[A-Za-z0-9_]{1,90}|SandoChlBio(?:Rev)?Full)", stage):
                    return self.send(400, {"error": "Invalid stage"})
                try:
                    cached = getattr(self.server, "board_cache", None)
                    if not cached or cached[0] != stage or cached[1] < time.monotonic():
                        value = request_json(SITE + "/api/leaderboard?stage=" + stage)
                        if not isinstance(value.get("records"), list):
                            raise ValueError("Invalid leaderboard response")
                        cached = (stage, time.monotonic() + 60, value)
                        self.server.board_cache = cached
                    return self.send(200, cached[2])
                except ValueError as error:
                    return self.send(502, {"error": str(error)})
            return self.send(404, {"error": "Ruta inexistente"})
        files = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js", "/i18n.js": "i18n.js",
                 "/assets/hero.png": "assets/hero.png", "/assets/logo.svg": "assets/logo.svg"}
        if re.fullmatch(r"/flags/[a-z]{2}\.svg", path):
            files[path] = path[1:]
        if path not in files:
            return self.send(404, {"error": "Archivo inexistente"})
        file = ROOT / "ui" / files[path]
        try:
            content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self.send(200, file.read_bytes(), content_type)
        except OSError:
            self.send(404, {"error": "Archivo no disponible"})

    def do_POST(self):
        if not self.valid_host() or self.headers.get("Origin") != self.server.origin:
            return self.send(403, {"error": "Origen no permitido"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2048:
                return self.send(413, {"error": "Solicitud demasiado grande"})
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Se espera un objeto")
        except (ValueError, UnicodeError):
            return self.send(400, {"error": "Solicitud no válida"})
        token = self.headers.get("X-App-Token") or body.get("token")
        if token != self.server.token:
            return self.send(403, {"error": "Sesión no autorizada"})
        path = urlsplit(self.path).path
        if path == "/api/auth/start":
            try:
                return self.send(200, {"url": self.server.engine.online.start(self.server.origin)})
            except ValueError as error:
                return self.send(400, {"error": str(error)})
        if path == "/api/auth/logout":
            self.server.engine.online.logout()
            return self.send(200, {"ok": True})
        if path == "/api/account":
            if not isinstance(body.get("name"), str):
                return self.send(400, {"error": "Escribe tu nombre de piloto"})
            try:
                return self.send(200, self.server.engine.online.account(body["name"]))
            except ValueError as error:
                return self.send(400, {"error": str(error)})
        if path == "/api/publish":
            try:
                return self.send(200, self.server.engine.publish(body.get("id")))
            except (ValueError, OSError, KeyError, TypeError) as error:
                return self.send(400, {"error": str(error) if isinstance(error, ValueError) else "No se pudo preparar la captura."})
        if path == "/api/sync":
            try:
                return self.send(200, self.server.engine.sync_publications())
            except (ValueError,OSError) as error:
                return self.send(400,{"error":str(error) if isinstance(error,ValueError) else "No se pudo actualizar el estado del envío."})
        if path == "/api/language":
            try:
                self.server.engine.set_language(body.get("language"))
            except ValueError as error:
                return self.send(400, {"error": str(error)})
            return self.send(200, {"ok": True})
        if path == "/api/auto":
            try:
                self.server.engine.set_auto(body.get("enabled"))
            except ValueError as error:
                return self.send(400, {"error": str(error)})
            return self.send(200, {"ok": True})
        if path == "/api/window-closed":
            self.server.engine.window_closed_at = time.monotonic()
            return self.send(200, {"ok": True})
        if path == "/api/shutdown":
            self.server.engine.stop.set()
            self.send(200, {"ok": True})
            return
        return self.send(404, {"error": "Ruta inexistente"})


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = (DATA / "app.log").open("a", encoding="utf-8", buffering=1)
    runtime_path = DATA / "runtime.json"
    engine = Engine()
    server = AppServer(("127.0.0.1", 0), engine)
    write_json(runtime_path, {"origin": server.origin, "token": server.token})
    engine.start()
    print("ACR MOD RECORDS lista en localhost.", flush=True)
    try:
        server.timeout = 0.5
        while not engine.stop.is_set():
            server.handle_request()
    except KeyboardInterrupt:
        engine.stop.set()
    finally:
        engine.stop.set()
        if engine.thread:
            engine.thread.join(timeout=5)
        server.server_close()
        runtime_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

