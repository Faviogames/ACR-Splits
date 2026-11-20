"""Inspecciona una COPIA del guardado GVAS; no modifica el juego ni adjudica records."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct

# Layout contrastado con client/acr_daily/rallyweekend.py de khanhonthetrack/acr-daily.
# shortcut: este formato no tiene version de resultados; validar otra vez tras parches de ACR.


class InvalidSave(ValueError):
    pass


class Cursor:
    def __init__(self, data, offset=0):
        self.data, self.offset = data, offset

    def unpack(self, fmt):
        size = struct.calcsize(fmt)
        if self.offset < 0 or self.offset + size > len(self.data):
            raise InvalidSave("Guardado truncado")
        value = struct.unpack_from(fmt, self.data, self.offset)
        self.offset += size
        return value

    def integer(self):
        return self.unpack("<i")[0]

    def string(self):
        size = self.integer()
        if not 1 <= size <= 300 or self.offset + size > len(self.data):
            raise InvalidSave("Longitud de FString no valida")
        raw = self.data[self.offset:self.offset + size]
        self.offset += size
        if raw[-1] != 0 or any(x < 32 or x > 126 for x in raw[:-1]):
            raise InvalidSave("FString ASCII no valida")
        return raw[:-1].decode("ascii")

    def count(self, maximum):
        value = self.integer()
        if not 1 <= value <= maximum:
            raise InvalidSave("Cantidad de elementos no valida")
        return value


def seconds_ms(seconds):
    if not math.isfinite(seconds) or not 0 <= seconds < 100000:
        raise InvalidSave("Tiempo o penalizacion no validos")
    return round(seconds * 1000)


def result_list(data, offset, mode):
    cursor = Cursor(data, offset)
    entries = []
    for _ in range(cursor.count(10000)):
        stage = cursor.string()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,95}", stage):
            raise InvalidSave("ID de tramo no valido")
        runs = []
        for _ in range(cursor.count(1000)):
            index = cursor.integer()
            car = cursor.string()
            if not car:
                raise InvalidSave("Coche vacio")
            splits = []
            for _ in range(cursor.count(200)):
                split, elapsed, section = cursor.unpack("<iff")
                splits.append({"index": split, "time_ms": seconds_ms(elapsed),
                               "section_ms": seconds_ms(section)})
            penalty_seconds = cursor.unpack("<f")[0]
            penalty_ms = seconds_ms(penalty_seconds)
            cursor.unpack("<8s")
            runs.append({"index": index, "car": car, "raw_time_ms": splits[-1]["time_ms"],
                         "penalty_ms": penalty_ms,
                         "official_time_ms": round((elapsed + penalty_seconds) * 1000),
                         "splits": splits})
        unix_seconds = (cursor.unpack("<q")[0] - 621355968000000000) / 10000000
        if not 1600000000 < unix_seconds < 4200000000:
            raise InvalidSave("Fecha del resultado no valida")
        entries.append({"mode": mode, "stage_id": stage,
                        "started_utc": datetime.fromtimestamp(unix_seconds, timezone.utc).isoformat(),
                        "runs": runs})
    return entries


def inspect(data):
    marker = b"PlayerSaveGameData\0"
    at = data.find(marker)
    if data[:4] != b"GVAS" or at < 0 or data.find(marker, at + 1) >= 0:
        raise InvalidSave("No es el GVAS esperado de ACR")
    payload_size_at = at + len(marker)
    payload_size = Cursor(data, payload_size_at).integer()
    if payload_size < 0 or payload_size_at + 4 + payload_size != len(data):
        raise InvalidSave("El tamano de PlayerSaveGameData no coincide")
    found = {}
    modes = set()
    rejected = 0
    for match in re.finditer(rb"Default[A-Za-z]+\0", data[payload_size_at + 4:]):
        start = payload_size_at + 4 + match.start()
        if start < 4 or Cursor(data, start - 4).integer() != len(match.group()):
            continue
        mode = match.group()[:-1].decode("ascii")
        modes.add(mode)
        try:
            entries = result_list(data, start + len(match.group()), mode)
        except InvalidSave:
            rejected += 1
            continue
        if mode in found:
            raise InvalidSave("Varias listas posibles para " + mode + "; no se elige automaticamente")
        found[mode] = entries
    return {"schema_version": 1, "source_sha256": hashlib.sha256(data).hexdigest(),
            "mode_names": sorted(modes), "rejected_or_nonresult_blocks": rejected,
            "results": [entry for entries in found.values() for entry in entries],
            "publication_eligible": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", required=True, type=Path, help="Copia local .sav, preferiblemente con ACR cerrado")
    args = parser.parse_args()
    try:
        report = inspect(args.save.read_bytes())
    except (OSError, InvalidSave) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
