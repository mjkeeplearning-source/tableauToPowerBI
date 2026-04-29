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
