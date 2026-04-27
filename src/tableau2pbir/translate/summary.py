"""Stage 3 summary.md renderer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationStats:
    total: int
    by_source: dict[str, int]               # "rule" | "ai" | "skip"
    rule_hits: dict[str, int]               # rule name → count
    ai_confidence: dict[str, int]           # "high" | "medium" | "low" → count
    ai_cache_hits: int
    ai_cache_misses: int
    validator_failed: int


def _fmt_hist(items: dict[str, int]) -> list[str]:
    if not items:
        return ["- (none)"]
    return [f"- {k}: {items[k]}" for k in sorted(items)]


def render_stage3_summary(stats: TranslationStats) -> str:
    cache_total = stats.ai_cache_hits + stats.ai_cache_misses
    if cache_total == 0:
        cache_rate = "n/a"
    else:
        cache_rate = f"{round(100 * stats.ai_cache_hits / cache_total)}%"

    lines = [
        "# Stage 3 — translate calcs",
        "",
        f"- total calculations: {stats.total}",
        f"- validator-failed: {stats.validator_failed}",
        f"- cache hit rate: {cache_rate}",
        "",
        "## Translation source",
        "",
        *_fmt_hist(stats.by_source),
        "",
        "## Rule hit histogram",
        "",
        *_fmt_hist(stats.rule_hits),
        "",
        "## AI confidence histogram",
        "",
        *_fmt_hist(stats.ai_confidence),
        "",
    ]
    return "\n".join(lines) + "\n"
