"""JSON Schema autogeneration from IR pydantic models.

This module is also a CLI entry-point. Run `python -m tableau2pbir.ir.schema`
to emit the schema JSON to stdout (wired via `make schema`)."""
from __future__ import annotations

import json
import sys
from typing import Any

from tableau2pbir.ir.workbook import Workbook


def generate_ir_schema() -> dict[str, Any]:
    """Return the JSON Schema for the top-level Workbook IR model."""
    return Workbook.model_json_schema()


def main() -> None:
    json.dump(generate_ir_schema(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
