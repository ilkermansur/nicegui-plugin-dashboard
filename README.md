# nicegui-plugin-dashboard

ngui için gösterge paneli: veritabanı tablolarından sütun, çizgi, alan, pasta ve dağılım grafikleri çizer. Grafikler ekranda oluşturulur: tablo, X sütunu, hesap (satır sayısı, toplam, ortalama, en küçük, en büyük) ve Y sütunu seçilir, önizleme anında güncellenir. Grafikler bütün kullanıcılar için ortaktır; düzenlemek `dashboard.edit` yetkisi ister.

Kur: `ngui add https://github.com/ilkermansur/nicegui-plugin-dashboard`

İlk açılışta kendi klasöründe (`ctx.data_dir`) örnek verili bir SQLite veritabanı ve dört örnek grafikle gelir.

## Gerçek veritabanına bağlamak

Postgres'i ngui'nin `docker-compose.yml` dosyasına ayrı bir servis olarak ekle:

```yaml
  postgres:
    image: postgres:17
    environment: {POSTGRES_USER: app, POSTGRES_PASSWORD: degistir, POSTGRES_DB: app}
    volumes: ["pg-data:/var/lib/postgresql/data"]
    restart: unless-stopped
# volumes altına: pg-data: {}
```

Sonra ya panelde **Veri kaynağı** düğmesinden adresi yaz:
`postgresql+psycopg://app:degistir@postgres:5432/app`
ya da `.env` içine `DASHBOARD_DB_URL=...` yaz (ortam değişkeni ekrandaki ayarı ezer ve parolayı uygulama verisinin dışında tutar).

## Şablon olarak kullanmak

| Dosya | Ne öğretir |
|---|---|
| `plugin.toml` | `core = ">=1.1,<2"` (`ctx.data_dir` için), birden çok pip bağımlılığı, yetki |
| `__init__.py` | Async sayfa, `run.io_bound` ile engellemeyen veritabanı çağrıları, KPI kartları, `ui.refreshable`, diyalog içinde form + canlı önizleme, ortak veri (`ctx.storage.shared`), yetkiye göre düğme gösterme |
| `db.py` | NiceGUI'siz veritabanı katmanı: şemadan doğrulama, SQLAlchemy ifadeleriyle güvenli sorgu, ECharts seçenekleri, demo veri |
| `tests/` | Demo veritabanı üzerinde sorgu testleri (SQL enjeksiyon denemeleri dahil) ve uygulamayı açan uçtan uca test |

## Geliştirme

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../n_gui[dev] "sqlalchemy>=2" pytest-asyncio
.venv/bin/pytest -q          # ../nicegui-core-plugins klasörünü bekler (NGUI_CORE_PLUGINS ile değiştirilebilir)
ngui link dashboard .
```
