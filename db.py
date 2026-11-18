"""Database side of the dashboard: no NiceGUI here, so it is easy to test.

Charts are plain dicts: {id, title, table, type, x, agg, y, limit}. Table and column names are
checked against the live schema before a query is built, and queries are built with SQLAlchemy
expressions, never by pasting text into SQL.
"""
import random
from pathlib import Path

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, create_engine, func, inspect,
                        select)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import Date, DateTime, Numeric

CHART_TYPES = ["bar", "line", "area", "pie", "scatter"]
AGGS = ["count", "sum", "avg", "min", "max"]
_engines: dict[str, Engine] = {}


class ChartError(Exception):
    """`key` is a locale key of this plugin, shown to the user."""

    def __init__(self, key: str, **vars):
        super().__init__(key)
        self.key, self.vars = key, vars


def engine(url: str) -> Engine:
    if url not in _engines:
        try:
            _engines[url] = create_engine(url, pool_pre_ping=True)
        except (SQLAlchemyError, ValueError, ImportError) as e:
            raise ChartError("err.url", detail=str(e)) from None
    return _engines[url]


def forget(url: str) -> None:
    if eng := _engines.pop(url, None):
        eng.dispose()


def masked(url: str) -> str:
    try:
        return engine(url).url.render_as_string(hide_password=True)
    except ChartError:
        return url


def _kind(sqltype) -> str:
    if isinstance(sqltype, (Integer, Float, Numeric)):
        return "number"
    return "date" if isinstance(sqltype, (Date, DateTime)) else "text"


def schema(url: str) -> dict[str, dict[str, str]]:
    """{table: {column: "number" | "text" | "date"}}"""
    try:
        insp = inspect(engine(url))
        return {t: {c["name"]: _kind(c["type"]) for c in insp.get_columns(t)} for t in sorted(insp.get_table_names())}
    except SQLAlchemyError as e:
        raise ChartError("err.connect", detail=str(e).splitlines()[0]) from None


def validate(chart: dict, tables: dict[str, dict[str, str]]) -> None:
    cols = tables.get(chart.get("table"))
    if cols is None:
        raise ChartError("err.table", table=chart.get("table"))
    if chart.get("type") not in CHART_TYPES:
        raise ChartError("err.type", type=chart.get("type"))
    if chart.get("x") not in cols:
        raise ChartError("err.column", column=chart.get("x"))
    if chart["type"] == "scatter" or chart.get("agg") != "count":
        if chart.get("agg") not in AGGS and chart["type"] != "scatter":
            raise ChartError("err.agg", agg=chart.get("agg"))
        if cols.get(chart.get("y")) != "number":
            raise ChartError("err.y_number", column=chart.get("y"))


def rows(url: str, chart: dict) -> list[tuple]:
    """(x, y) pairs for a chart. Blocking: call it with run.io_bound from the UI."""
    validate(chart, tables := schema(url))
    table = Table(chart["table"], MetaData(), *(Column(c) for c in tables[chart["table"]]))
    x = table.c[chart["x"]]
    limit = max(1, min(int(chart.get("limit") or 50), 1000))
    if chart["type"] == "scatter":
        stmt = select(x, table.c[chart["y"]]).limit(limit)
    else:
        y = func.count() if chart["agg"] == "count" else getattr(func, chart["agg"])(table.c[chart["y"]])
        stmt = select(x, y).group_by(x).order_by(x).limit(limit)
    try:
        with engine(url).connect() as conn:
            return [(r[0], float(r[1]) if r[1] is not None else None) for r in conn.execute(stmt)]
    except SQLAlchemyError as e:
        raise ChartError("err.query", detail=str(e).splitlines()[0]) from None


# Colours come from the theme's CSS variables at draw time (keys starting with ":" are JavaScript),
# so charts follow light/dark mode and any other theme plugin.
CSS_VAR = "getComputedStyle(document.body).getPropertyValue('{}').trim()"
PALETTE = "[" + ", ".join(CSS_VAR.format(f"--ngui-chart-{i}") for i in range(1, 7)) + "]"
GRID_LINE = {"lineStyle": {":color": CSS_VAR.format("--ngui-chart-grid")}}
AXIS = {"axisLine": {"show": False}, "axisTick": {"show": False}, "axisLabel": {"fontSize": 11}}


