from harness import import_plugin_module

sizes = import_plugin_module("sizes")


def test_defaults_line_and_area_are_wide_others_a_third():
    assert sizes.size({"type": "area"}) == (2, "m")
    assert sizes.size({"type": "line"}) == (2, "m")
    assert sizes.size({"type": "bar"}) == (1, "m")


def test_saved_size_wins_and_bad_values_fall_back():
    assert sizes.size({"type": "bar", "w": 3, "h": "l"}) == (3, "l")
    assert sizes.size({"type": "bar", "w": 7, "h": "huge"}) == (1, "m")


def test_cycles():
    assert [sizes.next_width(w) for w in (1, 2, 3)] == [2, 3, 1]
    assert sizes.next_height("m") == "l" and sizes.next_height("l") == "m"


def test_apply_writes_only_changed_charts_and_copies():
    charts = [{"id": "a", "type": "bar"}, {"id": "b", "type": "pie"}]
    out = sizes.apply(charts, {"b": (3, "l")})
    assert out == [{"id": "a", "type": "bar"}, {"id": "b", "type": "pie", "w": 3, "h": "l"}]
    assert "w" not in charts[1]
