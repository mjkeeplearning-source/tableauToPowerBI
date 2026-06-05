from __future__ import annotations

from tableau2pbir.stages._build_sheets import build_sheets


def test_basic_sheet():
    raw = [{
        "name": "Revenue",
        "datasource_refs": ("sample.csv",),
        "mark_type": "Bar",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, qtc_items = build_sheets(raw, calc_names=set(), table_id_for_ref={"sample.csv": "tbl__sample_csv"})
    assert len(sheets) == 1
    s = sheets[0]
    assert s.name == "Revenue"
    assert s.mark_type == "Bar"
    assert len(s.encoding.rows) == 1
    assert s.encoding.rows[0].column_id == "amount"
    assert s.uses_calculations == ()
    assert qtc_items == ()


def test_sheet_uses_calculations_back_ref():
    raw = [{
        "name": "Profit",
        "datasource_refs": ("ds",), "mark_type": "Bar",
        "encodings": {"rows": ("Profit Margin",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names={"Profit Margin"},
                             table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].uses_calculations == ("calc__profit_margin",)


def test_categorical_filter():
    raw = [{
        "name": "f", "datasource_refs": ("ds",), "mark_type": "Bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (),
                      "shape": None, "angle": None},
        "filters": [{"kind": "categorical", "column": "region",
                     "include": ('"West"',), "exclude": (), "expr": None}],
        "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    f = sheets[0].filters[0]
    assert f.kind == "categorical"
    assert f.include == ('"West"',)


def test_datasource_marker_pills_are_filtered_from_encoding():
    """Pills that are class.hash (dot-separated, no colon) must be dropped."""
    raw = [{
        "name": "Sheet 1",
        "datasource_refs": ("fed.ds",),
        "mark_type": "bar",
        "encodings": {
            "rows": ("federated.17kv7r10vp81pc1g60xgp0re1it8", "usr:DeltaOrder:qk"),
            "columns": ("federated.17kv7r10vp81pc1g60xgp0re1it8", "none:category:nk"),
            "color": None, "size": None, "label": None, "tooltip": None,
            "detail": (), "shape": None, "angle": None,
        },
        "filters": [], "sort": [], "dual_axis": False,
        "reference_lines": [], "quick_table_calcs": [],
    }]
    sheets, _ = build_sheets(raw, calc_names=set(), table_id_for_ref={"fed.ds": "tbl__fed"})
    enc = sheets[0].encoding
    col_ids = {fr.column_id for fr in enc.rows} | {fr.column_id for fr in enc.columns}
    assert not any("federated" in cid for cid in col_ids), "marker must be absent"
    assert len(enc.rows) == 1, "only the real field must remain on rows"
    assert len(enc.columns) == 1, "only the real field must remain on columns"


def test_quick_table_calc_surfaces_deferred_item():
    raw = [{
        "name": "Running", "datasource_refs": ("ds",), "mark_type": "Line",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [{"column": "amount", "type": "running_sum", "compute_using": None}],
    }]
    _, qtc_items = build_sheets(raw, calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert len(qtc_items) == 1
    assert qtc_items[0].code == "deferred_feature_table_calcs"
    assert "running_sum" in qtc_items[0].source_excerpt


def _raw(extra=None):
    base = {
        "name": "T", "datasource_refs": ("ds",), "mark_type": "bar",
        "encodings": {"rows": (), "columns": (), "color": None, "size": None,
                      "label": None, "tooltip": None, "detail": (),
                      "shape": None, "angle": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }
    if extra:
        base.update(extra)
    return base


def test_visual_format_none_when_key_absent():
    """Existing raw dicts without sheet_style key must produce Sheet.visual_format=None."""
    sheets, _ = build_sheets([_raw()], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].visual_format is None


def test_visual_format_populated_from_sheet_style():
    """Task 4: sheet_style dict with mark_color/labels_show is converted to VisualFormat."""
    raw = _raw({"sheet_style": {"mark_color": "#e15759", "labels_show": True}})
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    vf = sheets[0].visual_format
    assert vf is not None
    assert vf.mark_color == "#e15759"
    assert vf.labels_show is True


def test_visual_format_none_when_all_defaults():
    """Fix: empty-ish sheet_style dict with all defaults returns None (not a no-op VisualFormat)."""
    raw = _raw({"sheet_style": {"mark_color": None, "labels_show": False}})
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].visual_format is None


def _raw_with_style(style_extra: dict) -> dict:
    """Build a minimal raw worksheet dict with the given sheet_style overrides."""
    return {
        "name": "S", "datasource_refs": ("ds",), "mark_type": "line",
        "encodings": {"rows": ("sum:sales:qk",), "columns": ("yr:order_date:ok",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None, "text": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
        "sheet_style": style_extra,
    }


def test_axis_titles_single_wired_to_visual_format():
    raw = _raw_with_style({
        "axis_titles": [{"field": "sum_sales_qk", "scope": "rows", "title": "#  Revenue"}],
    })
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    vf = sheets[0].visual_format
    assert vf is not None
    assert len(vf.axis_titles) == 1
    assert vf.axis_titles[0].field_id == "sum_sales_qk"
    assert vf.axis_titles[0].scope == "rows"
    assert vf.axis_titles[0].title == "#  Revenue"


def test_axis_titles_multi_measure_order_preserved():
    raw = _raw_with_style({
        "axis_titles": [
            {"field": "sum_profit_qk", "scope": "rows", "title": "#  Profit"},
            {"field": "sum_sales_qk", "scope": "rows", "title": "#  Sales"},
        ],
    })
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    vf = sheets[0].visual_format
    assert vf is not None
    assert len(vf.axis_titles) == 2
    assert vf.axis_titles[0].title == "#  Profit"
    assert vf.axis_titles[1].title == "#  Sales"


def test_axis_titles_absent_produces_no_visual_format():
    """A raw dict with no sheet_style at all → visual_format remains None."""
    raw = {
        "name": "S", "datasource_refs": ("ds",), "mark_type": "bar",
        "encodings": {"rows": ("amount",), "columns": ("month",),
                      "color": None, "size": None, "label": None, "tooltip": None,
                      "detail": (), "shape": None, "angle": None, "text": None},
        "filters": [], "sort": [], "dual_axis": False, "reference_lines": [],
        "quick_table_calcs": [],
    }
    sheets, _ = build_sheets([raw], calc_names=set(), table_id_for_ref={"ds": "tbl__ds"})
    assert sheets[0].visual_format is None
