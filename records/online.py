"""Discord PKCE; solo la clave pública viaja al cliente. Sesión protegida por Windows."""
import base64
import ctypes
import hashlib
import json
import math
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SITE = "https://acrsplits.online"
SUPABASE = "https://yhqsxrqzkzroesbxvzka.supabase.co"


def publication_payload(path):
    attempt = json.loads(path.read_text(encoding="utf-8-sig"))
    evidence = attempt.get("save_evidence", {})
    if attempt.get("start_observed") is not True or attempt.get("capture_status") != "closed" or not evidence.get("result_id"):
        raise ValueError("Esta pasada no tiene un inicio completo y un resultado nuevo del guardado. Haz una nueva captura con la app abierta.")
    trace = path.parent / attempt["trace_file"]
    if trace.resolve().parent != path.parent.resolve() or trace.suffix != ".jsonl":
        raise ValueError("Ruta de captura no válida.")
    points, last = [], None
    with trace.open(encoding="utf-8") as source:
        for line in source:
            if len(line) > 20000:
                raise ValueError("Muestra demasiado grande.")
            sample = json.loads(line)
            if "clock_ms" not in sample or sample["clock_ms"] > attempt["raw_time_ms"]:
                continue
            point = [sample["elapsed_s"], sample["clock_ms"], sample["distance_m"],
                     *sample["xyz_m"], sample["speed_kmh"]]
            if len(point) != 7 or not all(type(n) in (int, float) and math.isfinite(n) for n in point):
                raise ValueError("La captura contiene muestras no válidas.")
            last = point
            if not points or point[0] - points[-1][0] >= 1:
                points.append(point)
            if point[1] == attempt["raw_time_ms"]:
                break
            if len(points) > 8000:
                raise ValueError("La captura es demasiado larga.")
    if last and (not points or last[0] != points[-1][0]):
        points.append(last)
    return {"stage_id": attempt["stage_game_id"], "car_id": evidence["car_game_id"],
            "result_hash": evidence["result_id"], "raw_time_ms": attempt["raw_time_ms"],
            "penalty_ms": attempt["penalty_ms"], "start_observed": True, "points": points}


def request_json(url, data=None, headers=None):
    payload = None if data is None else json.dumps(data, allow_nan=False).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read(1024 * 1024))
    except HTTPError as error:
        # Nunca incluir respuestas OAuth, URLs o tokens en el log o la interfaz.
        if url.startswith(SITE + "/api/"):
            try:
                message = json.loads(error.read(10000)).get("error")
                if isinstance(message, str) and len(message) <= 300:
                    raise ValueError(message) from None
            except (json.JSONDecodeError, UnicodeError, AttributeError):
                pass
        raise ValueError("El servicio rechazó la solicitud (%s)." % error.code) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("No se pudo conectar. Comprueba Internet y vuelve a intentarlo.") from None


def protect(data, decrypt=False):
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint32), ("data", ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    target = Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    function = api.CryptUnprotectData if decrypt else api.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError("Windows no pudo proteger o recuperar la sesión. Vuelve a iniciar sesión.")
    kernel = ctypes.WinDLL("kernel32")
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class Online:
    def __init__(self, data):
        self.path = data / "session.bin"
        self.lock = threading.RLock()
        self.session = None
        self.pending = None
        self.key = None
        self.profile = None
        if self.path.exists():
            try:
                self.session = json.loads(protect(self.path.read_bytes(), decrypt=True))
            except (OSError, ValueError):
                pass

    def config(self):
        if self.key is None:
            config = request_json(SITE + "/api/config")
            if config.get("supabase_url") != SUPABASE or not config.get("publishable_key", "").startswith("sb_publishable_"):
                raise ValueError("La configuración online no es válida.")
            self.key = config["publishable_key"]
        return self.key

    def start(self, origin):
        with self.lock:
            self.config()
            verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            nonce = os.urandom(24).hex()
            self.pending = (nonce, verifier, time.monotonic() + 600)
            return SUPABASE + "/auth/v1/authorize?" + urlencode({
                "provider": "discord", "redirect_to": origin + "/auth/callback/" + nonce,
                "code_challenge": challenge, "code_challenge_method": "s256"})

    def callback(self, nonce, code):
        with self.lock:
            if not self.pending or self.pending[0] != nonce or self.pending[2] < time.monotonic():
                raise ValueError("El inicio de sesión ha caducado. Inténtalo desde la app.")
            _, verifier, _ = self.pending
            self.pending = None
            if not isinstance(code, str) or not 1 <= len(code) <= 4096:
                raise ValueError("Discord no devolvió un código válido.")
            session = request_json(SUPABASE + "/auth/v1/token?grant_type=pkce",
                                   {"auth_code": code, "code_verifier": verifier}, {"apikey": self.config()})
            self.save(session)

    def save(self, session):
        user = session.get("user", {})
        if not any(identity.get("provider") == "discord" for identity in user.get("identities", [])):
            raise ValueError("Se requiere una cuenta de Discord.")
        # Los tokens del proveedor Discord no se conservan: solo la sesión de nuestra app.
        stored = {key: session[key] for key in ("access_token", "refresh_token", "expires_in", "user")}
        stored["expires_at"] = time.time() + stored["expires_in"]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(protect(json.dumps(stored).encode()))
        temporary.replace(self.path)
        self.session = stored

    def access_token(self):
        with self.lock:
            if not self.session:
                raise ValueError("Inicia sesión con Discord primero.")
            if self.session["expires_at"] < time.time() + 60:
                session = request_json(SUPABASE + "/auth/v1/token?grant_type=refresh_token",
                                       {"refresh_token": self.session["refresh_token"]}, {"apikey": self.config()})
                self.save(session)
            return self.session["access_token"]

    def status(self):
        session = self.session
        if not session:
            return {"signed_in": False}
        meta = session["user"].get("user_metadata", {})
        return {"signed_in": True, "name": (self.profile or {}).get("name") or meta.get("preferred_username") or meta.get("full_name") or "Piloto Discord",
                "name_chosen": (self.profile or {}).get("name_chosen", False)}

    def account(self, name=None):
        with self.lock:
            profile = request_json(SITE + "/api/account", None if name is None else {"name": name},
                                   {"Authorization": "Bearer " + self.access_token()})
            if type(profile.get("name_chosen")) is not bool or (profile["name_chosen"] and not isinstance(profile.get("name"), str)):
                raise ValueError("No se pudo comprobar el nombre de piloto.")
            self.profile = profile
            return profile

    def logout(self):
        with self.lock:
            self.session = None
            self.pending = None
            self.profile = None
            self.path.unlink(missing_ok=True)

    def publish(self, payload):
        return request_json(SITE + "/api/publish", payload, {"Authorization": "Bearer " + self.access_token()})

    def revalidate(self, run_id):
        return request_json(SITE + "/api/revalidate", {"id": run_id}, {"Authorization": "Bearer " + self.access_token()})

