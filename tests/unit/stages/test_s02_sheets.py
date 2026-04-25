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
