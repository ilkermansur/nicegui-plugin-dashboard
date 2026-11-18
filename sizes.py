"""Chart sizes on the dashboard grid. No NiceGUI here, so it is easy to test.

Width is a column span on a 3-column grid (1 = a third, 2 = two thirds, 3 = full width);
height is "m" (normal) or "l" (tall). Charts saved before sizes existed get a default.
"""

WIDTHS = (1, 2, 3)
HEIGHTS = ("m", "l")


def size(chart: dict) -> tuple[int, str]:
    default_w = 2 if chart.get("type") in ("line", "area") else 1
    w = chart.get("w") if chart.get("w") in WIDTHS else default_w
    h = chart.get("h") if chart.get("h") in HEIGHTS else "m"
    return w, h


def next_width(w: int) -> int:
    return WIDTHS[(WIDTHS.index(w) + 1) % len(WIDTHS)] if w in WIDTHS else WIDTHS[0]


def next_height(h: str) -> str:
    return HEIGHTS[(HEIGHTS.index(h) + 1) % len(HEIGHTS)] if h in HEIGHTS else HEIGHTS[0]


def apply(charts: list[dict], sizes: dict[str, tuple[int, str]]) -> list[dict]:
    """Charts with the sizes chosen in edit mode written into them; the given list is not changed."""
    return [{**c, "w": sizes[c["id"]][0], "h": sizes[c["id"]][1]} if c["id"] in sizes else c for c in charts]
