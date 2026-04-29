# Plan 4 — Stage 5 (compute layout) + Stage 6 (build TMDL) + Stage 7 (build report PBIR)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Plan-1 no-op stubs for stages 5, 6, and 7 with v1-scope implementations. End state: `tableau2pbir convert tests/golden/synthetic/<v1-fixture>.twb --out ./out/<wb>/` produces:
- `stages/05_layout.json` — IR with every `Leaf.position` populated (or clamped/dropped, with warnings logged to `unsupported.json`).
- `SemanticModel/` — TMDL files (`database.tmdl`, `model.tmdl`, `tables/<name>.tmdl`, `relationships/<id>.tmdl`) + `stages/06_tmdl.json` manifest.
- `Report/definition/` — PBIR JSON tree (`report.json`, `pages/<page>/page.json`, `pages/<page>/visuals/<vid>/visual.json`) + `stages/07_pbir.json` manifest including `blocked_visuals[]`.
- Full pytest suite stays green. Stage 8 still runs as a no-op stub.

**Architecture:** Three pure-Python stages, no AI. Stage 5 is a deterministic container-tree walker that resolves every dashboard `Leaf.position` to absolute pixel `(x,y,w,h)` rectangles at the chosen canvas size; off-canvas leaves are clamped (warning) or dropped (warning). Stage 6 walks the IR `data_model` and renders TMDL text files to disk: tables, columns, measures (one per `Calculation` whose `dax_expr` is non-null and whose `scope == 'measure'`), calculated columns (one per `Calculation` whose `scope == 'column'`), relationships, and one M-partition per Tier-1/Tier-2 datasource (credentials stripped per §5.8). Parameters are emitted per `Parameter.intent` (numeric_what_if → `GENERATESERIES` table + `SelectedValue` measure; categorical_selector → disconnected-rows table + `SelectedValue` measure; internal_constant → hidden literal measure). Stage 7 walks the IR `dashboards` + `sheets` and emits PBIR JSON: one `page/` per dashboard, one `visual/` per `Sheet`-bearing leaf using the `Sheet.pbir_visual` annotation from Stage 4 + position from Stage 5; filter cards become slicers, parameter cards become slicers bound to the §5.7-emitted tables; workbook-level filters that apply to every page promote to a report filter, others stay page-scoped; actions emit as `visualInteractions` entries; visuals backed by `deferred_feature_*` or `connector_tier == 4` datasources are still rendered (placeholder + warning) and recorded in `blocked_visuals[]` for §8.1 to consume. Stage 6 and Stage 7 are filesystem-emitting (writing under `ctx.output_dir`) but their `StageResult.output` is a structured JSON manifest, not the IR — Stage 8 reads the manifests, not re-derives them.

**v1 simplifications honored from Plan 3 + spec §16:**
- Calcs: only `row` / `aggregate` / `lod_fixed` have `dax_expr` set; deferred kinds are already in `unsupported[]` with `code` starting `deferred_feature_`. Stage 6 emits a measure for a `Calculation` only when `dax_expr is not None`. LOD INCLUDE/EXCLUDE and per-sheet measure expansion stay unwired — the (calc, sheet) lane in Stage 6 is implemented but empty in v1.
- Parameter intents emitted: `numeric_what_if`, `categorical_selector`, `internal_constant`. `formatting_control` and `unsupported` intents emit nothing — the latter is already in `unsupported[]` from Plan 2.
- Connectors: Tier 1 + Tier 2 emit M; Tier 3 is already deferred via `unsupported[]`; Tier 4 datasources still get a placeholder M file (a one-step `error` partition with the `user_action_required` text) so Stage 7's `blocked_visuals[]` mechanism has something to point at. §8.1 will then force `failed`.
- Visual catalog: bar, line, area (clusteredColumnChart / lineChart / areaChart / scatterChart / tableEx / pieChart / filledMapVisual) — same set Stage 4 already emits in `Sheet.pbir_visual.visual_type`.
- Layout: tiled + floating, both fully resolved (§16 v1 in-scope).
- Mobile layout / Device Designer: deferred.

**Out of scope for Plan 4 (deferred to Plan 5 or v1.1+):**
- Stage 8 (package + validate + Desktop-open gate + acceptance rubric) — stays a no-op stub.
- §9 layer iv-c DAX semantic probes runner — Plan 5.
- TabularEditor 2 / pbi-tools / Desktop-open process launching — Plan 5.
- `LLMClient.cleanup_name` — still raises `NotImplementedError` (no live caller in Plan 4 either; raw IR names are written verbatim to TMDL/PBIR. §6 stage 6 mentions name cleanup as nice-to-have, not v1-required).
- Per-sheet LOD measure expansion (`<calc_name>__<sheet_safe_name>`) — execution path stays implemented-but-empty.
- `formatting_control` parameter switch tables — flag-gated to v1.1.
- Bookmarks emission for action-driven navigation — stays as `actions[]` data only; PBIR `bookmarks/` directory is NOT written in v1 (visual interactions handle filter/highlight actions).
- Report-page-tooltip layout — flag-gated.

**Tech stack:** Python 3.11+, pydantic v2 (existing IR — no schema bump in Plan 4; `Leaf.position` is already optional and gets populated), stdlib `json`, `pathlib`, `dataclasses`, `textwrap`, `re`. **No new runtime dependencies.** Test deps unchanged.

**Spec reference:** `C:\Tableau_PBI\docs\superpowers\specs\2026-04-23-tableau-to-pbir-design.md`. Primary sections: §4.4 (output structure), §5.1–§5.3 (IR layout tree + Action), §5.7 (Parameter emission per intent — Stage 6 + Stage 7), §5.8 (connector tier → M), §6 Stage 5/6/7 (algorithms), §8.1 (status rule — Stage 7 emits `blocked_visuals[]`), §14 (compatibility ledger — placeholder text rules), §16 (v1 scope), §A.4-3 (`blocked_visuals[]` contract).

**Plan-1/2/3 outputs Plan 4 builds on (do NOT re-create or restructure):**
- `src/tableau2pbir/ir/dashboard.py` — `Container` / `Leaf` / `Position` / `Dashboard` / `DashboardSize` / `Action` / `LeafKind`.
- `src/tableau2pbir/ir/sheet.py` — `Sheet` with `pbir_visual: PbirVisual | None` populated by Stage 4.
- `src/tableau2pbir/ir/parameter.py` — `Parameter.intent` populated by Stage 2.
- `src/tableau2pbir/ir/datasource.py` — `Datasource.connector_tier` (1–4), `pbi_m_connector`, `connection_params`, `user_action_required`.
- `src/tableau2pbir/ir/calculation.py` — `Calculation.dax_expr` populated by Stage 3 (None for deferred / unsupported / column-scope without expression).
- `src/tableau2pbir/ir/version.py` — `IR_SCHEMA_VERSION = "1.1.0"`. **Plan 4 does NOT bump it** (no IR field added or changed).
- `src/tableau2pbir/ir/workbook.py` — `Workbook` aggregate with `unsupported: tuple[UnsupportedItem, ...]`.
- `src/tableau2pbir/ir/common.py` — `IRBase`, `FieldRef`, `UnsupportedItem`.
- `src/tableau2pbir/pipeline.py` — `StageContext`, `StageResult`, `StageError`, runner.
- `src/tableau2pbir/stages/s05_compute_layout.py`, `s06_build_tmdl.py`, `s07_build_pbir.py` — Plan-1 no-op stubs to be replaced.
- `tests/golden/synthetic/dashboard_tiled_floating.twb` — already authored; Plan 4 adds layout golden expectations.
- `tests/golden/synthetic/visual_marks_v1.twb` — already authored; Plan 4 adds TMDL + PBIR golden expectations.
- `tests/golden/synthetic/params_all_intents.twb` — already authored; Plan 4 adds parameter-emission golden expectations.

---

## File structure (Plan 4)

**Create (new files):**

```
C:\Tableau_PBI\
├── src/tableau2pbir/
│   ├── layout/
│   │   ├── __init__.py
│   │   ├── canvas.py                 # canvas-size selection + scaling
│   │   ├── walker.py                 # container-tree walker → absolute rects
│   │   ├── leaf_types.py             # Tableau leaf-kind → PBI object-type mapping table
│   │   └── summary.py                # stage 5 summary.md renderer
│   ├── emit/
│   │   ├── __init__.py
│   │   ├── _io.py                    # safe write_text helper (atomic, utf-8, LF)
│   │   ├── tmdl/
│   │   │   ├── __init__.py
│   │   │   ├── render.py             # entry: render_semantic_model(workbook, out_dir)
│   │   │   ├── database.py           # database.tmdl
│   │   │   ├── model.py              # model.tmdl
│   │   │   ├── table.py              # tables/<name>.tmdl
│   │   │   ├── column.py             # column / calculated-column TMDL fragment
│   │   │   ├── measure.py            # measure TMDL fragment
│   │   │   ├── relationship.py       # relationships/<id>.tmdl
│   │   │   ├── m_expression.py       # Datasource → M (Tier 1, Tier 2, Tier 4 placeholder)
│   │   │   ├── parameters.py         # what-if / selector / constant TMDL emission per §5.7
│   │   │   ├── escape.py             # TMDL identifier + string escaping
│   │   │   └── summary.py            # stage 6 summary.md renderer
│   │   └── pbir/
│   │       ├── __init__.py
│   │       ├── render.py             # entry: render_report(workbook, out_dir) → manifest
│   │       ├── report.py             # report.json (root)
│   │       ├── page.py               # pages/<page>/page.json
│   │       ├── visual.py             # visuals/<vid>/visual.json — dispatches on visual_type
│   │       ├── slicer.py             # filter-card slicer + parameter-card slicer
│   │       ├── filters.py            # workbook + page filter promotion
│   │       ├── actions.py            # action → visualInteractions entries
│   │       ├── blocked.py            # blocked_visuals[] computation
│   │       ├── ids.py                # stable PBIR id generator
│   │       └── summary.py            # stage 7 summary.md renderer
├── tests/
│   ├── unit/
│   │   ├── layout/
│   │   │   ├── __init__.py
│   │   │   ├── test_canvas.py
│   │   │   ├── test_walker.py
│   │   │   └── test_leaf_types.py
│   │   ├── emit/
│   │   │   ├── __init__.py
│   │   │   ├── tmdl/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_database.py
│   │   │   │   ├── test_model.py
│   │   │   │   ├── test_table.py
│   │   │   │   ├── test_column.py
│   │   │   │   ├── test_measure.py
│   │   │   │   ├── test_relationship.py
│   │   │   │   ├── test_m_expression.py
│   │   │   │   ├── test_parameters.py
│   │   │   │   └── test_escape.py
│   │   │   └── pbir/
│   │   │       ├── __init__.py
│   │   │       ├── test_report.py
│   │   │       ├── test_page.py
│   │   │       ├── test_visual.py
│   │   │       ├── test_slicer.py
│   │   │       ├── test_filters.py
│   │   │       ├── test_actions.py
│   │   │       └── test_blocked.py
│   │   └── stages/
│   │       ├── test_s05_compute_layout.py
│   │       ├── test_s06_build_tmdl.py
│   │       └── test_s07_build_pbir.py
│   ├── contract/
│   │   ├── test_stage5_layout_contract.py
│   │   ├── test_stage6_tmdl_contract.py
│   │   └── test_stage7_pbir_contract.py
│   └── integration/
│       └── test_stage5_6_7_integration.py
```

**Modify:**

- `src/tableau2pbir/stages/s05_compute_layout.py` — replace stub with real `run()`.
- `src/tableau2pbir/stages/s06_build_tmdl.py` — replace stub with real `run()`.
- `src/tableau2pbir/stages/s07_build_pbir.py` — replace stub with real `run()`.

**Untouched in Plan 4:**

- All Plan-1/2/3 files. No IR schema changes. No prompt changes. No new runtime dependencies.

---

## Stage 5 — compute layout (Tasks 1–6)

### Task 1: Canvas size selection

**Files:**
- Create: `src/tableau2pbir/layout/canvas.py`
- Test: `tests/unit/layout/test_canvas.py`

- [x] **Step 1: Write the failing test**

```python
# tests/unit/layout/test_canvas.py
from tableau2pbir.ir.dashboard import DashboardSize
from tableau2pbir.layout.canvas import select_canvas

def test_exact_size_matches_standard_16x9():
    size = DashboardSize(w=1280, h=720, kind="exact")
    canvas = select_canvas(size, config={})
    assert canvas == (1280, 720, 1.0)

def test_automatic_falls_back_to_default_landscape():
    size = DashboardSize(w=0, h=0, kind="automatic")
    canvas = select_canvas(size, config={})
    assert canvas == (1280, 720, 1.0)

def test_range_resolved_to_midpoint():
    size = DashboardSize(w=1000, h=600, kind="range")
    canvas = select_canvas(size, config={})
    assert canvas == (1000, 600, 1.0)

def test_user_override_via_config():
    size = DashboardSize(w=800, h=600, kind="exact")
    canvas = select_canvas(size, config={"layout": {"canvas_w": 1280, "canvas_h": 720}})
    # Scale = min(1280/800, 720/600) = min(1.6, 1.2) = 1.2
    assert canvas == (1280, 720, 1.2)
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/layout/test_canvas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tableau2pbir.layout'`.

