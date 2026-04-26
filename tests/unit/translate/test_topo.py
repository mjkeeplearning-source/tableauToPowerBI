"""Stage 3 topological order — global lane (row, aggregate, lod_fixed,
named table_calc) and per-sheet lane (lod_include, lod_exclude, anonymous
quick-table-calc). Per spec §5.6 / §6 Stage 3."""
from __future__ import annotations

from tableau2pbir.ir.calculation import (
    Calculation, CalculationKind, CalculationPhase, LodFixed,
)
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.translate.topo import partition_lanes, topo_sort


def _calc(
    cid: str, kind: CalculationKind, depends: tuple[str, ...] = (),
    *, owner_sheet_id: str | None = None,
) -> Calculation:
    return Calculation(
        id=cid, name=cid, scope="measure", tableau_expr="0",
        depends_on=depends, kind=kind, phase=CalculationPhase.AGGREGATE,
        lod_fixed=LodFixed(dimensions=(FieldRef(table_id="t", column_id="c"),))
            if kind is CalculationKind.LOD_FIXED else None,
        owner_sheet_id=owner_sheet_id,
    )


def test_partition_lanes_separates_global_from_per_sheet():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.AGGREGATE)
    c = _calc("c", CalculationKind.LOD_INCLUDE, owner_sheet_id="sheet1")
    d = _calc("d", CalculationKind.TABLE_CALC, owner_sheet_id="sheet2")
    global_lane, per_sheet_lane = partition_lanes((a, b, c, d))
    assert {x.id for x in global_lane} == {"a", "b"}
    assert {x.id for x in per_sheet_lane} == {"c", "d"}


def test_topo_sort_respects_depends_on():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.AGGREGATE, depends=("a",))
    c = _calc("c", CalculationKind.AGGREGATE, depends=("b",))
    ordered = topo_sort((c, a, b))
    ids = [x.id for x in ordered]
    assert ids.index("a") < ids.index("b") < ids.index("c")


def test_topo_sort_skips_unknown_depends():
    """Refs to ids not in the input set are ignored (e.g. dangling refs to
    calcs already routed to unsupported[])."""
    a = _calc("a", CalculationKind.ROW, depends=("missing",))
    ordered = topo_sort((a,))
    assert [x.id for x in ordered] == ["a"]


def test_topo_sort_breaks_ties_by_id_for_determinism():
    a = _calc("a", CalculationKind.ROW)
    b = _calc("b", CalculationKind.ROW)
    c = _calc("c", CalculationKind.ROW)
    ordered = topo_sort((c, a, b))
    assert [x.id for x in ordered] == ["a", "b", "c"]
