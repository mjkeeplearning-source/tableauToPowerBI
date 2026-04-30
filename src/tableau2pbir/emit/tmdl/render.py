"""Stage 6 orchestrator. §6 Stage 6."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.emit._io import write_text
from tableau2pbir.emit.tmdl.database import render_database
from tableau2pbir.emit.tmdl.model import render_model
from tableau2pbir.emit.tmdl.parameters import render_parameter
from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.emit.tmdl.table import render_table
from tableau2pbir.ir.calculation import CalculationScope
from tableau2pbir.ir.workbook import Workbook


def render_semantic_model(wb: Workbook, out_dir: Path) -> dict:
    sm = out_dir / "SemanticModel"
    files: list[str] = []

    db_name = Path(wb.source_path).stem or "Workbook"
    write_text(sm / "database.tmdl", render_database(name=db_name))
    files.append("database.tmdl")
    write_text(sm / "model.tmdl", render_model())
    files.append("model.tmdl")

    # DataModel has no columns field in v1 — Column objects were discarded in
    # Stage 2. Tables are rendered without column fragments until that gap is filled.
    primary_table_id = wb.data_model.tables[0].id if wb.data_model.tables else None
    measures_for_table: dict[str, list] = {t.id: [] for t in wb.data_model.tables}
    for calc in wb.data_model.calculations:
        if calc.scope == CalculationScope.MEASURE and calc.dax_expr and primary_table_id:
            measures_for_table[primary_table_id].append(calc)

    table_count = 0
    measure_count = 0
    for t in wb.data_model.tables:
        ds = next((d for d in wb.data_model.datasources if d.id == t.datasource_id), None)
        if ds is None:
            continue
        body = render_table(
            name=t.name, columns=[],
            measures=measures_for_table.get(t.id, []), datasource=ds,
        )
        rel = f"tables/{t.name}.tmdl"
        write_text(sm / rel, body)
        files.append(rel)
        table_count += 1
        measure_count += len(measures_for_table.get(t.id, []))

    rel_count = 0
    for r in wb.data_model.relationships:
        from_t = next((t.name for t in wb.data_model.tables if t.id == r.from_ref.table_id), r.from_ref.table_id)
        to_t = next((t.name for t in wb.data_model.tables if t.id == r.to_ref.table_id), r.to_ref.table_id)
        body = render_relationship(r, from_t, to_t)
        rel = f"relationships/{r.id}.tmdl"
        write_text(sm / rel, body)
        files.append(rel)
        rel_count += 1

    param_count = 0
    constants_path = sm / "tables/_Constants.tmdl"
    for p in wb.data_model.parameters:
        for fname, body in render_parameter(p).items():
            dest = sm / fname
            if fname == "tables/_Constants.tmdl" and constants_path.is_file():
                body = constants_path.read_text(encoding="utf-8") + "\n" + body
            write_text(dest, body)
            if fname not in files:
                files.append(fname)
            param_count += 1

    return {
        "files": files,
        "counts": {
            "tables": table_count, "measures": measure_count,
            "relationships": rel_count, "parameters": param_count,
        },
    }