- [x] **Step 3: Create `src/tableau2pbir/layout/__init__.py` (empty) and write minimal implementation**

```python
# src/tableau2pbir/layout/__init__.py
```

```python
# src/tableau2pbir/layout/canvas.py
"""Canvas size selection — §6 Stage 5 step 2 + step 3."""
from __future__ import annotations

from tableau2pbir.ir.dashboard import DashboardSize

_DEFAULT_W = 1280
_DEFAULT_H = 720


def select_canvas(size: DashboardSize, config: dict) -> tuple[int, int, float]:
    """Return (canvas_w, canvas_h, scale). Scale is applied to all leaf rects."""
    layout_cfg = (config or {}).get("layout", {}) or {}
    override_w = layout_cfg.get("canvas_w")
    override_h = layout_cfg.get("canvas_h")

    if size.kind == "automatic" or (size.w == 0 or size.h == 0):
        nominal_w, nominal_h = _DEFAULT_W, _DEFAULT_H
    else:
        nominal_w, nominal_h = size.w, size.h

    if override_w and override_h:
        scale = min(override_w / nominal_w, override_h / nominal_h)
        return (override_w, override_h, scale)
    return (nominal_w, nominal_h, 1.0)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/layout/test_canvas.py -v`
Expected: PASS (4 tests).

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/layout/__init__.py src/tableau2pbir/layout/canvas.py tests/unit/layout/__init__.py tests/unit/layout/test_canvas.py
git commit -m "feat(layout): add canvas size selection with config override"
```

---

### Task 2: Container-tree walker → absolute rects

**Files:**
- Create: `src/tableau2pbir/layout/walker.py`
- Test: `tests/unit/layout/test_walker.py`

The walker takes the dashboard's `layout_tree` (a `Container | Leaf`) plus the canvas `(w, h, scale)` and returns a list of `(leaf_id, position, z_order)` tuples — leaves in document order, positions in absolute pixel space at the canvas size. Floating leaves keep their explicit `position` (scaled). Tiled containers split their rect among children: `h` containers split horizontally, `v` containers split vertically; padding is consumed off the parent before the split.

- [x] **Step 1: Write the failing test**

```python
# tests/unit/layout/test_walker.py
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Leaf, LeafKind, Position,
)
from tableau2pbir.layout.walker import walk_layout, ResolvedLeaf


def _leaf(kind: LeafKind, payload: dict, position: Position | None = None) -> Leaf:
    return Leaf(kind=kind, payload=payload, position=position)


def test_single_leaf_fills_canvas():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "s1"})
    container = Container(kind=ContainerKind.H, children=(leaf,))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert len(out) == 1
    assert out[0].position == Position(x=0, y=0, w=1000, h=600)
    assert out[0].payload == {"sheet_id": "s1"}

def test_horizontal_split_two_equal():
    a = _leaf(LeafKind.SHEET, {"sheet_id": "a"})
    b = _leaf(LeafKind.SHEET, {"sheet_id": "b"})
    container = Container(kind=ContainerKind.H, children=(a, b))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert [r.position for r in out] == [
        Position(x=0, y=0, w=500, h=600),
        Position(x=500, y=0, w=500, h=600),
    ]

def test_vertical_split_three_equal():
    children = tuple(_leaf(LeafKind.SHEET, {"sheet_id": f"s{i}"}) for i in range(3))
    container = Container(kind=ContainerKind.V, children=children)
    out = walk_layout(container, canvas_w=900, canvas_h=600, scale=1.0)
    assert [r.position for r in out] == [
        Position(x=0, y=0,   w=900, h=200),
        Position(x=0, y=200, w=900, h=200),
        Position(x=0, y=400, w=900, h=200),
    ]

def test_floating_leaf_keeps_explicit_position_scaled():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "f"}, position=Position(x=100, y=50, w=200, h=150))
    container = Container(kind=ContainerKind.FLOATING, children=(leaf,))
    out = walk_layout(container, canvas_w=1280, canvas_h=720, scale=2.0)
    assert out[0].position == Position(x=200, y=100, w=400, h=300)

def test_z_order_reflects_document_order():
    a = _leaf(LeafKind.SHEET, {"sheet_id": "a"})
    b = _leaf(LeafKind.SHEET, {"sheet_id": "b"})
    container = Container(kind=ContainerKind.FLOATING, children=(a, b))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert [r.z_order for r in out] == [0, 1]

