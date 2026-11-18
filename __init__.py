"""Dashboard: charts from database tables, built and edited on screen.

Template notes:
- db.py holds every database call and is tested without a browser; this file is only UI.
- Database calls block, so they run in run.io_bound threads: one slow query never freezes other users.
- Charts are shared by all users (ctx.storage.shared); only users with `dashboard.edit` may change them.
- The demo SQLite database lives in ctx.data_dir; set a real database on the data source dialog
  or with the DASHBOARD_DB_URL environment variable (for example postgresql+psycopg://user:pw@postgres/app).
- Charts use the SVG renderer so their text takes the theme's colour from CSS, in light and dark mode.
"""
import os
import uuid

from nicegui import run, ui

from . import db
from .db import AGGS, CHART_TYPES, ChartError

CSS = """
.ngui-dashboard-kpis, .ngui-dashboard-grid { display: grid; width: 100%; gap: var(--ngui-gap); }
.ngui-dashboard-kpis { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.ngui-dashboard-grid { grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); grid-auto-flow: dense; }
.ngui-dashboard-wide { grid-column: span 2; }
@media (max-width: 900px) { .ngui-dashboard-wide { grid-column: auto; } }
.ngui-dashboard-chart { width: 100%; height: 260px; }
.ngui-dashboard-chart svg text { fill: var(--ngui-muted) !important; stroke: none !important; }
.ngui-dashboard-muted { color: var(--ngui-muted); font-size: 0.875rem; }
.ngui-dashboard-error { color: var(--ngui-danger); font-size: 0.875rem; }
.ngui-dashboard-builder { width: min(960px, 92vw); max-width: none; }
"""


