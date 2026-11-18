import pytest

from harness import import_plugin_module

db = import_plugin_module("db")


@pytest.fixture
def url(tmp_path):
    return db.demo_url(tmp_path)


def chart(**kw):
    return {"id": "c", "title": "t", "table": "sales", "type": "bar", "x": "region", "agg": "sum",
            "y": "revenue", "limit": 50, **kw}


def test_demo_database_is_seeded_once(tmp_path, url):
    tables = db.schema(url)
    assert set(tables) == {"sales", "tickets"}
    assert tables["sales"]["revenue"] == "number" and tables["sales"]["region"] == "text"
    assert db.demo_url(tmp_path) == url and len(db.rows(url, chart(agg="count", y=None))) == 4


def test_sum_by_group_is_ordered(url):
    data = db.rows(url, chart())
    assert [x for x, _ in data] == sorted(["Akdeniz", "Ege", "Marmara", "İç Anadolu"])
    assert all(y > 0 for _, y in data)


def test_count_needs_no_value_column(url):
    data = dict(db.rows(url, chart(table="tickets", x="priority", agg="count", y=None)))
    assert sum(data.values()) == 300


def test_scatter_returns_raw_pairs_up_to_limit(url):
    data = db.rows(url, chart(type="scatter", x="units", y="revenue", agg=None, limit=7))
    assert len(data) == 7


@pytest.mark.parametrize("bad,key", [
    ({"table": "users; drop table sales"}, "err.table"),
    ({"x": "region) or 1=1 --"}, "err.column"),
    ({"type": "radar"}, "err.type"),
    ({"agg": "median"}, "err.agg"),
    ({"y": "region"}, "err.y_number"),
])
def test_validate_rejects_anything_not_in_the_schema(url, bad, key):
    with pytest.raises(db.ChartError) as e:
        db.rows(url, chart(**bad))
    assert e.value.key == key
    assert len(db.rows(url, chart())) == 4  # sales still there


def test_unreachable_database_is_a_chart_error(tmp_path):
    with pytest.raises(db.ChartError) as e:
        db.schema("postgresql+psycopg://u:p@127.0.0.1:9/x") if _has_psycopg() else db.schema("nope://x")
    assert e.value.key in ("err.connect", "err.url")
    assert "secret" not in db.masked("sqlite:///x.db")


def _has_psycopg():
    import importlib.util
    return importlib.util.find_spec("psycopg") is not None


def test_masked_hides_password():
    assert "s3cret" not in db.masked("sqlite+pysqlite:///a.db") and db.masked("sqlite:///a.db").startswith("sqlite")


def test_options_per_type():
    data = [("a", 1.0), ("b", 2.0)]
    assert db.option(chart(type="pie"), data)["series"][0]["data"] == [{"name": "a", "value": 1.0},
                                                                      {"name": "b", "value": 2.0}]
    area = db.option(chart(type="area"), data)
    assert area["series"][0]["type"] == "line" and "areaStyle" in area["series"][0]
    assert area["xAxis"]["data"] == ["a", "b"]
    assert db.option(chart(type="scatter"), [(1, 2.0)])["series"][0]["data"] == [[1, 2.0]]
