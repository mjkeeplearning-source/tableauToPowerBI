"""Stage 2 summary.md renderer. Stable ordering so golden tests don't flap."""
from __future__ import annotations

from collections import Counter

from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.common import UnsupportedItem
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.parameter import Parameter


def _histogram(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"## {title}")
    lines.append("")
    if not counter:
        lines.append("- (none)")
    else:
        for key in sorted(counter):
            lines.append(f"- {key}: {counter[key]}")
    lines.append("")


def render_stage2_summary(
    *,
    datasources: tuple[Datasource, ...],
    calculations: tuple[Calculation, ...],
    parameters: tuple[Parameter, ...],
    sheets_count: int,
    dashboards_count: int,
    unsupported: tuple[UnsupportedItem, ...],
) -> str:
    lines: list[str] = ["# Stage 2 — canonicalize → IR", ""]

    lines.append("## IR object counts")
    lines.append("")
    lines.append(f"- datasources: {len(datasources)}")
    lines.append(f"- calculations: {len(calculations)}")
    lines.append(f"- parameters: {len(parameters)}")
    lines.append(f"- sheets: {sheets_count}")
    lines.append(f"- dashboards: {dashboards_count}")
    lines.append(f"- unsupported entries: {len(unsupported)}")
    lines.append("")

    tier_counter: Counter[str] = Counter(f"Tier {ds.connector_tier.value}" for ds in datasources)
    _histogram(lines, "Datasource tier histogram", tier_counter)

    kind_counter: Counter[str] = Counter(c.kind.value for c in calculations)
    _histogram(lines, "Calc kind histogram", kind_counter)

    intent_counter: Counter[str] = Counter(p.intent.value for p in parameters)
    _histogram(lines, "Parameter intent histogram", intent_counter)

    code_counter: Counter[str] = Counter(item.code for item in unsupported)
    _histogram(lines, "Unsupported breakdown (by code)", code_counter)

    return "\n".join(lines) + "\n"