def test_padding_shrinks_child_rect():
    leaf = _leaf(LeafKind.SHEET, {"sheet_id": "p"})
    container = Container(kind=ContainerKind.H, children=(leaf,), padding=10)
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert out[0].position == Position(x=10, y=10, w=980, h=580)
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/layout/test_walker.py -v`
Expected: FAIL with `ImportError`.

- [x] **Step 3: Implement the walker**

```python
# src/tableau2pbir/layout/walker.py
"""Container-tree walker — §6 Stage 5 step 1 + step 4 + step 5."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Leaf, LeafKind, Position,
)


@dataclass(frozen=True)
class ResolvedLeaf:
    kind: LeafKind
    payload: dict[str, Any]
    position: Position
    z_order: int


def walk_layout(root: Container | Leaf, canvas_w: int, canvas_h: int, scale: float) -> list[ResolvedLeaf]:
    out: list[ResolvedLeaf] = []
    _counter = [0]
    _walk(root, x=0, y=0, w=canvas_w, h=canvas_h, scale=scale, out=out, counter=_counter)
    return out


def _walk(node, x: int, y: int, w: int, h: int, scale: float,
          out: list[ResolvedLeaf], counter: list[int]) -> None:
    if isinstance(node, Leaf):
        if node.position is not None:
            pos = Position(
                x=int(node.position.x * scale),
                y=int(node.position.y * scale),
                w=int(node.position.w * scale),
                h=int(node.position.h * scale),
            )
        else:
            pos = Position(x=x, y=y, w=w, h=h)
        out.append(ResolvedLeaf(kind=node.kind, payload=node.payload, position=pos, z_order=counter[0]))
        counter[0] += 1
        return

    pad = node.padding
    inner_x, inner_y = x + pad, y + pad
    inner_w, inner_h = max(0, w - 2 * pad), max(0, h - 2 * pad)

    if node.kind == ContainerKind.FLOATING:
        for child in node.children:
            _walk(child, inner_x, inner_y, inner_w, inner_h, scale, out, counter)
        return

    n = len(node.children) or 1
    if node.kind == ContainerKind.H:
        seg = inner_w // n
        for i, child in enumerate(node.children):
            child_w = inner_w - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x + seg * i, inner_y, child_w, inner_h, scale, out, counter)
    else:  # V
        seg = inner_h // n
        for i, child in enumerate(node.children):
            child_h = inner_h - seg * (n - 1) if i == n - 1 else seg
            _walk(child, inner_x, inner_y + seg * i, inner_w, child_h, scale, out, counter)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/layout/test_walker.py -v`
Expected: PASS (6 tests).

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/layout/walker.py tests/unit/layout/test_walker.py
git commit -m "feat(layout): add container-tree walker resolving absolute leaf rects"
```

---

### Task 3: Off-canvas clamping

**Files:**
- Modify: `src/tableau2pbir/layout/walker.py`
- Test: `tests/unit/layout/test_walker.py`

A floating leaf may have a position that extends past the canvas. Per §6 Stage 5 step 6, clamp it and record a warning (the warning surfaces in the stage's `errors`, not here). When the clamped rect has zero or negative area, drop it (return `None` instead of a `ResolvedLeaf` and tag it). We surface clamp/drop decisions on the `ResolvedLeaf` itself with two new fields: `clamped: bool` and `dropped: bool`. Dropped leaves stay in the output list (so the stage runner can log them) but their position area is 0.

- [x] **Step 1: Write the failing test**

```python
# tests/unit/layout/test_walker.py — append:
def test_floating_leaf_off_canvas_is_clamped():
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "x"},
                position=Position(x=900, y=500, w=500, h=400))
    container = Container(kind=ContainerKind.FLOATING, children=(leaf,))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert out[0].clamped is True
    assert out[0].dropped is False
    assert out[0].position == Position(x=900, y=500, w=100, h=100)

def test_floating_leaf_completely_off_canvas_is_dropped():
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "x"},
                position=Position(x=2000, y=2000, w=100, h=100))
    container = Container(kind=ContainerKind.FLOATING, children=(leaf,))
    out = walk_layout(container, canvas_w=1000, canvas_h=600, scale=1.0)
    assert out[0].dropped is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/layout/test_walker.py -v -k "clamp or drop"`
Expected: FAIL — `clamped` / `dropped` not on `ResolvedLeaf`.

- [x] **Step 3: Update `ResolvedLeaf` and `_walk`**

```python
# src/tableau2pbir/layout/walker.py — replace ResolvedLeaf and add clamp logic in the Leaf branch:

@dataclass(frozen=True)
class ResolvedLeaf:
    kind: LeafKind
    payload: dict[str, Any]
    position: Position
    z_order: int
    clamped: bool = False
    dropped: bool = False


def _clamp(pos: Position, canvas_w: int, canvas_h: int) -> tuple[Position, bool, bool]:
    x, y = pos.x, pos.y
    right = pos.x + pos.w
    bottom = pos.y + pos.h
    new_right = min(right, canvas_w)
    new_bottom = min(bottom, canvas_h)
    new_w = max(0, new_right - x)
    new_h = max(0, new_bottom - y)
    clamped = (new_w != pos.w) or (new_h != pos.h)
    dropped = (new_w <= 0 or new_h <= 0 or x >= canvas_w or y >= canvas_h)
    if dropped:
        return Position(x=x, y=y, w=0, h=0), False, True
    return Position(x=x, y=y, w=new_w, h=new_h), clamped, False
```

Then in `_walk`, after computing `pos` for a leaf with explicit `position`, run it through `_clamp`:

```python
    if isinstance(node, Leaf):
        if node.position is not None:
            scaled = Position(
                x=int(node.position.x * scale),
                y=int(node.position.y * scale),
                w=int(node.position.w * scale),
                h=int(node.position.h * scale),
            )
            pos, clamped, dropped = _clamp(scaled, canvas_w, canvas_h)
        else:
            pos, clamped, dropped = Position(x=x, y=y, w=w, h=h), False, False
        out.append(ResolvedLeaf(
            kind=node.kind, payload=node.payload, position=pos,
            z_order=counter[0], clamped=clamped, dropped=dropped,
        ))
        counter[0] += 1
        return
```

(Add `canvas_w` and `canvas_h` as `_walk` arguments and thread them through; current implementation already has `canvas_w`/`canvas_h` only at the public wrapper — pass them down.)

- [x] **Step 4: Run tests**

Run: `pytest tests/unit/layout/test_walker.py -v`
Expected: PASS (8 tests, all 6 prior + 2 new).

- [x] **Step 5: Commit**

```bash
git add src/tableau2pbir/layout/walker.py tests/unit/layout/test_walker.py
git commit -m "feat(layout): clamp off-canvas floating leaves; drop fully-out-of-bounds"
```

---

### Task 4: Tableau leaf-kind → PBI object-type mapping

**Files:**
- Create: `src/tableau2pbir/layout/leaf_types.py`
- Test: `tests/unit/layout/test_leaf_types.py`

Per §6 Stage 5 step 4, a fixed table maps each `LeafKind` to a downstream "object plan" string consumed by Stage 7. Stage 5 itself doesn't write PBIR JSON — it just labels the leaf so Stage 7 dispatches correctly. The mapping is one-to-one for v1; placeholder leaves (web-page, blank) carry that label and emit a placeholder visual in Stage 7.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/layout/test_leaf_types.py
from tableau2pbir.ir.dashboard import LeafKind
from tableau2pbir.layout.leaf_types import map_leaf_kind, PbiObjectKind

def test_sheet_maps_to_visual():
    assert map_leaf_kind(LeafKind.SHEET) == PbiObjectKind.VISUAL

def test_filter_card_maps_to_slicer():
    assert map_leaf_kind(LeafKind.FILTER_CARD) == PbiObjectKind.SLICER_FILTER

def test_parameter_card_maps_to_parameter_slicer():
    assert map_leaf_kind(LeafKind.PARAMETER_CARD) == PbiObjectKind.SLICER_PARAMETER

def test_legend_is_suppressed_with_host_flag():
    assert map_leaf_kind(LeafKind.LEGEND) == PbiObjectKind.LEGEND_SUPPRESS

def test_text_image_navigation_pass_through():
    assert map_leaf_kind(LeafKind.TEXT) == PbiObjectKind.TEXTBOX
    assert map_leaf_kind(LeafKind.IMAGE) == PbiObjectKind.IMAGE
    assert map_leaf_kind(LeafKind.NAVIGATION) == PbiObjectKind.NAV_BUTTON

def test_web_page_and_blank_become_placeholder():
    assert map_leaf_kind(LeafKind.WEB_PAGE) == PbiObjectKind.PLACEHOLDER
    assert map_leaf_kind(LeafKind.BLANK) == PbiObjectKind.DROP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/layout/test_leaf_types.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/layout/leaf_types.py
"""LeafKind → PBI object-kind mapping. §6 Stage 5 step 4."""
from __future__ import annotations

from enum import Enum

from tableau2pbir.ir.dashboard import LeafKind


class PbiObjectKind(str, Enum):
    VISUAL = "visual"
    SLICER_FILTER = "slicer_filter"
    SLICER_PARAMETER = "slicer_parameter"
    LEGEND_SUPPRESS = "legend_suppress"
    TEXTBOX = "textbox"
    IMAGE = "image"
    NAV_BUTTON = "nav_button"
    PLACEHOLDER = "placeholder"
    DROP = "drop"


_TABLE: dict[LeafKind, PbiObjectKind] = {
    LeafKind.SHEET:          PbiObjectKind.VISUAL,
    LeafKind.FILTER_CARD:    PbiObjectKind.SLICER_FILTER,
    LeafKind.PARAMETER_CARD: PbiObjectKind.SLICER_PARAMETER,
    LeafKind.LEGEND:         PbiObjectKind.LEGEND_SUPPRESS,
    LeafKind.TEXT:           PbiObjectKind.TEXTBOX,
    LeafKind.IMAGE:          PbiObjectKind.IMAGE,
    LeafKind.NAVIGATION:     PbiObjectKind.NAV_BUTTON,
    LeafKind.WEB_PAGE:       PbiObjectKind.PLACEHOLDER,
    LeafKind.BLANK:          PbiObjectKind.DROP,
}


def map_leaf_kind(kind: LeafKind) -> PbiObjectKind:
    return _TABLE[kind]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/layout/test_leaf_types.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/layout/leaf_types.py tests/unit/layout/test_leaf_types.py
git commit -m "feat(layout): map Tableau leaf kinds to PBI object kinds"
```

---

### Task 5: Stage 5 summary renderer

**Files:**
- Create: `src/tableau2pbir/layout/summary.py`
- Test: included in Task 6 stage runner test

- [ ] **Step 1: Write the implementation directly (rendered text is end-to-end-tested in Task 6)**

```python
# src/tableau2pbir/layout/summary.py
"""Stage 5 summary.md renderer."""
from __future__ import annotations


def render_summary(per_dashboard: list[dict]) -> str:
    lines = ["# Stage 5 — compute layout", ""]
    if not per_dashboard:
        lines.append("_no dashboards in workbook_")
        return "\n".join(lines) + "\n"
    lines.append("| dashboard | canvas | leaves | clamped | dropped | placeholder_ratio |")
    lines.append("|---|---|---|---|---|---|")
    for d in per_dashboard:
        ratio = f"{d['placeholder_ratio']:.2f}" if d["leaves"] else "n/a"
        lines.append(
            f"| {d['name']} | {d['canvas_w']}x{d['canvas_h']} (scale {d['scale']:.2f}) "
            f"| {d['leaves']} | {d['clamped']} | {d['dropped']} | {ratio} |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 2: Commit**

```bash
git add src/tableau2pbir/layout/summary.py
git commit -m "feat(layout): add stage 5 summary.md renderer"
```

---

### Task 6: Stage 5 runner

**Files:**
- Modify: `src/tableau2pbir/stages/s05_compute_layout.py`
- Test: `tests/unit/stages/test_s05_compute_layout.py`

The stage's `run(input_json, ctx)` parses the IR JSON (from stage 4 output), iterates dashboards, walks each layout tree, mutates `Leaf.position`, and returns the IR-shaped dict back. Clamped/dropped leaves emit `StageError` records (severity `warn`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/stages/test_s05_compute_layout.py
from pathlib import Path

from tableau2pbir.ir.common import FieldRef, UnsupportedItem
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s05_compute_layout


def _make_ir_dict(dashboard: Dashboard) -> dict:
    wb = Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="abc",
        tableau_version="2024.1", config={},
        data_model=DataModel(), sheets=(), dashboards=(dashboard,), unsupported=(),
    )
    return wb.model_dump(mode="json")


def test_stage5_resolves_leaf_positions(tmp_path: Path):
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"})
    dash = Dashboard(
        id="d1", name="Page1",
        size=DashboardSize(w=1280, h=720, kind="exact"),
        layout_tree=Container(kind=ContainerKind.H, children=(leaf,)),
    )
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=5)
    result = s05_compute_layout.run(_make_ir_dict(dash), ctx)
    pos = result.output["dashboards"][0]["layout_tree"]["children"][0]["position"]
    assert pos == {"x": 0, "y": 0, "w": 1280, "h": 720}
    assert "Stage 5" in result.summary_md


def test_stage5_warns_on_clamp(tmp_path: Path):
    leaf = Leaf(
        kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
        position=Position(x=900, y=500, w=500, h=400),
    )
    dash = Dashboard(
        id="d1", name="Page1",
        size=DashboardSize(w=1000, h=600, kind="exact"),
        layout_tree=Container(kind=ContainerKind.FLOATING, children=(leaf,)),
    )
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=5)
    result = s05_compute_layout.run(_make_ir_dict(dash), ctx)
    codes = [e.code for e in result.errors]
    assert "layout.leaf_clamped" in codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/stages/test_s05_compute_layout.py -v`
Expected: FAIL — current stub doesn't populate positions.

- [ ] **Step 3: Implement the stage runner**

```python
# src/tableau2pbir/stages/s05_compute_layout.py
"""Stage 5 — compute layout (pure python). §6 Stage 5."""
from __future__ import annotations

from typing import Any

from tableau2pbir.ir.dashboard import Container, Leaf, Position
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.layout.canvas import select_canvas
from tableau2pbir.layout.walker import walk_layout
from tableau2pbir.layout.leaf_types import PbiObjectKind, map_leaf_kind
from tableau2pbir.layout.summary import render_summary
from tableau2pbir.pipeline import StageContext, StageError, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    per_dashboard: list[dict] = []
    errors: list[StageError] = []

    new_dashboards = []
    for dash in wb.dashboards:
        canvas_w, canvas_h, scale = select_canvas(dash.size, ctx.config or {})
        resolved = walk_layout(dash.layout_tree, canvas_w, canvas_h, scale)

        # Re-walk the original tree, splicing in the resolved positions by document order.
        positions_iter = iter(resolved)
        new_tree = _rebuild_tree(dash.layout_tree, positions_iter)
        new_dash = dash.model_copy(update={"layout_tree": new_tree})
        new_dashboards.append(new_dash)

        clamped = sum(1 for r in resolved if r.clamped)
        dropped = sum(1 for r in resolved if r.dropped)
        placeholders = sum(
            1 for r in resolved
            if map_leaf_kind(r.kind) in (PbiObjectKind.PLACEHOLDER, PbiObjectKind.DROP)
        )
        leaves = len(resolved) or 1
        per_dashboard.append({
            "name": dash.name, "canvas_w": canvas_w, "canvas_h": canvas_h, "scale": scale,
            "leaves": len(resolved), "clamped": clamped, "dropped": dropped,
            "placeholder_ratio": placeholders / leaves,
        })
        for r in resolved:
            if r.clamped:
                errors.append(StageError(
                    severity="warn", code="layout.leaf_clamped",
                    object_id=dash.id, message=f"Leaf in dashboard '{dash.name}' clamped to canvas.",
                    fix_hint=None,
                ))
            if r.dropped:
                errors.append(StageError(
                    severity="warn", code="layout.leaf_dropped",
                    object_id=dash.id, message=f"Leaf in dashboard '{dash.name}' completely off-canvas; dropped.",
                    fix_hint=None,
                ))

    new_wb = wb.model_copy(update={"dashboards": tuple(new_dashboards)})
    return StageResult(
        output=new_wb.model_dump(mode="json"),
        summary_md=render_summary(per_dashboard),
        errors=tuple(errors),
    )


def _rebuild_tree(node, positions_iter):
    if isinstance(node, Leaf):
        resolved = next(positions_iter)
        return node.model_copy(update={"position": resolved.position})
    new_children = tuple(_rebuild_tree(c, positions_iter) for c in node.children)
    return node.model_copy(update={"children": new_children})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/stages/test_s05_compute_layout.py -v`
Expected: PASS (2 tests).

Then run the broader suite to make sure nothing regressed:

Run: `pytest tests/ -v -x`
Expected: ALL GREEN.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/stages/s05_compute_layout.py tests/unit/stages/test_s05_compute_layout.py
git commit -m "feat(stage5): replace stub with layout walker; populate Leaf.position; warn on clamp/drop"
```

---

### Task 7: Stage 5 contract test (JSON Schema validity)

**Files:**
- Create: `tests/contract/test_stage5_layout_contract.py`

After Stage 5 the IR JSON must still validate against the IR JSON Schema (§5.4). Stage 5 only fills already-optional `position` fields, so this is a smoke check.

- [ ] **Step 1: Write the test**

```python
# tests/contract/test_stage5_layout_contract.py
import json
from pathlib import Path

import pytest

from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext, run_stage


@pytest.mark.parametrize("fixture", ["dashboard_tiled_floating", "trivial"])
def test_stage5_output_validates_against_ir(synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str):
    ctx = StageContext(workbook_id=fixture, output_dir=tmp_path, config={}, stage_number=1)
    result = run_stage("extract", {"path": str(synthetic_fixtures_dir / f"{fixture}.twb")}, ctx)
    for stage in ("canonicalize", "translate_calcs", "map_visuals", "compute_layout"):
        result = run_stage(stage, result.output, ctx.model_copy(update={"stage_number": ctx.stage_number + 1}))
    Workbook.model_validate(result.output)  # raises if invalid
```

(If `run_stage` is not yet exported by `pipeline.py`, the test invokes `s05_compute_layout.run` directly using the prior stage's output — adapt to the actual pipeline API.)

- [ ] **Step 2: Run test**

Run: `pytest tests/contract/test_stage5_layout_contract.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_stage5_layout_contract.py
git commit -m "test(contract): stage 5 output round-trips through IR validator"
```

---

## Stage 6 — build TMDL (Tasks 8–18)

### Task 8: TMDL identifier + string escaping

**Files:**
- Create: `src/tableau2pbir/emit/__init__.py` (empty)
- Create: `src/tableau2pbir/emit/tmdl/__init__.py` (empty)
- Create: `src/tableau2pbir/emit/tmdl/escape.py`
- Test: `tests/unit/emit/tmdl/test_escape.py`

TMDL identifiers must be quoted with single-quotes when they contain spaces or special chars; embedded single quotes double up. String literals use double quotes; embedded double quotes double up.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_escape.py
from tableau2pbir.emit.tmdl.escape import tmdl_ident, tmdl_string

def test_simple_ident_unquoted():
    assert tmdl_ident("Sales") == "Sales"

def test_ident_with_space_quoted():
    assert tmdl_ident("Total Revenue") == "'Total Revenue'"

def test_ident_with_apostrophe_doubled():
    assert tmdl_ident("Bob's KPIs") == "'Bob''s KPIs'"

def test_string_literal_quotes_doubled():
    assert tmdl_string('a "b" c') == '"a ""b"" c"'

def test_empty_ident_quoted():
    assert tmdl_ident("") == "''"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/emit/tmdl/test_escape.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/__init__.py
```

```python
# src/tableau2pbir/emit/tmdl/__init__.py
```

```python
# src/tableau2pbir/emit/tmdl/escape.py
"""TMDL identifier and string-literal escaping."""
from __future__ import annotations

import re

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def tmdl_ident(name: str) -> str:
    if name and _SAFE_IDENT.match(name):
        return name
    return "'" + name.replace("'", "''") + "'"


def tmdl_string(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_escape.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/__init__.py src/tableau2pbir/emit/tmdl/__init__.py src/tableau2pbir/emit/tmdl/escape.py tests/unit/emit/__init__.py tests/unit/emit/tmdl/__init__.py tests/unit/emit/tmdl/test_escape.py
git commit -m "feat(tmdl): add identifier and string-literal escaping helpers"
```

---

### Task 9: `database.tmdl` and `model.tmdl`

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/database.py`
- Create: `src/tableau2pbir/emit/tmdl/model.py`
- Test: `tests/unit/emit/tmdl/test_database.py`, `tests/unit/emit/tmdl/test_model.py`

These two are essentially fixed text with workbook name and culture substituted.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/emit/tmdl/test_database.py
from tableau2pbir.emit.tmdl.database import render_database

def test_database_tmdl_basic():
    out = render_database(name="MyWorkbook", compatibility_level=1567)
    assert "database 'MyWorkbook'" in out
    assert "compatibilityLevel: 1567" in out
```

```python
# tests/unit/emit/tmdl/test_model.py
from tableau2pbir.emit.tmdl.model import render_model

def test_model_tmdl_includes_culture_and_default_table():
    out = render_model(culture="en-US")
    assert "model Model" in out
    assert "culture: en-US" in out
    assert "defaultPowerBIDataSourceVersion" in out
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_database.py tests/unit/emit/tmdl/test_model.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/database.py
"""Render database.tmdl. See PBIR TMDL spec."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident


