"""Write the .pbip root pointer file. See spec §4.4 + §6 Stage 8 step 1."""
from __future__ import annotations

import json
from pathlib import Path

_PBIP_PAYLOAD = {
    "version": "1.0",
    "artifacts": [
        {"report": {"path": "Report"}},
        {"dataset": {"path": "SemanticModel"}},
    ],
    "settings": {"enableAutoRecovery": True},
}

_DEFINITION_PBIR_PAYLOAD = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
    "version": "4.0",
    "datasetReference": {
        "byPath": {"path": "../SemanticModel"},
        "byConnection": None,
    },
}


def write_pbip_root(out_dir: Path, workbook_id: str) -> Path:
    """Write `<workbook_id>.pbip` and `Report/definition.pbir` under `out_dir`.

    `Report/definition.pbir` is the binding file PBI Desktop uses to locate the
    SemanticModel. Without it the project cannot be opened in Desktop even though
    all other artifacts are present.

    Raises FileNotFoundError if Report/ is absent.
    Overwrites any existing files (including the Plan-1 0-byte stub).
    """
    if not (out_dir / "Report").is_dir():
        raise FileNotFoundError(f"missing Report/ under {out_dir!s}; cannot write .pbip")

    target = out_dir / f"{workbook_id}.pbip"
    target.write_text(json.dumps(_PBIP_PAYLOAD, indent=2), encoding="utf-8")

    definition_pbir = out_dir / "Report" / "definition.pbir"
    definition_pbir.write_text(
        json.dumps(_DEFINITION_PBIR_PAYLOAD, indent=2), encoding="utf-8"
    )

    return target