def setup(ctx):
    t = ctx.t
    shared = ctx.storage.shared  # one dashboard for every user
    demo = db.demo_url(ctx.data_dir)
    ui.add_css(CSS, shared=True)

    def db_url() -> str:
        return os.environ.get("DASHBOARD_DB_URL") or shared.get("db_url") or demo

    def default_charts() -> list[dict]:
        def chart(title, table, type_, x, agg, y=None):
            return {"id": uuid.uuid4().hex[:8], "title": t(title), "table": table, "type": type_, "x": x,
                    "agg": agg, "y": y, "limit": 50}
        return [chart("demo.revenue_by_region", "sales", "bar", "region", "sum", "revenue"),
                chart("demo.revenue_by_month", "sales", "area", "month", "sum", "revenue"),
                chart("demo.units_by_product", "sales", "pie", "product", "sum", "units"),
                chart("demo.tickets_by_priority", "tickets", "bar", "priority", "count")]

    @ctx.role("layout").page("/dashboard", lambda: t("title"), icon="insights")
    async def page():
        theme = ctx.role("theme")
        can_edit = ctx.role("auth").has("dashboard.edit")
        url = db_url()
        def header_actions():
            if can_edit:
                ui.button(t("source.title"), icon="storage", on_click=lambda: source_dialog(), color=None).props(
                    "outline")
                ui.button(t("chart.new"), icon="add_chart", on_click=lambda: builder())

        theme.page_header(t("title"), t("description"), actions=header_actions)
        try:
            tables, problem = await run.io_bound(db.schema, url), None
        except ChartError as e:
            tables, problem = {}, t(e.key, **e.vars)
        if shared.get("charts") is None:
            shared.set("charts", default_charts() if url == demo else [])

        def charts() -> list[dict]:
            return shared.get("charts", []) or []

        def store(items: list[dict]) -> None:
            shared.set("charts", items)
            board.refresh()

        # --- summary and toolbar ------------------------------------------------------------
        with ui.element("div").classes("ngui-dashboard-kpis"):
            theme.kpi(t("kpi.charts"), len(charts()), icon="insights")
            theme.kpi(t("kpi.tables"), len(tables), icon="table_chart",
                      delta=t("kpi.rows_hint"), trend=None)
            theme.kpi(t("kpi.source"), db.source_name(url), icon="storage", tone="danger" if problem else "neutral",
                      delta=t("source.demo") if url == demo else db.masked(url).split("@")[-1],
                      trend="down" if problem else None)
        if problem:
            ui.label(problem).classes("ngui-dashboard-error")

        # --- charts ------------------------------------------------------------------------
        async def fill(chart: dict, box) -> None:
            try:
                data = await run.io_bound(db.rows, url, chart)
            except ChartError as e:
                if box.is_deleted:  # the user moved on while the query ran
                    return
                box.clear()
                with box:
                    ui.label(t(e.key, **e.vars)).classes("ngui-dashboard-error")
                return
            if box.is_deleted:
                return
            box.clear()
            with box:
                if data:
                    ui.echart(db.option(chart, data), renderer="svg").classes("ngui-dashboard-chart")
                else:
                    ui.label(t("chart.no_data")).classes("ngui-dashboard-muted")

        @ui.refreshable
        def board():
            items = charts()
            if not items:
                ui.label(t("chart.none")).classes("ngui-dashboard-muted")
                return
            with ui.element("div").classes("ngui-dashboard-grid"):
                for chart in items:
                    def actions(chart=chart):
                        if can_edit:
                            ui.button(icon="edit", on_click=lambda: builder(chart), color=None).props(
                                "flat round dense").tooltip(t("chart.edit"))
                            ui.button(icon="delete", on_click=lambda: confirm_delete(chart), color=None).props(
                                "flat round dense").tooltip(t("chart.delete"))
                    meta = t(f"agg.{chart['agg']}") if chart["type"] != "scatter" and chart.get("agg") else t("type.scatter")
                    wide = " ngui-dashboard-wide" if chart["type"] in ("line", "area") else ""
                    with theme.card(chart["title"], actions=actions, meta=f"{chart['table']} · {meta}").classes(
                            "w-full" + wide):
                        box = ui.column().classes("w-full")
                        with box:
                            ui.spinner()
                        ui.timer(0.01, lambda chart=chart, box=box: fill(chart, box), once=True)

        def confirm_delete(chart: dict):
            with ui.dialog() as dlg, ui.card():
                ui.label(t("chart.confirm_delete", title=chart["title"]))
                with ui.row().classes("w-full justify-end"):
                    ui.button(t("action.cancel"), on_click=dlg.close, color=None).props("flat")
                    ui.button(t("chart.delete"), color="negative",
                              on_click=lambda: (store([c for c in charts() if c["id"] != chart["id"]]), dlg.close()))
            dlg.open()

        # --- chart builder -----------------------------------------------------------------------
        def builder(existing: dict | None = None):
            if not tables:
                ui.notify(problem or t("err.no_tables"), type="warning")
                return
            first = next(iter(tables))
            text_cols = [c for c, k in tables[first].items() if k == "text"]  # a category axis reads best
            draft = dict(existing or {"id": uuid.uuid4().hex[:8], "title": "", "table": first, "type": "bar",
                                      "x": (text_cols or list(tables[first]))[0], "agg": "count", "y": None,
                                      "limit": 50})

            def columns(kind: str | None = None) -> list[str]:
                return [c for c, k in tables.get(draft["table"], {}).items() if kind is None or k == kind]

            def sync():
                x_sel.set_options(columns(), value=draft["x"] if draft["x"] in columns() else columns()[0])
                numbers = columns("number")
                y_sel.set_options(numbers, value=draft["y"] if draft["y"] in numbers else (numbers or [None])[0])
                agg_sel.set_visibility(draft["type"] != "scatter")
                y_sel.set_visibility(draft["type"] == "scatter" or draft["agg"] != "count")
                preview.refresh()

            @ui.refreshable
            def preview():
                box = ui.column().classes("w-full")
                try:
                    db.validate(draft, tables)
                except ChartError as e:
                    with box:
                        ui.label(t(e.key, **e.vars)).classes("ngui-dashboard-muted")
                    return
                with box:
                    ui.spinner()
                ui.timer(0.01, lambda: fill(dict(draft), box), once=True)

            def save():
                try:
                    db.validate(draft, tables)
                except ChartError as e:
                    ui.notify(t(e.key, **e.vars), type="warning")
                    return
                draft["title"] = draft["title"].strip() or f"{draft['table']} · {draft['x']}"
                items = charts()
                index = next((i for i, c in enumerate(items) if c["id"] == draft["id"]), None)
                if index is None:
                    items.append(dict(draft))
                else:
                    items[index] = dict(draft)
                store(items)
                dlg.close()

            built = []  # sync only once every field exists; bindings fire change events while building
            on = lambda _: built and sync()  # noqa: E731
            with ui.dialog() as dlg, ui.card().classes("ngui-dashboard-builder"):
                ui.label(t("chart.edit" if existing else "chart.new")).classes("ngui-card-title")
                with ui.row().classes("w-full no-wrap items-start gap-6"):
                    with ui.column().classes("w-72 gap-2"):
                        ui.input(t("field.title")).bind_value(draft, "title").props("dense outlined").classes("w-full")
                        ui.select(list(tables), label=t("field.table"), on_change=on).bind_value(
                            draft, "table").props("dense outlined").classes("w-full")
                        ui.select({k: t(f"type.{k}") for k in CHART_TYPES}, label=t("field.type"),
                                  on_change=on).bind_value(draft, "type").props("dense outlined").classes("w-full")
                        x_sel = ui.select(columns(), label=t("field.x"), on_change=on).bind_value(draft, "x").props(
                            "dense outlined").classes("w-full")
                        agg_sel = ui.select({k: t(f"agg.{k}") for k in AGGS}, label=t("field.agg"),
                                            on_change=on).bind_value(draft, "agg").props("dense outlined").classes("w-full")
                        y_sel = ui.select(columns("number"), label=t("field.y"), on_change=on).bind_value(draft, "y").props(
                            "dense outlined").classes("w-full")
                        ui.number(t("field.limit"), min=1, max=1000, step=1, on_change=on).bind_value(
                            draft, "limit").props("dense outlined").classes("w-full")
                    with ui.column().classes("grow"):
                        ui.label(t("chart.preview")).classes("ngui-dashboard-muted")
                        preview()
                with ui.row().classes("w-full justify-end"):
                    ui.button(t("action.cancel"), on_click=dlg.close, color=None).props("flat")
                    ui.button(t("action.save"), icon="check", on_click=save).props("unelevated")
            built.append(True)
            sync()
            dlg.open()

        # --- data source -------------------------------------------------------------------------
        def source_dialog():
            env = bool(os.environ.get("DASHBOARD_DB_URL"))
            with ui.dialog() as dlg, ui.card().classes("w-[560px] max-w-[92vw]"):
                ui.label(t("source.title")).classes("ngui-card-title")
                ui.label(t("source.env" if env else "source.hint")).classes("ngui-dashboard-muted")
                field = ui.input(t("source.url"), value=shared.get("db_url") or "",
                                 placeholder="postgresql+psycopg://user:password@postgres:5432/app",
                                 password=True, password_toggle_button=True).props("dense outlined").classes("w-full")
                field.set_enabled(not env)

                async def test():
                    target = field.value.strip() or demo
                    try:
                        found = await run.io_bound(db.schema, target)
                    except ChartError as e:
                        ui.notify(t(e.key, **e.vars), type="negative", multi_line=True)
                        return
                    ui.notify(t("source.ok", count=len(found)), type="positive")

                def save():
                    old = db_url()
                    shared.set("db_url", field.value.strip() or None)
                    db.forget(old)
                    ui.navigate.reload()

                with ui.row().classes("w-full justify-end"):
                    ui.button(t("source.test"), icon="cable", on_click=test, color=None).props("flat")
                    ui.button(t("action.cancel"), on_click=dlg.close, color=None).props("flat")
                    save_btn = ui.button(t("action.save"), icon="check", on_click=save).props("unelevated")
                    save_btn.set_enabled(not env)
            dlg.open()

        board()