def option(chart: dict, data: list[tuple]) -> dict:
    """ECharts option for a chart and its (x, y) rows."""
    base = {":color": PALETTE, "animation": False,
            "tooltip": {"trigger": "item" if chart["type"] in ("pie", "scatter") else "axis"},
            "grid": {"left": 4, "right": 12, "top": 12, "bottom": 4, "containLabel": True}}
    if chart["type"] == "pie":
        return {**base, "legend": {"bottom": 0, "type": "scroll", "icon": "roundRect", "itemWidth": 10, "itemHeight": 10,
                                   "textStyle": {"fontSize": 11}},
                "series": [{"type": "pie", "radius": ["48%", "70%"], "center": ["50%", "45%"],
                            "itemStyle": {"borderWidth": 2, ":borderColor": CSS_VAR.format("--ngui-surface")},
                            "label": {"show": False},
                            "data": [{"name": str(x), "value": y} for x, y in data]}]}
    value_axis = {"type": "value", "splitLine": GRID_LINE, **AXIS}
    if chart["type"] == "scatter":
        return {**base, "xAxis": {**value_axis, "scale": True}, "yAxis": {**value_axis, "scale": True},
                "series": [{"type": "scatter", "symbolSize": 7, "data": [[x, y] for x, y in data]}]}
    series = {"type": "line" if chart["type"] == "area" else chart["type"], "data": [y for _, y in data]}
    if chart["type"] == "bar":
        series.update(barMaxWidth=28, itemStyle={"borderRadius": [4, 4, 0, 0]})
    else:
        series.update(smooth=True, symbol="circle", symbolSize=5, lineStyle={"width": 2})
    if chart["type"] == "area":
        series["areaStyle"] = {"opacity": 0.15}
    return {**base, "xAxis": {"type": "category", "data": [str(x) for x, _ in data], **AXIS},
            "yAxis": value_axis, "series": [series]}


def source_name(url: str) -> str:
    """Short database name for the summary card: SQLite, PostgreSQL, ..."""
    try:
        backend = engine(url).url.get_backend_name()
    except ChartError:
        return "?"
    return {"postgresql": "PostgreSQL", "sqlite": "SQLite", "mysql": "MySQL"}.get(backend, backend)


def demo_url(data_dir: Path) -> str:
    """A SQLite demo database in the plugin's folder, created with sample data on first use."""
    path = data_dir / "demo.sqlite3"
    url = f"sqlite:///{path}"
    if not path.exists():
        _seed(engine(url))
    return url


def _seed(eng: Engine) -> None:
    md, rnd = MetaData(), random.Random(42)
    sales = Table("sales", md, Column("id", Integer, primary_key=True), Column("month", String),
                  Column("region", String), Column("product", String), Column("units", Integer),
                  Column("revenue", Float))
    tickets = Table("tickets", md, Column("id", Integer, primary_key=True), Column("month", String),
                    Column("priority", String), Column("status", String), Column("hours", Float))
    md.create_all(eng)
    months = [f"2026-{m:02d}" for m in range(1, 13)]
    sale_rows = [{"month": m, "region": r, "product": p, "units": (u := rnd.randint(20, 120) + i * 4),
                  "revenue": round(u * price * rnd.uniform(0.9, 1.1), 2)}
                 for i, m in enumerate(months) for r in ("Marmara", "Ege", "İç Anadolu", "Akdeniz")
                 for p, price in (("Basic", 49.0), ("Pro", 149.0), ("Team", 399.0))]
    ticket_rows = [{"month": rnd.choice(months), "priority": rnd.choice(["low", "medium", "high", "urgent"]),
                    "status": rnd.choice(["open", "closed", "closed", "closed"]),
                    "hours": round(rnd.expovariate(1 / 18), 1)} for _ in range(300)]
    with eng.begin() as conn:
        conn.execute(sales.insert(), sale_rows)
        conn.execute(tickets.insert(), ticket_rows)
