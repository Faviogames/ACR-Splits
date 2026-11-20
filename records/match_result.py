"""Asocia una captura con un resultado nuevo entre dos informes del guardado. Sin envios."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


def run_key(entry, run):
    return (entry["mode"], entry["stage_id"].casefold(),
            datetime.fromisoformat(entry["started_utc"]).isoformat(),
            run["index"], run["car"].casefold())


def match(before, after, attempt):
    if attempt.get("capture_status") == "recording":
        raise ValueError("La captura sigue abierta; cerrarla antes de asociar resultados")
    if before["source_sha256"] == after["source_sha256"]:
        raise ValueError("El guardado no ha cambiado")
    known = {run_key(entry, run) for entry in before["results"] for run in entry["runs"]}
    car = re.sub(r"[^a-z0-9]", "", attempt["identity"][0].casefold())
    candidates = []
    for entry in after["results"]:
        for run in entry["runs"]:
            if run_key(entry, run) in known:
                continue
            if re.sub(r"[^a-z0-9]", "", run["car"].casefold()) != car:
                continue
            if run["raw_time_ms"] != attempt["raw_time_ms"]:
                continue
            expected_stage = attempt.get("stage_game_id")
            if expected_stage and expected_stage.casefold() != entry["stage_id"].casefold():
                continue
            candidates.append((entry, run))
    if len(candidates) != 1:
        raise ValueError("Se necesita una coincidencia nueva y unica; encontradas: " + str(len(candidates)))
    entry, run = candidates[0]
    key_json = json.dumps(run_key(entry, run), ensure_ascii=True, separators=(",", ":"))
    result_id = hashlib.sha256(key_json.encode("ascii")).hexdigest()
    if attempt.get("save_evidence", {}).get("result_id") == result_id:
        raise ValueError("Este resultado ya esta asociado")
    result = dict(attempt)
    result.update(stage_game_id=entry["stage_id"], stage_source="new_save_result_match",
                  official_time_ms=run["official_time_ms"], penalty_ms=run["penalty_ms"],
                  publication_eligible=False,
                  save_evidence={"result_id": result_id, "source_sha256": after["source_sha256"],
                                 "baseline_sha256": before["source_sha256"], "mode": entry["mode"],
                                 "stage_game_id": entry["stage_id"], "car_game_id": run["car"],
                                 "result_started_utc": entry["started_utc"], "run_index": run["index"],
                                 "match": "unique_new_result_by_car_raw_time_and_optional_stage"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path, help="Informe JSON anterior a conducir")
    parser.add_argument("--after", required=True, type=Path, help="Informe JSON posterior a conducir")
    parser.add_argument("--capture", required=True, type=Path, help="Resumen JSON de la captura cerrada")
    parser.add_argument("--output", required=True, type=Path, help="Archivo nuevo para el resumen enriquecido")
    args = parser.parse_args()
    try:
        read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
        result = match(read(args.before), read(args.after), read(args.capture))
        with args.output.open("x", encoding="utf-8") as target:
            target.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")
    print("Asociado:", result["stage_game_id"], "| bruto", result["raw_time_ms"],
          "| penalizacion", result["penalty_ms"], "| total", result["official_time_ms"], "ms")


if __name__ == "__main__":
    main()
