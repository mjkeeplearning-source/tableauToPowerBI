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
