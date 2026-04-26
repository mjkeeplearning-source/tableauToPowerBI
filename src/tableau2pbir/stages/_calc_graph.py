"""Calc dependency graph utilities. Kahn-style topo-walk to isolate cycle
members; everything not removed is a cycle member."""
from __future__ import annotations

from collections import defaultdict, deque

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import UnsupportedItem


def detect_cycles(calcs: tuple[Calculation, ...]) -> tuple[UnsupportedItem, ...]:
    """Return an UnsupportedItem for every calc that participates in a cycle."""
    ids = {c.id for c in calcs}
    # Edges restricted to known ids — ignore dangling refs to external calcs.
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    for c in calcs:
        for dep in c.depends_on:
            if dep in ids:
                incoming[c.id].add(dep)
                outgoing[dep].add(c.id)

    queue: deque[str] = deque(cid for cid in ids if not incoming[cid])
    resolved: set[str] = set()
    while queue:
        n = queue.popleft()
        resolved.add(n)
        for m in list(outgoing[n]):
            outgoing[n].discard(m)
            incoming[m].discard(n)
            if not incoming[m]:
                queue.append(m)

    cycle_members = ids - resolved
    out: list[UnsupportedItem] = []
    calc_by_id = {c.id: c for c in calcs}
    for cid in sorted(cycle_members):
        calc = calc_by_id[cid]
        out.append(UnsupportedItem(
            object_kind="calc",
            object_id=cid,
            source_excerpt=calc.tableau_expr[:200],
            reason=f"Calculation {calc.name!r} participates in a dependency cycle.",
            code="calc_cycle",
        ))
    return tuple(out)
