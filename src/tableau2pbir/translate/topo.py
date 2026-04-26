"""Topological ordering for stage-3 calc translation. Two lanes per spec
§6 Stage 3 + §5.6: 'global' contains row/aggregate/lod_fixed and named
table_calc; 'per-sheet' contains lod_include/lod_exclude and any calc
with `owner_sheet_id` set (anonymous quick-table-calcs).

Cycle handling lives in `_calc_graph.detect_cycles` (Plan 2). This module
assumes the input is acyclic for the lanes that matter; cycle members
are pre-routed to unsupported[] before reaching here."""
from __future__ import annotations

from collections import defaultdict, deque

from tableau2pbir.ir.calculation import Calculation, CalculationKind

_GLOBAL_KINDS = frozenset({
    CalculationKind.ROW,
    CalculationKind.AGGREGATE,
    CalculationKind.LOD_FIXED,
})


def _is_global(c: Calculation) -> bool:
    if c.owner_sheet_id is not None:
        return False
    if c.kind in _GLOBAL_KINDS:
        return True
    if c.kind is CalculationKind.TABLE_CALC:
        # Named table_calc (no owner_sheet_id) lives in the global lane.
        return True
    # lod_include / lod_exclude — always per-sheet.
    return False


def partition_lanes(
    calcs: tuple[Calculation, ...],
) -> tuple[tuple[Calculation, ...], tuple[Calculation, ...]]:
    """Split into (global_lane, per_sheet_lane)."""
    g: list[Calculation] = []
    p: list[Calculation] = []
    for c in calcs:
        (g if _is_global(c) else p).append(c)
    return tuple(g), tuple(p)


def topo_sort(calcs: tuple[Calculation, ...]) -> tuple[Calculation, ...]:
    """Kahn's algorithm; ties broken by sorted(id) for stable output.
    Edges to ids not in `calcs` are ignored."""
    by_id = {c.id: c for c in calcs}
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for c in calcs:
        for dep in c.depends_on:
            if dep in by_id:
                incoming[c.id].add(dep)
                outgoing[dep].add(c.id)

    ready = sorted(cid for cid in by_id if not incoming[cid])
    result: list[Calculation] = []
    queue: deque[str] = deque(ready)
    while queue:
        n = queue.popleft()
        result.append(by_id[n])
        for m in sorted(outgoing[n]):
            outgoing[n].discard(m)
            incoming[m].discard(n)
            if not incoming[m]:
                # Insert in sorted position to keep id-tiebreak determinism.
                queue.append(m)
                items = sorted(queue)
                queue.clear()
                queue.extend(items)
    return tuple(result)
