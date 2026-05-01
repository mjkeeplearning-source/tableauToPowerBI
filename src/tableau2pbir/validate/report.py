"""Markdown reporters for Stage 8. See spec §4.4 + §6 Stage 8."""
from __future__ import annotations


def render_workbook_report(*, workbook_id: str, status: str, triggers: list[str],
                           validators: dict, datasources: list[dict],
                           placeholders_per_page: dict[str, int]) -> str:
    lines: list[str] = []
    lines.append(f"# Workbook conversion report — {workbook_id}")
    lines.append("")
    lines.append(f"**Status:** {status}")
    if triggers:
        lines.append("")
        lines.append("**Triggers:**")
        for t in triggers:
            lines.append(f"- {t}")
    lines.append("")
    lines.append("## Validators")
    for name, info in validators.items():
        suffix = ""
        if info.get("reason"):
            suffix = f" ({info['reason']})"
        lines.append(f"- {name}: {info.get('outcome', 'unknown')}{suffix}")
    lines.append("")
    lines.append("## Datasources")
    if not datasources:
        lines.append("- (none)")
    else:
        for ds in datasources:
            ua = ", ".join(ds.get("user_action_required") or []) or "none"
            lines.append(f"- **{ds.get('name', '?')}** (tier {ds.get('tier', '?')}) — actions: {ua}")
    lines.append("")
    lines.append("## Placeholders per page")
    for page, count in placeholders_per_page.items():
        lines.append(f"- {page}: {count}")
    lines.append("")
    return "\n".join(lines)


def render_summary_md(*, validators: dict, artifact_size_bytes: int, status: str) -> str:
    lines: list[str] = ["# Stage 8 — package + validate", ""]
    lines.append(f"Final status: **{status}**")
    lines.append("")
    lines.append("Validator outcomes:")
    for name, info in validators.items():
        reason = f" ({info['reason']})" if info.get("reason") else ""
        lines.append(f"- {name}: {info.get('outcome', 'unknown')}{reason}")
    lines.append("")
    lines.append(f"Total artifact size: {artifact_size_bytes} bytes")
    lines.append("")
    return "\n".join(lines)


def render_run_manifest_row(workbook_id: str, status: str,
                            triggers: list[str], link: str) -> str:
    return f"| {workbook_id} | {status} | {','.join(triggers) or '—'} | {link} |"