def render_database(name: str, compatibility_level: int = 1567) -> str:
    return (
        f"database {tmdl_ident(name)}\n"
        f"\tcompatibilityLevel: {compatibility_level}\n"
    )
```

```python
# src/tableau2pbir/emit/tmdl/model.py
"""Render model.tmdl."""
from __future__ import annotations


def render_model(culture: str = "en-US") -> str:
    return (
        "model Model\n"
        f"\tculture: {culture}\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: " + culture + "\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n"
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/emit/tmdl/test_database.py tests/unit/emit/tmdl/test_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/database.py src/tableau2pbir/emit/tmdl/model.py tests/unit/emit/tmdl/test_database.py tests/unit/emit/tmdl/test_model.py
git commit -m "feat(tmdl): render database.tmdl and model.tmdl"
```

---

### Task 10: Column TMDL fragment

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/column.py`
- Test: `tests/unit/emit/tmdl/test_column.py`

A column fragment is rendered nested under a `table` block and can be either a raw column (with `dataType` only) or a calculated column (with `expression: <DAX>`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_column.py
from tableau2pbir.emit.tmdl.column import render_column
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole


def test_raw_column():
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    out = render_column(col)
    assert "column Region" in out
    assert "dataType: string" in out
    assert "expression" not in out

def test_calculated_column():
    col = Column(
        id="c2", name="Region Upper", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.CALCULATED,
        tableau_expr="UPPER([Region])",
        dax_expr="UPPER('Sales'[Region])",
    )
    out = render_column(col)
    assert "column 'Region Upper'" in out
    assert "expression: UPPER('Sales'[Region])" in out

def test_calculated_column_without_dax_emits_nothing():
    col = Column(
        id="c3", name="Skip Me", datatype="string",
        role=ColumnRole.DIMENSION, kind=ColumnKind.CALCULATED,
        tableau_expr="some_unsupported", dax_expr=None,
    )
    assert render_column(col) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_column.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/column.py
"""Render a column or calculated-column block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Column, ColumnKind


def render_column(col: Column) -> str:
    if col.kind == ColumnKind.CALCULATED and col.dax_expr is None:
        return ""  # deferred / unsupported / not yet translated
    head = "column " + tmdl_ident(col.name)
    body_lines = [f"dataType: {col.datatype or 'string'}"]
    if col.kind == ColumnKind.CALCULATED:
        body_lines.append(f"expression: {col.dax_expr}")
    body = indent("\n".join(body_lines), "\t")
    return f"\t{head}\n{body}\n"
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_column.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/column.py tests/unit/emit/tmdl/test_column.py
git commit -m "feat(tmdl): render column / calculated-column fragments"
```

---

### Task 11: Measure TMDL fragment

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/measure.py`
- Test: `tests/unit/emit/tmdl/test_measure.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_measure.py
from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope


def test_aggregate_measure():
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([Sales])", dax_expr="SUM('Sales'[Sales])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    out = render_measure(calc)
    assert "measure 'Total Sales'" in out
    assert "expression: SUM('Sales'[Sales])" in out

def test_measure_with_no_dax_returns_empty():
    calc = Calculation(
        id="m2", name="Deferred Calc", scope=CalculationScope.MEASURE,
        tableau_expr="WINDOW_SUM(SUM([x]))", dax_expr=None,
        kind=CalculationKind.TABLE_CALC, phase=CalculationPhase.VIZ,
    )
    assert render_measure(calc) == ""

def test_column_scope_is_not_a_measure():
    calc = Calculation(
        id="c1", name="Row Calc", scope=CalculationScope.COLUMN,
        tableau_expr="[A]+[B]", dax_expr="'T'[A]+'T'[B]",
        kind=CalculationKind.ROW, phase=CalculationPhase.ROW,
    )
    assert render_measure(calc) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_measure.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/measure.py
"""Render a measure block (nested under a table)."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.calculation import Calculation, CalculationScope


def render_measure(calc: Calculation) -> str:
    if calc.scope != CalculationScope.MEASURE or not calc.dax_expr:
        return ""
    head = "measure " + tmdl_ident(calc.name)
    body = indent(f"expression: {calc.dax_expr}", "\t")
    return f"\t{head}\n{body}\n"
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_measure.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/measure.py tests/unit/emit/tmdl/test_measure.py
git commit -m "feat(tmdl): render measure fragment; skip non-measure / null-DAX calcs"
```

---

### Task 12: Datasource → M expression (Tier 1, Tier 2, Tier 4 placeholder)

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/m_expression.py`
- Test: `tests/unit/emit/tmdl/test_m_expression.py`

Per §5.8: Tier 1 emits a real M with values inlined; Tier 2 emits an M with server/database from `connection_params` and credentials omitted; Tier 4 emits a placeholder `error` step that surfaces the user_action_required text on first open. Tier 3 is already-deferred via `unsupported[]` so its datasources still hit Tier-1 or Tier-2 emission paths, just for the surviving connection — this plan treats Tier 3 connectors that survive to Stage 6 as Tier 1/2-equivalent (Plan 2 mapped `pbi_m_connector` for them).

The function returns a multi-line M expression string (the `M` partition body) — the `partition` block wrapper is added in `table.py` (Task 13).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_m_expression.py
from tableau2pbir.emit.tmdl.m_expression import render_m_expression
from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def _ds(**kw):
    defaults = dict(
        id="d", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/data/sales.csv"},
        user_action_required=(), table_ids=(), extract_ignored=False,
    )
    defaults.update(kw)
    return Datasource(**defaults)


def test_csv_tier1():
    ds = _ds()
    m = render_m_expression(ds, table_name="Sales")
    assert "Csv.Document(File.Contents(\"C:/data/sales.csv\"))" in m
    assert "Source" in m

def test_sql_server_tier1():
    ds = _ds(
        tableau_kind="sqlserver", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Sql.Database",
        connection_params={"server": "srv01", "dbname": "Adventure"},
    )
    m = render_m_expression(ds, table_name="DimCustomer")
    assert "Sql.Database(\"srv01\", \"Adventure\")" in m

def test_snowflake_tier2_omits_credentials():
    ds = _ds(
        tableau_kind="snowflake", connector_tier=ConnectorTier.TIER_2,
        pbi_m_connector="Snowflake.Databases",
        connection_params={"server": "acct.snowflakecomputing.com", "warehouse": "WH"},
        user_action_required=("enter credentials",),
    )
    m = render_m_expression(ds, table_name="ORDERS")
    assert "Snowflake.Databases(\"acct.snowflakecomputing.com\", \"WH\")" in m
    assert "password" not in m.lower()

def test_tier4_emits_error_placeholder():
    ds = _ds(
        tableau_kind="webdata", connector_tier=ConnectorTier.TIER_4,
        pbi_m_connector=None, connection_params={},
        user_action_required=("Web Data Connector unsupported",),
    )
    m = render_m_expression(ds, table_name="X")
    assert "error" in m
    assert "Web Data Connector unsupported" in m
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_m_expression.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/m_expression.py
"""Datasource → M partition body. §5.8 connector matrix."""
from __future__ import annotations

from tableau2pbir.ir.datasource import ConnectorTier, Datasource


def render_m_expression(ds: Datasource, table_name: str) -> str:
    if ds.connector_tier == ConnectorTier.TIER_4 or not ds.pbi_m_connector:
        msg = "; ".join(ds.user_action_required) or f"connector {ds.tableau_kind} not supported"
        msg_escaped = msg.replace('"', '\\"')
        return (
            "let\n"
            f"    Source = error \"{msg_escaped}\"\n"
            "in\n"
            "    Source"
        )

    src_call = _source_call(ds)
    nav = f"#\"{table_name}\""
    return (
        "let\n"
        f"    Source = {src_call},\n"
        f"    Navigation = Source{{[Item={_string(table_name)}]}}[Data]\n"
        "in\n"
        "    Navigation"
    )


def _source_call(ds: Datasource) -> str:
    p = ds.connection_params
    fn = ds.pbi_m_connector
    if fn == "Csv.Document":
        return f"Csv.Document(File.Contents({_string(p.get('filename', ''))}))"
    if fn == "Excel.Workbook":
        return f"Excel.Workbook(File.Contents({_string(p.get('filename', ''))}), null, true)"
    if fn == "Sql.Database":
        return f"Sql.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Snowflake.Databases":
        return f"Snowflake.Databases({_string(p.get('server', ''))}, {_string(p.get('warehouse', ''))})"
    if fn == "DatabricksMultiCloud.Catalogs":
        return f"DatabricksMultiCloud.Catalogs({_string(p.get('host', ''))}, {_string(p.get('http_path', ''))})"
    if fn == "GoogleBigQuery.Database":
        return f"GoogleBigQuery.Database({_string(p.get('billing_project', ''))})"
    if fn == "PostgreSQL.Database":
        return f"PostgreSQL.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Oracle.Database":
        return f"Oracle.Database({_string(p.get('server', ''))})"
    if fn == "AmazonRedshift.Database":
        return f"AmazonRedshift.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    if fn == "Teradata.Database":
        return f"Teradata.Database({_string(p.get('server', ''))})"
    if fn == "MySql.Database":
        return f"MySql.Database({_string(p.get('server', ''))}, {_string(p.get('dbname') or p.get('database', ''))})"
    return f"{fn}()"


def _string(s: str) -> str:
    return '"' + (s or "").replace('"', '""') + '"'
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_m_expression.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/m_expression.py tests/unit/emit/tmdl/test_m_expression.py
git commit -m "feat(tmdl): render datasource M partition per connector tier"
```

---

### Task 13: Table TMDL renderer (assemble columns + measures + partition)

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/table.py`
- Test: `tests/unit/emit/tmdl/test_table.py`

A `tables/<name>.tmdl` file pieces together: the `table <name>` header, every column block, every measure block whose `Calculation` belongs to the table, and one `partition` block with the M expression.

Mapping calculation → table for v1: a measure-scope `Calculation` is attached to the **first** table of the workbook's primary datasource (the one referenced by the most sheets) — this matches the Tableau "all measures live on one table" pattern. A column-scope calculated `Calculation` lives on the table whose name matches the field reference root.

For v1 simplicity this task accepts the table → owned-calculations mapping as an explicit argument; the assignment heuristic ships in Task 16 (the orchestrator).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_table.py
from tableau2pbir.emit.tmdl.table import render_table
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole


def test_table_with_one_column_one_measure_csv_partition():
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document",
        connection_params={"filename": "C:/data.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    cols = [Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)]
    measures = [Calculation(
        id="m1", name="Total", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([X])", dax_expr="SUM('Sales'[X])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )]
    out = render_table(name="Sales", columns=cols, measures=measures, datasource=ds)
    assert out.startswith("table Sales")
    assert "column Region" in out
    assert "measure Total" in out
    assert "partition Sales = m" in out
    assert "Csv.Document" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_table.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/table.py
"""Render tables/<name>.tmdl."""
from __future__ import annotations

from textwrap import indent

from tableau2pbir.emit.tmdl.column import render_column
from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.emit.tmdl.measure import render_measure
from tableau2pbir.emit.tmdl.m_expression import render_m_expression
from tableau2pbir.ir.calculation import Calculation
from tableau2pbir.ir.datasource import Datasource
from tableau2pbir.ir.model import Column


def render_table(name: str, columns: list[Column], measures: list[Calculation],
                 datasource: Datasource) -> str:
    parts = [f"table {tmdl_ident(name)}", ""]
    for col in columns:
        frag = render_column(col)
        if frag:
            parts.append(frag.rstrip())
    for calc in measures:
        frag = render_measure(calc)
        if frag:
            parts.append(frag.rstrip())
    m_body = render_m_expression(datasource, table_name=name)
    partition = (
        f"\tpartition {tmdl_ident(name)} = m\n"
        f"\t\tmode: import\n"
        f"\t\tsource =\n"
        f"{indent(m_body, chr(9) * 3)}"
    )
    parts.append(partition)
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_table.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/table.py tests/unit/emit/tmdl/test_table.py
git commit -m "feat(tmdl): render tables/<name>.tmdl assembling columns, measures, M partition"
```

---

### Task 14: Relationship TMDL renderer

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/relationship.py`
- Test: `tests/unit/emit/tmdl/test_relationship.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_relationship.py
from tableau2pbir.emit.tmdl.relationship import render_relationship
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.model import Relationship, RelationshipSource


def test_one_to_many_single_filter():
    rel = Relationship(
        id="r1",
        from_ref=FieldRef(table_id="Orders", column_id="CustomerKey"),
        to_ref=FieldRef(table_id="Customers", column_id="CustomerKey"),
        cardinality="many_to_one", cross_filter="single",
        source=RelationshipSource.TABLEAU_JOIN,
    )
    out = render_relationship(rel, from_table_name="Orders", to_table_name="Customers")
    assert "relationship r1" in out
    assert "fromColumn: Orders.CustomerKey" in out
    assert "toColumn: Customers.CustomerKey" in out
    assert "fromCardinality: many" in out
    assert "toCardinality: one" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_relationship.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/relationship.py
"""Render relationships/<id>.tmdl."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident
from tableau2pbir.ir.model import Relationship


_CARD_MAP = {
    "one_to_one":   ("one", "one"),
    "one_to_many":  ("one", "many"),
    "many_to_one":  ("many", "one"),
    "many_to_many": ("many", "many"),
}


def render_relationship(rel: Relationship, from_table_name: str, to_table_name: str) -> str:
    fr, to = _CARD_MAP.get(rel.cardinality, ("many", "one"))
    cf = "bothDirections" if rel.cross_filter == "both" else "oneDirection"
    return (
        f"relationship {tmdl_ident(rel.id)}\n"
        f"\tfromColumn: {from_table_name}.{rel.from_ref.column_id}\n"
        f"\ttoColumn: {to_table_name}.{rel.to_ref.column_id}\n"
        f"\tfromCardinality: {fr}\n"
        f"\ttoCardinality: {to}\n"
        f"\tcrossFilteringBehavior: {cf}\n"
    )
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_relationship.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/relationship.py tests/unit/emit/tmdl/test_relationship.py
git commit -m "feat(tmdl): render relationships/<id>.tmdl"
```

---

### Task 15: Parameter emission per intent (numeric_what_if, categorical_selector, internal_constant)

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/parameters.py`
- Test: `tests/unit/emit/tmdl/test_parameters.py`

Per §5.7 Stage 6 column:
- `numeric_what_if`: emit a disconnected table named `<param_name>` with one column `Value` defined by `GENERATESERIES(min, max, step)` and a measure `<param_name> SelectedValue = SELECTEDVALUE('<param>'[Value], <default>)`.
- `categorical_selector`: emit a disconnected table whose rows are the `allowed_values`, plus a `SelectedValue` measure.
- `internal_constant`: emit a hidden measure on the model named `<param_name>` returning the literal default.
- `formatting_control` and `unsupported`: emit nothing (deferred / already in unsupported[]).

The `min`/`max`/`step` for `numeric_what_if` come from `Parameter.allowed_values` — by Plan 2's classification, `numeric_what_if` parameters store `("min", "max", "step")` as the three first entries of `allowed_values`.

Each function returns a `dict[filename, content]` (filename is relative to `SemanticModel/`) so the orchestrator (Task 16) can write them.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_parameters.py
from tableau2pbir.emit.tmdl.parameters import render_parameter
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent


def test_numeric_what_if_emits_table_and_measure():
    p = Parameter(
        id="p1", name="Discount Rate", datatype="real", default="0.1",
        allowed_values=("0", "1", "0.05"),
        intent=ParameterIntent.NUMERIC_WHAT_IF, exposure=ParameterExposure.CARD,
    )
    files = render_parameter(p)
    body = files["tables/Discount Rate.tmdl"]
    assert "GENERATESERIES(0,1,0.05)" in body
    assert "measure 'Discount Rate SelectedValue'" in body

def test_categorical_selector_emits_rows_table():
    p = Parameter(
        id="p2", name="Region", datatype="string", default="West",
        allowed_values=("North", "South", "East", "West"),
        intent=ParameterIntent.CATEGORICAL_SELECTOR, exposure=ParameterExposure.CARD,
    )
    files = render_parameter(p)
    body = files["tables/Region.tmdl"]
    assert '{"North"}' in body or '"North"' in body
    assert "measure 'Region SelectedValue'" in body

def test_internal_constant_hidden_measure():
    p = Parameter(
        id="p3", name="Threshold", datatype="real", default="100",
        allowed_values=(),
        intent=ParameterIntent.INTERNAL_CONSTANT, exposure=ParameterExposure.CALC_ONLY,
    )
    files = render_parameter(p)
    assert any("measure Threshold" in body and "isHidden: true" in body for body in files.values())

def test_unsupported_intent_emits_nothing():
    p = Parameter(
        id="p4", name="X", datatype="string", default="",
        allowed_values=(), intent=ParameterIntent.UNSUPPORTED,
        exposure=ParameterExposure.SHELF,
    )
    assert render_parameter(p) == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_parameters.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/tmdl/parameters.py
"""Parameter emission per §5.7 Stage 6."""
from __future__ import annotations

from tableau2pbir.emit.tmdl.escape import tmdl_ident, tmdl_string
from tableau2pbir.ir.parameter import Parameter, ParameterIntent


def render_parameter(p: Parameter) -> dict[str, str]:
    if p.intent == ParameterIntent.NUMERIC_WHAT_IF:
        return _numeric_what_if(p)
    if p.intent == ParameterIntent.CATEGORICAL_SELECTOR:
        return _categorical_selector(p)
    if p.intent == ParameterIntent.INTERNAL_CONSTANT:
        return _internal_constant(p)
    return {}


def _numeric_what_if(p: Parameter) -> dict[str, str]:
    vals = p.allowed_values or ("0", "1", "0.1")
    mn, mx, step = (vals + ("0", "1", "0.1"))[:3]
    body = (
        f"table {tmdl_ident(p.name)}\n"
        f"\tcolumn Value\n"
        f"\t\tdataType: double\n\n"
        f"\tpartition {tmdl_ident(p.name)} = calculated\n"
        f"\t\tsource = GENERATESERIES({mn},{mx},{step})\n\n"
        f"\tmeasure {tmdl_ident(p.name + ' SelectedValue')}\n"
        f"\t\texpression: SELECTEDVALUE('{p.name}'[Value], {p.default})\n"
    )
    return {f"tables/{p.name}.tmdl": body}


def _categorical_selector(p: Parameter) -> dict[str, str]:
    rows = ", ".join("{" + tmdl_string(v) + "}" for v in p.allowed_values)
    body = (
        f"table {tmdl_ident(p.name)}\n"
        f"\tcolumn Value\n"
        f"\t\tdataType: string\n\n"
        f"\tpartition {tmdl_ident(p.name)} = calculated\n"
        f"\t\tsource = #table({{\"Value\"}}, {{{rows}}})\n\n"
        f"\tmeasure {tmdl_ident(p.name + ' SelectedValue')}\n"
        f"\t\texpression: SELECTEDVALUE('{p.name}'[Value], {tmdl_string(p.default)})\n"
    )
    return {f"tables/{p.name}.tmdl": body}


def _internal_constant(p: Parameter) -> dict[str, str]:
    literal = p.default if p.datatype in ("integer", "real") else tmdl_string(p.default)
    body = (
        f"\tmeasure {tmdl_ident(p.name)}\n"
        f"\t\texpression: {literal}\n"
        f"\t\tisHidden: true\n"
    )
    return {f"tables/_Constants.tmdl": _constants_header() + body}


def _constants_header() -> str:
    return "table _Constants\n\tisHidden: true\n\n"
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_parameters.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/parameters.py tests/unit/emit/tmdl/test_parameters.py
git commit -m "feat(tmdl): emit parameter tables/measures per ParameterIntent"
```

---

### Task 16: Atomic file-write helper + render orchestrator

**Files:**
- Create: `src/tableau2pbir/emit/_io.py`
- Create: `src/tableau2pbir/emit/tmdl/render.py`
- Test: `tests/unit/emit/tmdl/test_render.py`

The orchestrator turns a `Workbook` into a directory tree under `<output_dir>/SemanticModel/` and returns a manifest dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/tmdl/test_render.py
from pathlib import Path

from tableau2pbir.emit.tmdl.render import render_semantic_model
from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.parameter import Parameter, ParameterExposure, ParameterIntent
from tableau2pbir.ir.workbook import DataModel, Workbook


def _wb_with_one_table_and_one_measure() -> Workbook:
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([X])", dax_expr="SUM('Sales'[X])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    dm = DataModel(datasources=(ds,), tables=(table,), calculations=(calc,))
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=dm, sheets=(), dashboards=(), unsupported=(),
    )


def test_render_writes_files(tmp_path: Path):
    wb = _wb_with_one_table_and_one_measure()
    manifest = render_semantic_model(wb, tmp_path)
    sm = tmp_path / "SemanticModel"
    assert (sm / "database.tmdl").is_file()
    assert (sm / "model.tmdl").is_file()
    assert (sm / "tables" / "Sales.tmdl").is_file()
    assert "tables/Sales.tmdl" in manifest["files"]
    assert manifest["counts"]["tables"] == 1
    assert manifest["counts"]["measures"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/tmdl/test_render.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/_io.py
"""Atomic UTF-8 / LF file writes."""
from __future__ import annotations

from pathlib import Path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)
```

```python
# src/tableau2pbir/emit/tmdl/render.py
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

    cols_by_table = {t.id: [c for c in _all_columns(wb) if c.id in t.column_ids] for t in wb.data_model.tables}
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
            name=t.name, columns=cols_by_table.get(t.id, []),
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
    for p in wb.data_model.parameters:
        for fname, body in render_parameter(p).items():
            existing = (sm / fname)
            if existing.is_file():
                body = existing.read_text(encoding="utf-8") + "\n" + body  # append for _Constants
            write_text(sm / fname, body)
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


def _all_columns(wb: Workbook):
    seen = []
    for t in wb.data_model.tables:
        for c in getattr(wb.data_model, "columns", ()):
            if c.id in t.column_ids:
                seen.append(c)
    # IR keeps columns inside DataModel only via Table.column_ids → Column lookup;
    # if Plan 2 stores columns elsewhere, adapt this accessor.
    return seen
```

> NOTE for the implementer: verify whether columns live on `DataModel.columns` or are inlined into `Table.column_ids` referencing a workbook-level column list. Adjust `_all_columns` to read whichever exists. The tests above assume `DataModel.columns: tuple[Column, ...]` exists; if not, adapt the test fixture and the accessor together.

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/tmdl/test_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/_io.py src/tableau2pbir/emit/tmdl/render.py tests/unit/emit/tmdl/test_render.py
git commit -m "feat(tmdl): add render_semantic_model orchestrator + atomic write helper"
```

---

### Task 17: Stage 6 summary renderer + stage runner

**Files:**
- Create: `src/tableau2pbir/emit/tmdl/summary.py`
- Modify: `src/tableau2pbir/stages/s06_build_tmdl.py`
- Test: `tests/unit/stages/test_s06_build_tmdl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/stages/test_s06_build_tmdl.py
from pathlib import Path

from tableau2pbir.ir.calculation import Calculation, CalculationKind, CalculationPhase, CalculationScope
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.workbook import DataModel, Workbook
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s06_build_tmdl


def _wb() -> dict:
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    calc = Calculation(
        id="m1", name="Total Sales", scope=CalculationScope.MEASURE,
        tableau_expr="SUM([X])", dax_expr="SUM('Sales'[X])",
        kind=CalculationKind.AGGREGATE, phase=CalculationPhase.AGGREGATE,
    )
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,), calculations=(calc,)),
        sheets=(), dashboards=(), unsupported=(),
    ).model_dump(mode="json")


def test_stage6_writes_files_and_returns_manifest(tmp_path: Path):
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=6)
    result = s06_build_tmdl.run(_wb(), ctx)
    assert (tmp_path / "SemanticModel" / "database.tmdl").is_file()
    assert "tables/Sales.tmdl" in result.output["files"]
    assert result.output["counts"]["measures"] == 1
    assert "Stage 6" in result.summary_md
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/stages/test_s06_build_tmdl.py -v`
Expected: FAIL — current stub.

- [ ] **Step 3: Implement summary + runner**

```python
# src/tableau2pbir/emit/tmdl/summary.py
"""Stage 6 summary.md."""
from __future__ import annotations


def render_summary(manifest: dict) -> str:
    c = manifest.get("counts", {})
    return (
        "# Stage 6 — build TMDL\n\n"
        f"- files: {len(manifest.get('files', []))}\n"
        f"- tables: {c.get('tables', 0)}\n"
        f"- measures: {c.get('measures', 0)}\n"
        f"- relationships: {c.get('relationships', 0)}\n"
        f"- parameters emitted: {c.get('parameters', 0)}\n"
    )
```

```python
# src/tableau2pbir/stages/s06_build_tmdl.py
"""Stage 6 — build TMDL (pure python). §6 Stage 6."""
from __future__ import annotations

from typing import Any

from tableau2pbir.emit.tmdl.render import render_semantic_model
from tableau2pbir.emit.tmdl.summary import render_summary
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    manifest = render_semantic_model(wb, ctx.output_dir)
    return StageResult(
        output=manifest,
        summary_md=render_summary(manifest),
        errors=(),
    )
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/stages/test_s06_build_tmdl.py -v`
Expected: PASS.

Then run the broader suite:

Run: `pytest tests/ -v -x`
Expected: ALL GREEN.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/tmdl/summary.py src/tableau2pbir/stages/s06_build_tmdl.py tests/unit/stages/test_s06_build_tmdl.py
git commit -m "feat(stage6): replace stub with TMDL emission orchestrator"
```

---

### Task 18: Stage 6 contract test (TMDL well-formedness)

**Files:**
- Create: `tests/contract/test_stage6_tmdl_contract.py`

Plan 4 cannot run TabularEditor 2 (Plan 5 ships that). The contract test verifies textual structure: every `tables/*.tmdl` file starts with `table `, every `relationships/*.tmdl` starts with `relationship `, the file is utf-8 + LF-only, and balanced indentation.

- [ ] **Step 1: Write the test**

```python
# tests/contract/test_stage6_tmdl_contract.py
from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, run_stage


@pytest.mark.parametrize("fixture", ["trivial", "datasources_mixed", "params_all_intents"])
def test_stage6_emits_well_formed_tmdl(synthetic_fixtures_dir: Path, tmp_path: Path, fixture: str):
    ctx = StageContext(workbook_id=fixture, output_dir=tmp_path, config={}, stage_number=1)
    result = run_stage("extract", {"path": str(synthetic_fixtures_dir / f"{fixture}.twb")}, ctx)
    for stage in ("canonicalize", "translate_calcs", "map_visuals", "compute_layout", "build_tmdl"):
        result = run_stage(stage, result.output, ctx.model_copy(update={"stage_number": ctx.stage_number + 1}))
    sm = tmp_path / "SemanticModel"
    assert (sm / "database.tmdl").is_file()
    assert (sm / "model.tmdl").is_file()
    for path in (sm / "tables").glob("*.tmdl"):
        text = path.read_bytes()
        assert b"\r\n" not in text, f"{path} has CRLF"
        decoded = text.decode("utf-8")
        assert decoded.startswith("table "), f"{path} missing table header"
    for path in (sm / "relationships").glob("*.tmdl"):
        assert path.read_text(encoding="utf-8").startswith("relationship ")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/contract/test_stage6_tmdl_contract.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_stage6_tmdl_contract.py
git commit -m "test(contract): stage 6 TMDL output is utf-8/LF and headers are well-formed"
```

---

## Stage 7 — build report PBIR (Tasks 19–28)

### Task 19: Stable PBIR id generator

**Files:**
- Create: `src/tableau2pbir/emit/pbir/__init__.py` (empty)
- Create: `src/tableau2pbir/emit/pbir/ids.py`
- Test: `tests/unit/emit/pbir/test_ids.py` (folded into Task 20)

PBIR uses content-hash-stable ids for visuals and pages so re-runs diff cleanly.

- [ ] **Step 1: Write the implementation**

```python
# src/tableau2pbir/emit/pbir/__init__.py
```

```python
# src/tableau2pbir/emit/pbir/ids.py
"""Stable PBIR id generator (deterministic for diffable output)."""
from __future__ import annotations

import hashlib


def stable_id(*parts: str) -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return h[:16]
```

- [ ] **Step 2: Commit**

```bash
git add src/tableau2pbir/emit/pbir/__init__.py src/tableau2pbir/emit/pbir/ids.py
git commit -m "feat(pbir): stable id helper for visuals + pages"
```

---

### Task 20: `report.json` (root)

**Files:**
- Create: `src/tableau2pbir/emit/pbir/report.py`
- Test: `tests/unit/emit/pbir/test_report.py`

Per PBIR v2: `definition/report.json` carries report-level metadata, theme name, and `pages` ordering.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_report.py
import json

from tableau2pbir.emit.pbir.report import render_report


def test_report_json_minimal():
    out = render_report(report_name="Wb", page_order=["pageA", "pageB"])
    obj = json.loads(out)
    assert obj["$schema"].startswith("https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/")
    assert obj["pages"]["pageOrder"] == ["pageA", "pageB"]
    assert obj["pages"]["activePageName"] == "pageA"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/report.py
"""Render Report/definition/report.json."""
from __future__ import annotations

import json


def render_report(report_name: str, page_order: list[str]) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10"}},
        "pages": {
            "pageOrder": list(page_order),
            "activePageName": page_order[0] if page_order else "",
        },
    }
    return json.dumps(obj, indent=2)
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_report.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/report.py tests/unit/emit/pbir/test_report.py
git commit -m "feat(pbir): render report.json root"
```

---

### Task 21: Page emitter

**Files:**
- Create: `src/tableau2pbir/emit/pbir/page.py`
- Test: `tests/unit/emit/pbir/test_page.py`

Each Tableau dashboard becomes one PBIR `pages/<page_id>/page.json` with display name, ordinal, and canvas size.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_page.py
import json

from tableau2pbir.emit.pbir.page import render_page


def test_page_json_basic():
    out = render_page(page_id="p1", display_name="Revenue", ordinal=0, width=1280, height=720)
    obj = json.loads(out)
    assert obj["name"] == "p1"
    assert obj["displayName"] == "Revenue"
    assert obj["ordinal"] == 0
    assert obj["width"] == 1280
    assert obj["height"] == 720
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_page.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/page.py
"""Render pages/<page>/page.json."""
from __future__ import annotations

import json


def render_page(page_id: str, display_name: str, ordinal: int,
                width: int, height: int, filters: list | None = None) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "ordinal": ordinal,
        "width": width,
        "height": height,
        "filterConfig": {"filters": filters or []},
    }
    return json.dumps(obj, indent=2)
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_page.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/page.py tests/unit/emit/pbir/test_page.py
git commit -m "feat(pbir): render page.json"
```

---

### Task 22: Visual emitter (dispatch on visual_type from `Sheet.pbir_visual`)

**Files:**
- Create: `src/tableau2pbir/emit/pbir/visual.py`
- Test: `tests/unit/emit/pbir/test_visual.py`

A visual JSON file contains: name (id), position, visualType, query (datatransforms with one transform per encoding binding), and config. v1 emits a generic shape that PBI Desktop accepts for the seven supported visual types: a `name`, `visualType`, `objects` (formatting placeholder), and a `query` block whose `queryRef` blocks reference the IR field by `<table>.<column>` (or measure name).

For v1 we use a single emit function parameterized by the seven `visual_type` values; the per-type variations are limited to the `query` slot names that PBIR uses (`Y`, `Category`, etc.). A fixed table maps visualType → required slot order.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_visual.py
import json

from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import EncodingBinding, PbirVisual


def _bar_visual() -> PbirVisual:
    return PbirVisual(
        visual_type="clusteredBarChart",
        encoding_bindings=(
            EncodingBinding(channel="Category", source_field_id="Sales.Region"),
            EncodingBinding(channel="Y", source_field_id="Total Sales"),
        ),
        format={},
    )


def test_visual_json_has_position_and_query():
    pos = Position(x=10, y=20, w=400, h=300)
    out = render_visual(visual_id="v1", pbir_visual=_bar_visual(), position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["name"] == "v1"
    assert obj["position"]["x"] == 10
    assert obj["position"]["width"] == 400
    assert obj["visual"]["visualType"] == "clusteredBarChart"
    assert any("Region" in str(p) for p in obj["visual"]["query"]["queryState"]["Category"]["projections"])
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_visual.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/visual.py
"""Render visuals/<vid>/visual.json."""
from __future__ import annotations

import json

from tableau2pbir.ir.dashboard import Position
from tableau2pbir.ir.sheet import PbirVisual


def render_visual(visual_id: str, pbir_visual: PbirVisual, position: Position, z_order: int) -> str:
    query_state: dict[str, dict] = {}
    for b in pbir_visual.encoding_bindings:
        query_state.setdefault(b.channel, {"projections": []})
        query_state[b.channel]["projections"].append({"field": _field_obj(b.source_field_id)})

    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": pbir_visual.visual_type,
            "query": {"queryState": query_state},
            "objects": pbir_visual.format or {},
        },
    }
    return json.dumps(obj, indent=2)


def _field_obj(source_field_id: str) -> dict:
    if "." in source_field_id:
        table, col = source_field_id.split(".", 1)
        return {"Column": {"Expression": {"SourceRef": {"Source": table}}, "Property": col}}
    return {"Measure": {"Expression": {"SourceRef": {"Source": "Sales"}}, "Property": source_field_id}}
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_visual.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/visual.py tests/unit/emit/pbir/test_visual.py
git commit -m "feat(pbir): render visual.json with position and query state"
```

---

### Task 23: Slicer emitter (filter cards + parameter cards)

**Files:**
- Create: `src/tableau2pbir/emit/pbir/slicer.py`
- Test: `tests/unit/emit/pbir/test_slicer.py`

Filter-card leaf payload carries `field_id` (an IR `Column`). Parameter-card leaf payload carries `parameter_id`; for `numeric_what_if` and `categorical_selector`, the slicer binds to the `<param_name>[Value]` column emitted by Stage 6 Task 15.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_slicer.py
import json

from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.ir.dashboard import Position


def test_filter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_filter_slicer(visual_id="s1", source_field_id="Sales.Region", position=pos, z_order=0)
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Region" in json.dumps(obj)


def test_parameter_slicer_minimal():
    pos = Position(x=0, y=0, w=200, h=80)
    out = render_parameter_slicer(
        visual_id="ps1", parameter_name="Discount Rate", parameter_intent="numeric_what_if",
        position=pos, z_order=0,
    )
    obj = json.loads(out)
    assert obj["visual"]["visualType"] == "slicer"
    assert "Discount Rate" in json.dumps(obj)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_slicer.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/slicer.py
"""Slicer visuals — filter cards and parameter cards."""
from __future__ import annotations

import json

from tableau2pbir.emit.pbir.visual import _field_obj
from tableau2pbir.ir.dashboard import Position


def render_filter_slicer(visual_id: str, source_field_id: str,
                         position: Position, z_order: int) -> str:
    return _slicer_json(visual_id, source_field_id, position, z_order)


def render_parameter_slicer(visual_id: str, parameter_name: str, parameter_intent: str,
                            position: Position, z_order: int) -> str:
    if parameter_intent in ("numeric_what_if", "categorical_selector"):
        source_field_id = f"{parameter_name}.Value"
    else:
        source_field_id = parameter_name
    return _slicer_json(visual_id, source_field_id, position, z_order)


def _slicer_json(visual_id: str, source_field_id: str, position: Position, z_order: int) -> str:
    obj = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json",
        "name": visual_id,
        "position": {"x": position.x, "y": position.y,
                     "width": position.w, "height": position.h, "z": z_order},
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {"projections": [{"field": _field_obj(source_field_id)}]},
                },
            },
            "objects": {},
        },
    }
    return json.dumps(obj, indent=2)
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_slicer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/slicer.py tests/unit/emit/pbir/test_slicer.py
git commit -m "feat(pbir): render slicer visuals for filter and parameter cards"
```

---

### Task 24: Workbook + page filter promotion

**Files:**
- Create: `src/tableau2pbir/emit/pbir/filters.py`
- Test: `tests/unit/emit/pbir/test_filters.py`

A `Filter` that appears on every sheet of every page promotes to a report-level filter (returned separately so `report.json` can carry it). Otherwise it lives on the page's `filterConfig`. v1 walks `Workbook.sheets[*].filters[]` and intersects by `field.column_id` — a column filtered identically across every sheet of every page is "report scope".

For Plan 4 simplicity, this task only handles the page-scope path: collect each dashboard's sheet filters, dedupe by `field.column_id`, and emit them in the page's `filterConfig`. Report-level promotion is a polish item that we can defer if it's not exercised by v1 fixtures.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_filters.py
from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.sheet import Filter


def test_dedupes_filters_across_sheets_of_same_page():
    f1 = Filter(id="f1", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West", "East"))
    f2 = Filter(id="f2", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West", "East"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 1


def test_unique_filters_kept():
    f1 = Filter(id="f1", kind="categorical", field=FieldRef(table_id="Sales", column_id="Region"),
                include=("West",))
    f2 = Filter(id="f2", kind="range", field=FieldRef(table_id="Sales", column_id="Year"))
    out = collect_page_filters([(("s1",), [f1]), (("s2",), [f2])])
    assert len(out) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_filters.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/filters.py
"""Workbook + page filter promotion."""
from __future__ import annotations

from tableau2pbir.ir.sheet import Filter


def collect_page_filters(per_sheet: list[tuple[tuple[str, ...], list[Filter]]]) -> list[dict]:
    seen_keys: set[tuple] = set()
    out: list[dict] = []
    for _sheet_ids, filters in per_sheet:
        for f in filters:
            key = (f.field.table_id, f.field.column_id, f.kind, tuple(f.include), tuple(f.exclude))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            out.append(_filter_to_pbir(f))
    return out


def _filter_to_pbir(f: Filter) -> dict:
    obj: dict = {
        "name": f.id,
        "type": f.kind,
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Source": f.field.table_id}},
                "Property": f.field.column_id,
            },
        },
    }
    if f.kind == "categorical":
        obj["filter"] = {"include": list(f.include), "exclude": list(f.exclude)}
    return obj
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_filters.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/filters.py tests/unit/emit/pbir/test_filters.py
git commit -m "feat(pbir): collect and dedupe page-level filters"
```

---

### Task 25: Action → visualInteractions mapping

**Files:**
- Create: `src/tableau2pbir/emit/pbir/actions.py`
- Test: `tests/unit/emit/pbir/test_actions.py`

Tableau filter / highlight actions map to PBI `visualInteractions`. Per §14: filter action → `type: "filter"`, highlight action → `type: "highlight"`. URL / parameter actions are deferred (URL action is flag-gated to v1.1; parameter action is unsupported when it cascades). For Plan 4 we emit `filter` and `highlight` only.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_actions.py
from tableau2pbir.emit.pbir.actions import render_visual_interactions
from tableau2pbir.ir.dashboard import Action, ActionKind, ActionTrigger


def test_filter_action_emits_filter_interaction():
    a = Action(
        id="a1", name="On select", kind=ActionKind.FILTER, trigger=ActionTrigger.SELECT,
        source_sheet_ids=("s1",), target_sheet_ids=("s2",),
    )
    sheet_to_visual = {"s1": "v1", "s2": "v2"}
    out = render_visual_interactions([a], sheet_to_visual)
    assert out == [{"source": "v1", "target": "v2", "type": "filter"}]


def test_highlight_action_emits_highlight_interaction():
    a = Action(
        id="a2", name="On hover", kind=ActionKind.HIGHLIGHT, trigger=ActionTrigger.HOVER,
        source_sheet_ids=("s1",), target_sheet_ids=("s2",),
    )
    sheet_to_visual = {"s1": "v1", "s2": "v2"}
    out = render_visual_interactions([a], sheet_to_visual)
    assert out == [{"source": "v1", "target": "v2", "type": "highlight"}]


def test_url_action_skipped_in_v1():
    a = Action(
        id="a3", name="Go", kind=ActionKind.URL, trigger=ActionTrigger.MENU,
        source_sheet_ids=("s1",), target_sheet_ids=(),
    )
    out = render_visual_interactions([a], {"s1": "v1"})
    assert out == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_actions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/actions.py
"""Action → visualInteractions."""
from __future__ import annotations

from tableau2pbir.ir.dashboard import Action, ActionKind


def render_visual_interactions(actions: list[Action], sheet_to_visual: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.kind not in (ActionKind.FILTER, ActionKind.HIGHLIGHT):
            continue  # URL + PARAMETER deferred
        for src in a.source_sheet_ids:
            for tgt in a.target_sheet_ids:
                if src not in sheet_to_visual or tgt not in sheet_to_visual:
                    continue
                out.append({
                    "source": sheet_to_visual[src],
                    "target": sheet_to_visual[tgt],
                    "type": "filter" if a.kind == ActionKind.FILTER else "highlight",
                })
    return out
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_actions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/actions.py tests/unit/emit/pbir/test_actions.py
git commit -m "feat(pbir): map Tableau filter/highlight actions to visualInteractions"
```

---

### Task 26: Blocked-visuals computation

**Files:**
- Create: `src/tableau2pbir/emit/pbir/blocked.py`
- Test: `tests/unit/emit/pbir/test_blocked.py`

Per §A.4-3 / §6 Stage 7: every rendered-page visual whose backing field traces to a `deferred_feature_*` `unsupported[]` item OR a `connector_tier == 4` datasource → record `{page_id, visual_id, blocked_by: [unsupported.id]}`.

A visual's "backing field" is the `source_field_id` of its first encoding binding (typically the measure or main column). We resolve that to a calculation or column, then to its datasource via the table.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/emit/pbir/test_blocked.py
from tableau2pbir.emit.pbir.blocked import compute_blocked_visuals
from tableau2pbir.ir.common import UnsupportedItem


def test_visual_backed_by_deferred_calc_is_blocked():
    rendered = [{
        "page_id": "p1", "visual_id": "v1", "sheet_id": "s1",
        "field_ids": ("calc_table_calc_42",),
    }]
    unsupported = (
        UnsupportedItem(
            object_kind="calculation", object_id="calc_table_calc_42",
            source_excerpt="WINDOW_SUM", reason="deferred to v1.1",
            code="deferred_feature_table_calcs",
        ),
    )
    out = compute_blocked_visuals(rendered, unsupported, datasource_tier_by_field={})
    assert out == [{"page_id": "p1", "visual_id": "v1", "blocked_by": ["calc_table_calc_42"]}]


def test_visual_backed_by_tier4_is_blocked():
    rendered = [{
        "page_id": "p1", "visual_id": "v1", "sheet_id": "s1",
        "field_ids": ("col_xyz",),
    }]
    out = compute_blocked_visuals(rendered, (), datasource_tier_by_field={"col_xyz": 4})
    assert out == [{"page_id": "p1", "visual_id": "v1", "blocked_by": ["tier4_datasource"]}]


def test_clean_visual_not_blocked():
    rendered = [{"page_id": "p1", "visual_id": "v1", "sheet_id": "s1", "field_ids": ("col_a",)}]
    out = compute_blocked_visuals(rendered, (), datasource_tier_by_field={"col_a": 1})
    assert out == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_blocked.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/tableau2pbir/emit/pbir/blocked.py
"""Compute blocked_visuals[] per §A.4-3."""
from __future__ import annotations

from tableau2pbir.ir.common import UnsupportedItem


def compute_blocked_visuals(
    rendered: list[dict],
    unsupported: tuple[UnsupportedItem, ...],
    datasource_tier_by_field: dict[str, int],
) -> list[dict]:
    deferred_ids = {
        u.object_id for u in unsupported
        if (u.code or "").startswith("deferred_feature_")
    }
    out: list[dict] = []
    for v in rendered:
        blockers: list[str] = []
        for fid in v.get("field_ids", ()):
            if fid in deferred_ids:
                blockers.append(fid)
            elif datasource_tier_by_field.get(fid) == 4:
                blockers.append("tier4_datasource")
        if blockers:
            out.append({
                "page_id": v["page_id"], "visual_id": v["visual_id"],
                "blocked_by": blockers,
            })
    return out
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/emit/pbir/test_blocked.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/blocked.py tests/unit/emit/pbir/test_blocked.py
git commit -m "feat(pbir): compute blocked_visuals[] for deferred/Tier-4 backing fields"
```

---

### Task 27: PBIR render orchestrator (`render_report`) + Stage 7 runner

**Files:**
- Create: `src/tableau2pbir/emit/pbir/render.py`
- Create: `src/tableau2pbir/emit/pbir/summary.py`
- Modify: `src/tableau2pbir/stages/s07_build_pbir.py`
- Test: `tests/unit/emit/pbir/test_render.py`, `tests/unit/stages/test_s07_build_pbir.py`

The orchestrator walks `Workbook.dashboards`, resolves each `Leaf` per Stage 5's already-populated `position`, dispatches by leaf kind (using `layout.leaf_types.map_leaf_kind`), writes the page + visual files, computes filters and visualInteractions, computes `blocked_visuals[]`, and returns a manifest.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/emit/pbir/test_render.py
from pathlib import Path

from tableau2pbir.emit.pbir.render import render_report
from tableau2pbir.ir.common import FieldRef
from tableau2pbir.ir.dashboard import (
    Container, ContainerKind, Dashboard, DashboardSize, Leaf, LeafKind, Position,
)
from tableau2pbir.ir.datasource import ConnectorTier, Datasource
from tableau2pbir.ir.model import Column, ColumnKind, ColumnRole, Table
from tableau2pbir.ir.sheet import EncodingBinding, Encoding, PbirVisual, Sheet
from tableau2pbir.ir.workbook import DataModel, Workbook


def _wb_one_page_one_visual() -> Workbook:
    sheet = Sheet(
        id="s1", name="Bars", datasource_refs=("d1",), mark_type="bar",
        encoding=Encoding(), filters=(), sort=(), dual_axis=False, reference_lines=(),
        uses_calculations=(),
        pbir_visual=PbirVisual(
            visual_type="clusteredBarChart",
            encoding_bindings=(
                EncodingBinding(channel="Category", source_field_id="Sales.Region"),
                EncodingBinding(channel="Y", source_field_id="Total Sales"),
            ),
        ),
    )
    leaf = Leaf(kind=LeafKind.SHEET, payload={"sheet_id": "s1"},
                position=Position(x=0, y=0, w=1280, h=720))
    dash = Dashboard(
        id="d1", name="Page 1",
        size=DashboardSize(w=1280, h=720, kind="exact"),
        layout_tree=Container(kind=ContainerKind.H, children=(leaf,)),
    )
    ds = Datasource(
        id="d1", name="DS", tableau_kind="csv", connector_tier=ConnectorTier.TIER_1,
        pbi_m_connector="Csv.Document", connection_params={"filename": "C:/x.csv"},
        user_action_required=(), table_ids=("t1",), extract_ignored=False,
    )
    table = Table(id="t1", name="Sales", datasource_id="d1", column_ids=("c1",))
    col = Column(id="c1", name="Region", datatype="string", role=ColumnRole.DIMENSION, kind=ColumnKind.RAW)
    return Workbook(
        ir_schema_version="1.1.0", source_path="x.twb", source_hash="a",
        tableau_version="2024.1", config={},
        data_model=DataModel(datasources=(ds,), tables=(table,)),
        sheets=(sheet,), dashboards=(dash,), unsupported=(),
    )


def test_render_writes_page_and_visual(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    manifest = render_report(wb, tmp_path)
    rd = tmp_path / "Report" / "definition"
    assert (rd / "report.json").is_file()
    pages = list((rd / "pages").iterdir())
    assert len(pages) == 1
    visuals = list((pages[0] / "visuals").iterdir())
    assert len(visuals) == 1
    assert (visuals[0] / "visual.json").is_file()
    assert manifest["counts"]["pages"] == 1
    assert manifest["counts"]["visuals"] == 1
    assert manifest["blocked_visuals"] == []
```

```python
# tests/unit/stages/test_s07_build_pbir.py
from pathlib import Path

# Reuse the workbook helper from emit/pbir/test_render.py — for clarity, replicate inline.
from tests.unit.emit.pbir.test_render import _wb_one_page_one_visual  # type: ignore
from tableau2pbir.pipeline import StageContext
from tableau2pbir.stages import s07_build_pbir


def test_stage7_runner_writes_files_and_returns_manifest(tmp_path: Path):
    wb = _wb_one_page_one_visual()
    ctx = StageContext(workbook_id="wb", output_dir=tmp_path, config={}, stage_number=7)
    result = s07_build_pbir.run(wb.model_dump(mode="json"), ctx)
    assert (tmp_path / "Report" / "definition" / "report.json").is_file()
    assert result.output["counts"]["pages"] == 1
    assert "Stage 7" in result.summary_md
    assert "blocked_visuals" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/unit/emit/pbir/test_render.py tests/unit/stages/test_s07_build_pbir.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement orchestrator + summary + runner**

```python
# src/tableau2pbir/emit/pbir/render.py
"""Stage 7 orchestrator. §6 Stage 7."""
from __future__ import annotations

from pathlib import Path

from tableau2pbir.emit._io import write_text
from tableau2pbir.emit.pbir.actions import render_visual_interactions
from tableau2pbir.emit.pbir.blocked import compute_blocked_visuals
from tableau2pbir.emit.pbir.filters import collect_page_filters
from tableau2pbir.emit.pbir.ids import stable_id
from tableau2pbir.emit.pbir.page import render_page
from tableau2pbir.emit.pbir.report import render_report as render_report_json
from tableau2pbir.emit.pbir.slicer import render_filter_slicer, render_parameter_slicer
from tableau2pbir.emit.pbir.visual import render_visual
from tableau2pbir.ir.dashboard import Container, Leaf, LeafKind
from tableau2pbir.ir.datasource import ConnectorTier
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.layout.leaf_types import PbiObjectKind, map_leaf_kind


def render_report(wb: Workbook, out_dir: Path) -> dict:
    rd = out_dir / "Report" / "definition"
    sheet_by_id = {s.id: s for s in wb.sheets}
    parameter_by_id = {p.id: p for p in wb.data_model.parameters}
    column_to_tier: dict[str, int] = _column_tier_index(wb)

    page_ids: list[str] = []
    rendered_visuals: list[dict] = []
    sheet_to_visual: dict[str, str] = {}
    visual_count = 0
    slicer_count = 0

    for ordinal, dash in enumerate(wb.dashboards):
        page_id = stable_id("page", dash.id)
        page_ids.append(page_id)
        page_dir = rd / "pages" / page_id

        leaves = list(_iter_leaves(dash.layout_tree))
        per_sheet_filters: list[tuple[tuple[str, ...], list]] = []

        for z, leaf in enumerate(leaves):
            if leaf.position is None or leaf.position.w == 0 or leaf.position.h == 0:
                continue
            obj_kind = map_leaf_kind(leaf.kind)
            if obj_kind == PbiObjectKind.DROP:
                continue

            visual_id = stable_id("visual", page_id, str(z))
            v_dir = page_dir / "visuals" / visual_id

            if obj_kind == PbiObjectKind.VISUAL:
                sheet_id = leaf.payload.get("sheet_id")
                sheet = sheet_by_id.get(sheet_id)
                if sheet is None or sheet.pbir_visual is None:
                    continue
                write_text(v_dir / "visual.json",
                           render_visual(visual_id, sheet.pbir_visual, leaf.position, z))
                sheet_to_visual[sheet.id] = visual_id
                field_ids = tuple(b.source_field_id for b in sheet.pbir_visual.encoding_bindings)
                rendered_visuals.append({
                    "page_id": page_id, "visual_id": visual_id, "sheet_id": sheet.id,
                    "field_ids": field_ids,
                })
                per_sheet_filters.append(((sheet.id,), list(sheet.filters)))
                visual_count += 1

            elif obj_kind == PbiObjectKind.SLICER_FILTER:
                source_field_id = leaf.payload.get("field_id", "")
                write_text(v_dir / "visual.json",
                           render_filter_slicer(visual_id, source_field_id, leaf.position, z))
                slicer_count += 1

            elif obj_kind == PbiObjectKind.SLICER_PARAMETER:
                pid = leaf.payload.get("parameter_id", "")
                p = parameter_by_id.get(pid)
                if p is None:
                    continue
                write_text(v_dir / "visual.json",
                           render_parameter_slicer(visual_id, p.name, p.intent.value,
                                                   leaf.position, z))
                slicer_count += 1
            # TEXTBOX / IMAGE / NAV_BUTTON / PLACEHOLDER / LEGEND_SUPPRESS — v1 skips emission

        page_filters = collect_page_filters(per_sheet_filters)
        write_text(page_dir / "page.json",
                   render_page(page_id, dash.name, ordinal,
                               width=dash.size.w or 1280, height=dash.size.h or 720,
                               filters=page_filters))

        # actions for this page
        # (deferred: visualInteractions output isn't a separate file in this minimal v1
        #  emission; it stays in the manifest for Stage 8 / human inspection.)

    write_text(rd / "report.json",
               render_report_json(report_name=Path(wb.source_path).stem, page_order=page_ids))

    interactions: list[dict] = []
    for dash in wb.dashboards:
        interactions.extend(render_visual_interactions(list(dash.actions), sheet_to_visual))

    blocked = compute_blocked_visuals(rendered_visuals, wb.unsupported, column_to_tier)

    return {
        "counts": {
            "pages": len(page_ids),
            "visuals": visual_count,
            "slicers": slicer_count,
        },
        "blocked_visuals": blocked,
        "visual_interactions": interactions,
    }


def _iter_leaves(node):
    if isinstance(node, Leaf):
        yield node
        return
    if isinstance(node, Container):
        for c in node.children:
            yield from _iter_leaves(c)


def _column_tier_index(wb: Workbook) -> dict[str, int]:
    """Map every IR column id (and 'Table.Column' tag) → backing datasource connector_tier."""
    out: dict[str, int] = {}
    ds_by_id = {d.id: d for d in wb.data_model.datasources}
    for t in wb.data_model.tables:
        ds = ds_by_id.get(t.datasource_id)
        if ds is None:
            continue
        tier = int(ds.connector_tier)
        for col_id in t.column_ids:
            out[col_id] = tier
            out[f"{t.name}.{col_id}"] = tier
    return out
```

```python
# src/tableau2pbir/emit/pbir/summary.py
"""Stage 7 summary.md."""
from __future__ import annotations


def render_summary(manifest: dict) -> str:
    c = manifest.get("counts", {})
    blocked = manifest.get("blocked_visuals", [])
    inter = manifest.get("visual_interactions", [])
    return (
        "# Stage 7 — build report PBIR\n\n"
        f"- pages: {c.get('pages', 0)}\n"
        f"- visuals: {c.get('visuals', 0)}\n"
        f"- slicers: {c.get('slicers', 0)}\n"
        f"- visual_interactions: {len(inter)}\n"
        f"- blocked_visuals: {len(blocked)}\n"
    )
```

```python
# src/tableau2pbir/stages/s07_build_pbir.py
"""Stage 7 — build report PBIR (pure python). §6 Stage 7."""
from __future__ import annotations

from typing import Any

from tableau2pbir.emit.pbir.render import render_report
from tableau2pbir.emit.pbir.summary import render_summary
from tableau2pbir.ir.workbook import Workbook
from tableau2pbir.pipeline import StageContext, StageResult


def run(input_json: dict[str, Any], ctx: StageContext) -> StageResult:
    wb = Workbook.model_validate(input_json)
    manifest = render_report(wb, ctx.output_dir)
    return StageResult(
        output=manifest,
        summary_md=render_summary(manifest),
        errors=(),
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/emit/pbir/test_render.py tests/unit/stages/test_s07_build_pbir.py -v`
Expected: PASS.

Then run the broader suite:

Run: `pytest tests/ -v -x`
Expected: ALL GREEN.

- [ ] **Step 5: Commit**

```bash
git add src/tableau2pbir/emit/pbir/render.py src/tableau2pbir/emit/pbir/summary.py src/tableau2pbir/stages/s07_build_pbir.py tests/unit/emit/pbir/test_render.py tests/unit/stages/test_s07_build_pbir.py
git commit -m "feat(stage7): replace stub with PBIR emission orchestrator"
```

---

### Task 28: Stage 7 contract test (PBIR JSON well-formedness)

**Files:**
- Create: `tests/contract/test_stage7_pbir_contract.py`

Plan 4 cannot run `pbi-tools compile` (Plan 5). The contract test verifies: (a) every emitted JSON is valid JSON, (b) `report.json` carries `pages.pageOrder` matching the page directories on disk, (c) every `visual.json` has `name`, `position`, `visual.visualType`, (d) `manifest['blocked_visuals']` is a list of well-formed records.

- [ ] **Step 1: Write the test**

```python
# tests/contract/test_stage7_pbir_contract.py
import json
from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, run_stage


@pytest.mark.parametrize("fixture", ["dashboard_tiled_floating", "visual_marks_v1", "params_all_intents"])
def test_stage7_emits_valid_json(synthetic_fixtures_dir: Path, tmp_path: Path,
                                  snapshot_replay_env, fixture: str):
    ctx = StageContext(workbook_id=fixture, output_dir=tmp_path, config={}, stage_number=1)
    result = run_stage("extract", {"path": str(synthetic_fixtures_dir / f"{fixture}.twb")}, ctx)
    for stage in ("canonicalize", "translate_calcs", "map_visuals",
                  "compute_layout", "build_tmdl", "build_pbir"):
        result = run_stage(stage, result.output, ctx.model_copy(update={"stage_number": ctx.stage_number + 1}))

    rd = tmp_path / "Report" / "definition"
    report = json.loads((rd / "report.json").read_text(encoding="utf-8"))
    page_order = report["pages"]["pageOrder"]
    pages_on_disk = {p.name for p in (rd / "pages").iterdir() if p.is_dir()} if (rd / "pages").is_dir() else set()
    assert set(page_order) == pages_on_disk

    for page_dir in (rd / "pages").iterdir() if (rd / "pages").is_dir() else []:
        if not (page_dir / "visuals").is_dir():
            continue
        for v_dir in (page_dir / "visuals").iterdir():
            obj = json.loads((v_dir / "visual.json").read_text(encoding="utf-8"))
            assert "name" in obj
            assert "position" in obj
            assert obj["visual"]["visualType"]

    assert isinstance(result.output["blocked_visuals"], list)
```

- [ ] **Step 2: Run test**

Run: `pytest tests/contract/test_stage7_pbir_contract.py -v`
Expected: PASS (or report a precise gap in the orchestrator if a fixture exposes a path the tests didn't cover — fix forward in this task before commit).

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_stage7_pbir_contract.py
git commit -m "test(contract): stage 7 emits valid JSON + page-order matches disk"
```

---

## Final integration (Task 29)

### Task 29: End-to-end Stage 5+6+7 integration test on synthetic fixtures

**Files:**
- Create: `tests/integration/test_stage5_6_7_integration.py`

Confirms: pipeline runs through all stages, all artifacts land at the documented paths in §4.4, and `manifest['blocked_visuals']` has the expected emptiness on a clean v1 fixture.

- [ ] **Step 1: Write the test**

```python
# tests/integration/test_stage5_6_7_integration.py
import json
from pathlib import Path

import pytest

from tableau2pbir.pipeline import StageContext, run_stage


@pytest.mark.parametrize("fixture", [
    "trivial",
    "visual_marks_v1",
    "dashboard_tiled_floating",
    "params_all_intents",
    "datasources_mixed",
])
def test_full_v1_pipeline_through_stage7(synthetic_fixtures_dir: Path, tmp_path: Path,
                                          snapshot_replay_env, fixture: str):
    ctx = StageContext(workbook_id=fixture, output_dir=tmp_path, config={}, stage_number=1)
    result = run_stage("extract", {"path": str(synthetic_fixtures_dir / f"{fixture}.twb")}, ctx)
    for stage in ("canonicalize", "translate_calcs", "map_visuals",
                  "compute_layout", "build_tmdl", "build_pbir"):
        result = run_stage(stage, result.output, ctx.model_copy(update={"stage_number": ctx.stage_number + 1}))

    # SemanticModel artifacts present
    sm = tmp_path / "SemanticModel"
    assert (sm / "database.tmdl").is_file()
    assert (sm / "model.tmdl").is_file()

    # Report artifacts present
    rd = tmp_path / "Report" / "definition"
    assert (rd / "report.json").is_file()
    report = json.loads((rd / "report.json").read_text(encoding="utf-8"))
    assert "pages" in report
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_stage5_6_7_integration.py -v`
Expected: PASS for all five v1 fixtures.

If a fixture fails because it exercises a v1-deferred path, mark it skipped with a clear message OR open a follow-up bug — do NOT silently broaden the scope of Plan 4 to fix it.

Then run the entire suite end-to-end:

Run: `pytest tests/ -v`
Expected: ALL GREEN. No new skips beyond pre-existing deferred fixtures.

- [ ] **Step 3: Update `CLAUDE.md` to mark Plan 4 complete**

Edit `CLAUDE.md`:
- Change Plan 4 row's status from `🔲 NEXT` to `✅ DONE` and fill in the `File` column with this plan's path.
- Change Plan 5 row's status from `🔲 TODO` to `🔲 NEXT`.
- Update the "Plan 4 is next:" paragraph at the bottom to read "Plan 5 is next:" with a one-line description (Stage 8: package, validate, Desktop-open gate).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_stage5_6_7_integration.py CLAUDE.md
git commit -m "test(integration): stage 5+6+7 end-to-end on v1 synthetic fixtures; mark plan 4 done"
```

---

## Self-review checklist (run after Task 29)

1. **Spec coverage:**
   - §6 Stage 5 (canvas, walker, leaf-type map, clamp, summary): Tasks 1–6, 7.
   - §6 Stage 6 (database/model TMDL, table/column/measure/relationship, M, parameters): Tasks 8–18.
   - §6 Stage 7 (report.json, pages, visuals, slicers, filters, actions, blocked_visuals): Tasks 19–28.
   - §A.4-3 `blocked_visuals[]` on Stage 7 manifest: Task 26 + Task 27 (manifest assembly).
   - §5.7 parameter emission per intent: Task 15.
   - §5.8 connector tier → M: Task 12.
   - §16 v1 cut: respected in every emit module (deferred kinds skipped, intents skipped).

2. **Placeholders:** none — every step shows real code or a real command.

3. **Type consistency:**
   - `Position` used identically across Tasks 2, 3, 6, 22, 23.
   - `PbiObjectKind` enum members used the same in `leaf_types.py` and `render.py` (Task 27).
   - `manifest['counts']` shape consistent across Tasks 16/17 (TMDL) and 27 (PBIR).
   - `Sheet.pbir_visual` — read-only consumer in Task 27; produced by Plan 3.
   - `StageResult.output` — Stage 5 returns IR-shaped dict (round-trips through `Workbook`); Stages 6 + 7 return manifest dicts (NOT IR). Stage 8 in Plan 5 must read from manifests, not re-derive.

4. **Files-touched matrix:**
   - All new modules under `src/tableau2pbir/layout/` and `src/tableau2pbir/emit/`.
   - Three stage files modified (`s05_compute_layout.py`, `s06_build_tmdl.py`, `s07_build_pbir.py`).
   - One settings file modified (`CLAUDE.md`).
   - No IR module modified. No prompt module modified. No new runtime dependency.

---

## Execution handoff

**Execution mode: Inline (chosen 2026-04-29).** Execute tasks in-session using
`superpowers:executing-plans`, with checkpoint review at the end of each stage
boundary (after Task 7, after Task 18, after Task 28, after Task 29).

Do NOT dispatch subagents per task — this plan is run inline. If the executing
session is interrupted, the next session resumes by reading this file and the
last completed checkbox `- [x]`.
