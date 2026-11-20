"""Captura local de ACR, solo lectura; nunca publica resultados."""
import argparse
import base64
import ctypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import struct
import time

VERSION = "0.2.0"


def clock_ms(text):
    match = re.fullmatch(r"(\d+):([0-5]\d)\.(\d{3})", text)
    if match is None:
        return None
    minutes, seconds, millis = map(int, match.groups())
    return (minutes * 60 + seconds) * 1000 + millis


def u16(block, offset, count):
    return block[offset:offset + count * 2].decode("utf-16le", "replace").split("\0")[0]


class SharedMemory:
    def __init__(self):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        self.api.OpenFileMappingW.restype = ctypes.c_void_p
        self.api.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.c_uint32, ctypes.c_size_t]
        self.api.MapViewOfFile.restype = ctypes.c_void_p
        self.api.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        self.api.UnmapViewOfFile.restype = ctypes.c_int
        self.api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.api.CloseHandle.restype = ctypes.c_int

    def read(self, name):
        handle = self.api.OpenFileMappingW(4, False, name)
        if not handle:
            return None
        try:
            view = self.api.MapViewOfFile(handle, 4, 0, 0, 4096)
            if not view:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                return ctypes.string_at(view, 4096)
            finally:
                self.api.UnmapViewOfFile(view)
        finally:
            self.api.CloseHandle(handle)

    def sample(self):
        graphics = self.read("acpmf_graphics")
        physics = self.read("acpmf_physics")
        static = self.read("acpmf_static")
        if graphics is None or physics is None or static is None:
            return None
        sample = {
            "packet": struct.unpack_from("<i", graphics, 0)[0],
            "clock_ms": clock_ms(u16(graphics, 12, 15)),
            "distance_m": struct.unpack_from("<f", graphics, 156)[0],
            "xyz_m": list(struct.unpack_from("<3f", graphics, 256)),
            "speed_kmh": struct.unpack_from("<f", physics, 28)[0],
            "car": u16(static, 68, 33),
            "track_label": u16(static, 134, 33),
            "player": u16(static, 200, 33),
            "graphics_base64": base64.b64encode(graphics).decode("ascii"),
        }
        if not all(math.isfinite(x) for x in
                   [sample["distance_m"], sample["speed_kmh"], *sample["xyz_m"]]):
            return None
        return sample


class Recorder:
    """El reloj congelado genera un candidato, nunca certifica un resultado."""
    def __init__(self, output, stage):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.stage = stage
        self.active = None
        self.trace = None
        self.previous = None
        self.previous_at = None
        self.changed_at = None
        self.candidate = False
        self.checkpoint_at = None

    def checkpoint(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.active, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def write(self, row):
        self.trace.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        self.trace.flush()

    def feed(self, sample, now):
        if sample is None or sample["clock_ms"] is None:
            self.close("telemetry_unavailable")
            self.previous = None
            self.previous_at = None
            return
        previous = self.previous
        clock = sample["clock_ms"]
        identity = tuple(sample[k] for k in ("car", "track_label", "player"))
        if self.active and identity != self.active["identity"]:
            self.close("context_changed")
            previous = None
        if self.active and previous and clock < previous["clock_ms"]:
            self.close("clock_reset")
            previous = None
        if self.active is None and clock > 0 and (previous is None or clock > previous["clock_ms"]):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            self.path = self.output / (stamp + "-" + os.urandom(4).hex() + ".json")
            self.trace = self.path.with_suffix(".jsonl").open("x", encoding="utf-8")
            self.active = {
                "schema_version": 1, "client_version": VERSION,
                "stage_id": self.stage, "stage_source": "manual_unverified",
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "identity": identity,
                "start_observed": bool(previous and previous["clock_ms"] == 0
                                       and clock <= 1000 and now - self.previous_at <= 1),
                "raw_time_ms": clock, "official_time_ms": None, "penalty_ms": None,
                "publication_eligible": False, "trace_file": self.path.with_suffix(".jsonl").name,
                "sample_count": 0,
                "capture_status": "recording",
            }
            self.changed_at = now
            self.candidate = False
            self.checkpoint_at = now
            self.checkpoint()
            print("Intento:", self.path.name, flush=True)
        if self.active:
            if previous and clock > previous["clock_ms"]:
                if self.candidate:
                    self.write({"event": "clock_resumed", "elapsed_s": now - self.started_at})
                self.changed_at = now
                self.candidate = False
            if self.active["sample_count"] == 0:
                self.started_at = now
            self.write({"elapsed_s": round(now - self.started_at, 3), **sample})
            self.active["sample_count"] += 1
            self.active["raw_time_ms"] = clock
            if not self.candidate and now - self.changed_at >= 3:
                self.candidate = True
                self.write({"event": "clock_frozen_candidate", "elapsed_s": now - self.started_at})
                print("Reloj detenido: posible pausa o meta; resultado sin verificar.", flush=True)
            if self.active["sample_count"] == 1 or now - self.checkpoint_at >= 1:
                self.active["clock_frozen_at_close"] = self.candidate
                self.checkpoint()
                self.checkpoint_at = now
        self.previous = sample
        self.previous_at = now

    def close(self, reason):
        if self.active is None:
            return
        self.active.update(closed_reason=reason, clock_frozen_at_close=self.candidate,
                           ended_utc=datetime.now(timezone.utc).isoformat(), capture_status="closed")
        self.trace.close()
        self.checkpoint()
        print("Guardado:", self.path.name, "|", reason, flush=True)
        self.active = None
        self.trace = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, help="Tramo elegido manualmente, p. ej. ke_ss2")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "captures")
    parser.add_argument("--seconds", type=float, default=1800)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds debe ser un número positivo y finito")
    if os.name != "nt":
        parser.error("La captura requiere Windows")
    memory = SharedMemory()
    recorder = Recorder(args.output, args.stage)
    stop_file = args.output / "STOP"
    stop_file.unlink(missing_ok=True)
    print("Solo lectura, 5 Hz. Sin envío online. Ctrl+C para guardar y terminar.", flush=True)
    print("Cierre controlado: ejecutar records/DETENER_CAPTURA.cmd (carpeta de salida predeterminada).", flush=True)
    print("Esperando telemetría; carga el tramo antes de empezar a conducir.", flush=True)
    deadline = time.monotonic() + args.seconds
    reason = "duration_limit"
    try:
        while time.monotonic() < deadline:
            if stop_file.exists():
                stop_file.unlink()
                reason = "stop_requested"
                break
            recorder.feed(memory.sample(), time.monotonic())
            time.sleep(0.2)
    except KeyboardInterrupt:
        reason = "user_stopped"
    except Exception:
        reason = "capture_error"
        raise
    finally:
        recorder.close(reason)


if __name__ == "__main__":
    main()
