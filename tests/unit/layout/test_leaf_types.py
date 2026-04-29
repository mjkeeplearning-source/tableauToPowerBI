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
