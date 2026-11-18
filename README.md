# nicegui-plugin-dashboard

[ngui](https://github.com/ilkermansur/nicegui-core) için gösterge paneli. Bir veritabanındaki tablolardan grafik çizer; grafikler kod yazmadan, ekranda oluşturulur ve düzenlenir.

İki amacı var:
1. **Kullanmak:** Postgres (ya da SQLAlchemy'nin desteklediği başka bir veritabanı) verisini grafiklerle izlemek.
2. **Şablon olmak:** Veritabanına bağlanan, diyalog içinde form ve canlı önizleme kullanan, bütün kullanıcıların ortak verisiyle çalışan bir sayfa yazacaksan buradan başla.

## Kurulum

```bash
docker compose exec app ngui add https://github.com/ilkermansur/nicegui-plugin-dashboard
```

Uygulama yeniden başlar ve `sqlalchemy` ile `psycopg` bağımlılıklarını kurar. Menüde **Gösterge paneli** belirir.

İlk açılışta hiçbir ayar gerekmez. Plugin kendi klasöründe (`/data/data/plugins/dashboard/demo.sqlite3`) örnek veriyle bir SQLite veritabanı oluşturur ve dört örnek grafik gösterir:
- `sales`: 12 ay × 4 bölge × 3 ürün; satış adedi ve ciro
- `tickets`: 300 destek talebi; öncelik, durum, çözüm süresi

Çekirdek sözleşmesinin 1.1 sürümünü ister (`ctx.data_dir` için). Daha eski bir çekirdek bu plugin'i "bozuk" olarak işaretler.

## Ekran

```
Gösterge paneli
┌ Grafik: 5 ┐ ┌ Tablo: 2 ┐ ┌ Veri kaynağı: Demo veritabanı ┐
[+ Yeni grafik] [Veri kaynağı]                 (yalnızca dashboard.edit yetkisiyle)
┌ Bölgelere göre ciro    ✎ 🗑 ┐ ┌ Aylık ciro            ✎ 🗑 ┐
│ ▇▇ ▇▇ ▇▇ ▇▇                 │ │ ╱╲╱‾╲_╱‾                    │
└─────────────────────────────┘ └─────────────────────────────┘
```

**Yeni grafik / Düzenle** diyaloğu:

| Alan | Anlam |
|---|---|
| Başlık | Boş bırakılırsa `tablo · sütun` |
| Tablo | Veritabanındaki tablolar |
| Grafik türü | Sütun, çizgi, alan, pasta, dağılım |
| Gruplanan sütun (X) | Satırların gruplandığı sütun; varsayılan olarak ilk metin sütunu |
| Hesap | Satır sayısı, toplam, ortalama, en küçük, en büyük (dağılımda yok) |
| Değer sütunu (Y) | Yalnızca sayısal sütunlar. "Satır sayısı" seçiliyken gizli |
| En fazla satır | 1–1000 |

Sağdaki önizleme her değişiklikte yeniden çizilir. **Kaydet** grafiği panele ekler. Grafikler bütün kullanıcılar için ortaktır.

**Düzenleme modu.** Grafik kartları normalde yalnızca grafiği gösterir. Başlıktaki **Düzenle** düğmesi düzenleme modunu açar: kartlarda genişlik (üçte bir → üçte iki → tam), yükseklik (normal ↔ uzun), düzenle ve sil düğmeleri belirir, başlıkta **Vazgeç** ve **Kaydet** çıkar. Boyut değişiklikleri **Kaydet**'e basınca saklanır; **Vazgeç** onları atar. Izgara geniş ekranda 3, orta ekranda 2, dar ekranda 1 sütundur; boşluklar kendiliğinden doldurulur.

## Gerçek veritabanına bağlamak

Postgres'i ngui'nin `docker-compose.yml` dosyasına ayrı bir servis olarak ekle:

```yaml
services:
  # app: ... (var olan)
  postgres:
    image: postgres:17
    environment: {POSTGRES_USER: app, POSTGRES_PASSWORD: degistir, POSTGRES_DB: app}
    volumes: ["pg-data:/var/lib/postgresql/data"]
    restart: unless-stopped

volumes:
  ngui-data: {}
  pg-data: {}
```

Adresi vermenin iki yolu var:

| Yol | Nasıl | Ne zaman |
|---|---|---|
| Ekrandan | **Veri kaynağı** → `postgresql+psycopg://app:degistir@postgres:5432/app` → **Bağlantıyı dene** → **Kaydet** | Deneme ve hızlı kurulum. Adres uygulama verisinde (`/data`) saklanır |
| Ortam değişkeni | `.env` içine `DASHBOARD_DB_URL=postgresql+psycopg://...` | Kalıcı kurulum. Parola uygulama verisinin ve yedeklerin dışında kalır; ekrandaki ayarı ezer |

Adres boş bırakılırsa demo veritabanına dönülür. Bağlantı kurulamazsa sayfa yine açılır, hata mesajını gösterir ve "Veri kaynağı" kartı kırmızıya döner.

## Yetki ve güvenlik

- Paneli herkes görür. Grafik eklemek, düzenlemek, silmek ve veri kaynağını değiştirmek `dashboard.edit` yetkisi ister.
- Kullanıcının seçtiği tablo ve sütun adları her sorguda canlı şemayla karşılaştırılır. Sorgular SQLAlchemy ifadeleriyle kurulur, SQL'e metin yapıştırılmaz. Testlerde SQL enjeksiyonu denemeleri var.
- Yalnızca okuma yapılır: `SELECT ... GROUP BY ... LIMIT`.
- Panelin kullandığı veritabanı kullanıcısına yalnızca okuma yetkisi vermek yine de iyi bir alışkanlıktır.

## Nasıl çalışır

```
nicegui-plugin-dashboard/
  plugin.toml        core >=1.1, sqlalchemy + psycopg, dashboard.edit yetkisi
  __init__.py        sayfa: KPI'lar, grafik ızgarası, oluşturma diyaloğu, veri kaynağı diyaloğu
  db.py              NiceGUI'siz veritabanı katmanı: şema, doğrulama, sorgu, ECharts seçenekleri, demo veri
  sizes.py           grafik boyutları (genişlik, yükseklik), varsayılanlar ve geçiş sırası
  locales/*.toml     ekrandaki her metin (grafik türü ve hesap adları dahil)
  tests/             demo veritabanı üzerinde sorgu testleri + uygulamayı açan testler
```

| Konu | Nerede, nasıl |
|---|---|
| Grafik tanımı | Düz bir sözlük: `{id, title, table, type, x, agg, y, limit}`. Hepsi `ctx.storage.shared` içinde `charts` listesinde |
| Ortak veri | `ctx.storage.shared`: plugin'in bütün kullanıcıları aynı veriyi görür (API plugin'indeki `ctx.storage` ise kullanıcıya özeldir) |
| Dosya klasörü | `ctx.data_dir`: demo SQLite dosyası burada. Plugin kaldırılınca silinmez |
| Engellemeyen sorgu | Veritabanı çağrıları `await run.io_bound(db.rows, ...)` ile ayrı bir iş parçacığında çalışır; yavaş bir sorgu sayfayı dondurmaz |
| Önce sayfa, sonra veri | Kartlar önce yükleniyor simgesiyle çizilir, her grafik `ui.timer(..., once=True)` ile kendi verisini sonradan doldurur. Bir grafiğin hatası yalnızca kendi kartında görünür |
| Canlı önizleme | Diyaloğun her alanı `on_change` ile `sync()` çağırır. `sync` sütun seçeneklerini, alanların görünürlüğünü ve önizlemeyi günceller |
| Yetkiye göre arayüz | `ctx.role("auth").has("dashboard.edit")` sonucuna göre düzenleme düğmeleri çizilir ya da çizilmez |
| Tema uyumu | Grafikler SVG ile çizilir; yazı rengi CSS'ten `--ngui-muted` alır, böylece açık ve koyu modda okunur |

## Kendi panelini yapmak

Bu paneli beğenmediysen ya da başka bir veri ekranı istiyorsan **yalnızca kendi reposuna dokunursun**. Çekirdek ve core plugin'ler değişmez.

- **Küçük değişiklik** (yeni grafik türü, başka bir hesap): `db.py` içinde `CHART_TYPES`, `AGGS` ve `option()`; ardından iki dil dosyasına `type.<ad>` ya da `agg.<ad>` anahtarını ekle.
- **Farklı bir veri kaynağı** (REST API, CSV): `db.py` dosyasının yerine aynı üç fonksiyonu (`schema`, `rows`, `option`) sağlayan bir modül yaz. `__init__.py` neredeyse hiç değişmez.
- **Tamamen yeni bir sayfa:** `ngui new <ad>` ile iskelet oluştur, bu repodan `tests/` ve `pyproject.toml` dosyalarını kopyala, `db.py` örüntüsünü (arayüzden bağımsız katman ve onun testleri) koru.

Kurallar çekirdekteki [CONTRACT.md](https://github.com/ilkermansur/nicegui-core/blob/main/CONTRACT.md) dosyasında.

## Geliştirme

Klasörler yan yana olmalı: `n_gui/` (çekirdek), `nicegui-core-plugins/`, `nicegui-plugin-dashboard/`.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ../n_gui[dev] "sqlalchemy>=2" pytest-asyncio
.venv/bin/pytest -q
```

Testler `../nicegui-core-plugins` klasörünü bekler; farklı bir yer için `NGUI_CORE_PLUGINS=/yol` ver. Sayfa testleri uygulamayı gerçekten başlatır ve sayfayı HTTP ile çeker.

Çalışan uygulamada denemek:

```bash
ngui link dashboard .
# düzenle → uygulama yeniden başlar
git push
ngui unlink dashboard && ngui update dashboard
```

Her push'ta GitHub Actions testleri çalıştırır (`.github/workflows/test.yml`).
