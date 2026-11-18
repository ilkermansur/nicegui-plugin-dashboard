from harness import fetch


def test_dashboard_renders_kpis_and_demo_charts(start_app, tmp_path):
    html = fetch(start_app() + "/dashboard")
    assert "ngui-topbar" in html and "Gösterge paneli" in html
    for text in ("Veri kaynağı", "Demo veritabanı", "Bölgelere göre ciro", "Önceliğe göre destek talepleri",
                 "Yeni grafik"):
        assert text in html
    assert (tmp_path / "home" / "data" / "plugins" / "dashboard" / "demo.sqlite3").is_file()


def test_bad_database_url_shows_error_not_crash(start_app):
    url = start_app(env={"DASHBOARD_DB_URL": "sqlite:////nonexistent/dir/x.db"})
    html = fetch(url + "/dashboard")
    assert "ngui-topbar" in html and "Veritabanına bağlanılamadı" in html
    assert "Traceback" not in start_app.log()
