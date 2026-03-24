# DTX-AI Sprint 1 — Teknik Rapor

**Hazırlayan:** Hakkı
**Tarih:** 24 Mart 2026
**Sprint:** 1 — Temel Altyapı ve Dashboard MVP
**Proje:** DTX-AI — Akıllı Depo Dijital İkiz Platformu

---

## İçindekiler

1. [Genel Bakış](#1-genel-bakış)
2. [Kurulan Dosyalar ve Görevleri](#2-kurulan-dosyalar-ve-görevleri)
3. [Mimari Kararlar](#3-mimari-kararlar)
4. [Veri Akışı](#4-veri-akışı)
5. [Takım Entegrasyon Noktaları](#5-takım-entegrasyon-noktaları)
6. [Bilinen Limitasyonlar ve Sprint 3'e Bırakılanlar](#6-bilinen-limitasyonlar-ve-sprint-3e-bırakılanlar)
7. [Kurulum Adımları](#7-kurulum-adımları)

---

## 1. Genel Bakış

Bu sprint kapsamında DTX-AI projesinin iki ana bileşeni sıfırdan inşa edilmiştir:

- **`apps/api/`** — FastAPI tabanlı stub backend. Sensör olaylarını kabul eder, yapay bir anomali skoru üretir ve sonuçları hem REST hem de WebSocket üzerinden yayınlar.
- **`apps/dashboard/`** — React + Vite + Tailwind CSS tabanlı gerçek zamanlı izleme arayüzü. API'den gelen olayları canlı olarak gösterir; bağlantı kesilirse mock veriye düşer.

Sprint sonunda sistem uçtan uca çalışır durumda olup `curl` ile gönderilen bir sensör olayı saniyeler içinde dashboardda görünmektedir.

---

## 2. Kurulan Dosyalar ve Görevleri

### 2.1 Backend — `apps/api/`

```
apps/api/
├── main.py
├── requirements.txt
├── .env.example
├── schemas/
│   ├── __init__.py
│   └── events.py
├── services/
│   ├── __init__.py
│   └── ai_stub.py
└── routers/
    ├── __init__.py
    └── events.py
```

| Dosya | Görev |
|---|---|
| `main.py` | FastAPI uygulamasını başlatır, CORS middleware'i ekler, `routers.events` router'ını bağlar ve `uvicorn` giriş noktasını tanımlar. |
| `schemas/events.py` | Tüm veri modellerini tanımlar: `EventFeatures`, `EventIn`, `FeatureImpact`, `AnomalyResult`, `Severity`. Pydantic v2 tabanlı; otomatik validasyon ve OpenAPI dokümantasyonu sağlar. |
| `services/ai_stub.py` | Gerçek ML pipeline'ının yerini tutan stub servis. `process_event(EventIn) → AnomalyResult` fonksiyonunu dışa açar. Anomali tipini özellik değerlerine göre seçer, skoru rastgele atar, Türkçe açıklamalar döndürür. |
| `routers/events.py` | Üç endpoint sunar: `POST /events`, `GET /events`, `WS /ws/events`. In-memory `deque(maxlen=50)` ile son 50 sonucu tutar; dahili `_ConnectionManager` ile WebSocket istemcilerine broadcast yapar. |
| `requirements.txt` | `fastapi`, `uvicorn[standard]`, `websockets`, `python-dotenv`, `pydantic` bağımlılıklarını tanımlar. |
| `.env.example` | `API_HOST` ve `API_PORT` ortam değişkenlerinin şablonu. |

### 2.2 Frontend — `apps/dashboard/src/`

```
src/
├── App.jsx
├── main.jsx
├── index.css
├── lib/
│   └── mockData.js
├── hooks/
│   └── useWebSocket.js
├── pages/
│   └── Dashboard.jsx
└── components/
    ├── ui/
    │   ├── Badge.jsx
    │   └── Card.jsx
    ├── layout/
    │   ├── Sidebar.jsx
    │   └── TopBar.jsx
    └── dashboard/
        ├── StatusCards.jsx
        ├── EventTable.jsx
        ├── ExplanationPanel.jsx
        └── TrendChart.jsx
```

| Dosya | Görev |
|---|---|
| `App.jsx` | `BrowserRouter` sarmalar, `Sidebar` + `TopBar` sabit düzenini oluşturur, rotaları tanımlar. `useWebSocket` hook'unu layout seviyesinde çağırarak WS durumunu TopBar'a iletir. |
| `lib/mockData.js` | Yalnızca `mockEvents` dışa açar (5 örnek olay). `useWebSocket(null)` çağrısında mock mod için kullanılır. `statusSummary` ve `trendData` sprint içinde kaldırılmış; tüm türev veriler artık canlı olay listesinden hesaplanmaktadır. |
| `hooks/useWebSocket.js` | WebSocket bağlantısını yönetir. URL verilmezse mock mod etkinleşir. Bağlantı kesildiğinde 3 saniye sonra otomatik yeniden bağlanır. `url` referans bir `useRef` üzerinden takip edilir; bu sayede retry closure stale capture sorununa düşmez. |
| `pages/Dashboard.jsx` | Sayfanın ana bileşeni. Mount'ta `GET /events` ile mevcut olayları çeker, WebSocket üzerinden yeni olayları izler ve iki `useMemo` ile türev verileri (`summary`, `trendData`) hesaplar. |
| `components/ui/Badge.jsx` | Önem derecesine göre renkli pill rozeti. `low`=yeşil, `medium`=sarı, `high`=turuncu, `critical`=kırmızı. |
| `components/ui/Card.jsx` | Koyu arka plan, ince kenarlık ve gölge içeren temel kart sarmalayıcısı. `className` prop'u ile genişletilebilir. |
| `components/layout/Sidebar.jsx` | Sol tarafta sabit panel. "DTX-AI" başlığı, depo ikonu ve üç gezinme öğesi (`Dashboard`, `Olaylar`, `Ayarlar`). Aktif rota `react-router-dom`'un `NavLink` bileşeniyle vurgulanır. |
| `components/layout/TopBar.jsx` | Üstte sabit çubuk. Sol tarafta sayfa başlığı; sağ tarafta WebSocket durum göstergesi (yeşil/kırmızı nokta) ve her saniye güncellenen canlı saat. |
| `components/dashboard/StatusCards.jsx` | Dört metrik kartı grid içinde gösterir. Tüm değerleri prop olarak alır; aktif uyarı sayısı sıfırın üzerindeyse Bell kartı kırmızı `animate-pulse` ile vurgu yapar. |
| `components/dashboard/EventTable.jsx` | Olay listesini tablo olarak gösterir. Anomali skoru renkli çubuk (yeşil→kırmızı), önem derecesi `Badge` bileşeni ve tıklanabilir satırlarla desteklenir. |
| `components/dashboard/ExplanationPanel.jsx` | Seçili olay yokken boş durum gösterir. Olay seçildiğinde varlık adı, anomali tipi + skor, yatay özellik etkisi çubukları ve Türkçe açıklamayı gösterir. |
| `components/dashboard/TrendChart.jsx` | Recharts `LineChart` ile son 20 olayın anomali skorunu zaman ekseninde çizer. 0.70 eşiğinde kesik kırmızı referans çizgisi vardır. |

---

## 3. Mimari Kararlar

### 3.1 Stub-first Yaklaşım

Gerçek ML modeli (Isolation Forest, SHAP) henüz entegre edilmediğinden `ai_stub.py` servisi bu boşluğu doldurur. Önemli nokta: stub'ın imzası (`process_event(EventIn) → AnomalyResult`) nihai modelin imzasıyla birebir aynıdır. Bu sayede AI ekibi yalnızca `ai_stub.py` dosyasını kendi implementasyonuyla değiştirerek entegrasyon gerçekleştirebilir; router, schema veya dashboard'da değişiklik gerekmez.

### 3.2 Şemalar Tek Kaynak Olarak

`schemas/events.py` içindeki Pydantic modelleri projenin veri sözleşmesini tanımlar. FastAPI bu şemaları otomatik olarak OpenAPI dokümantasyonuna (`/docs`) dönüştürür. Frontend geliştiriciler, simülatör ekibi ve AI ekibi hangi alanların zorunlu, hangilerinin isteğe bağlı olduğunu bu tek dosyadan okuyabilir.

### 3.3 In-Memory Depolama

`routers/events.py` içindeki `deque(maxlen=50)` bilinçli bir seçimdir: sprint 1 için kalıcı veritabanı kurulumu gerekli değildir. `apps/api/api/database.py` dosyasında SQLite ile çalışan tam bir kalıcılık katmanı zaten mevcuttur; sprint 2'de `process_event` çıktısı `insert_event()` çağrısıyla buraya yönlendirilecektir.

### 3.4 WebSocket Yeniden Bağlanma Stratejisi

`useWebSocket.js` içinde `connect()` fonksiyonu bir `useCallback` ile stabilize edilmiştir ve URL'yi doğrudan kapatmak yerine `urlRef` referansı üzerinden okur. Bu tasarım iki sorunu önler:

1. **Stale closure:** Retry zamanlayıcı her zaman güncel URL'yi görür.
2. **Temizleme çakışması:** Unmount sırasında `ws.onclose` ve `ws.onerror` null'a çekilir; bu sayede component unmount olduğunda gereksiz retry planlanmaz.

### 3.5 Türev Veri Hesaplama

Dashboard'daki tüm özet değerler (`activeAlerts`, `connectedSensors`, `lastDataTime`, `systemStatus`, `trendData`) `useMemo` ile canlı `events` dizisinden türetilir. Ayrı bir state tutulmadığından senkronizasyon hatası riski sıfırdır: bir WebSocket mesajı geldiğinde tek bir state güncellemesi tüm UI'ı tutarlı biçimde yeniden hesaplar.

### 3.6 Karanlık Tema

Tailwind `darkMode: 'class'` ile yapılandırılmıştır. `App.jsx` kök elementine `dark` sınıfı eklenerek tüm uygulama varsayılan olarak karanlık modda başlatılır. Gelecekte tema geçişi eklemek için yalnızca bu sınıfı toggle etmek yeterlidir.

---

## 4. Veri Akışı

Aşağıdaki diyagram bir sensör olayının sistemden geçişini göstermektedir:

```
Simülatör / curl
      │
      │  POST /events
      │  {entity_id, entity_type, features: {proximity, speed, ...}}
      ▼
┌─────────────────────┐
│   FastAPI (main.py) │
│   CORS middleware   │
└────────┬────────────┘
         │
         ▼
┌────────────────────────┐
│  routers/events.py     │
│  ingest_event()        │
│  1. EventIn validate   │
│  2. process_event()    │──► services/ai_stub.py
│  3. deque.appendleft() │    - anomaly_score (rastgele 0.30-0.95)
│  4. broadcast()        │    - anomaly_type  (özellik bazlı seçim)
└────────┬───────────────┘    - severity      (skor eşiğine göre)
         │                    - top_features  (etki sıralaması)
         │                    - explanation   (Türkçe açıklama)
         │
         ├──► HTTP 201  AnomalyResult JSON  (curl yanıtı)
         │
         └──► WebSocket broadcast
                   │
                   ▼
        ┌──────────────────────┐
        │  Dashboard (React)   │
        │  useWebSocket.js     │
        │  onmessage → parse   │
        │  setEvents(prev =>   │
        │    [data, ...prev])  │
        └──────────┬───────────┘
                   │  useMemo
                   ├──► deriveStatus()  → StatusCards yenilenir
                   ├──► deriveTrend()   → TrendChart yenilenir
                   └──► EventTable      → Yeni satır en üste eklenir
```

**İlk yükleme akışı** (Dashboard mount):

```
Dashboard mount
      │
      ├──► WS bağlantısı kurulur (ws://localhost:8000/ws/events)
      │
      └──► GET /events  (http://localhost:8000/events)
                │
                ▼
           Son 50 olay alınır
           Mevcut event_id'lere göre tekrar önlenir
           setEvents() ile listeye eklenir
```

**Mock mod** (API erişilemez veya URL=null):

```
useWebSocket(null)
      │
      └──► mockEvents (5 statik olay)  → status = "connected"
```

---

## 5. Takım Entegrasyon Noktaları

### 5.1 AI Ekibi — `services/ai_stub.py`'ı Gerçek Modelle Değiştirme

Stub fonksiyonun imzası değişmemelidir:

```python
# services/ai_stub.py  →  services/ai_pipeline.py (veya aynı dosyada)
def process_event(event: EventIn) -> AnomalyResult:
    ...
```

Gerçek implementasyonda yapılacaklar:

1. `event.features` alanlarından (`proximity`, `speed`, `vibration_rms` vb.) bir NumPy/Pandas vektörü oluşturun.
2. Eğitilmiş Isolation Forest modelini çalıştırın → `anomaly_score` (0.0–1.0).
3. SHAP değerlerini hesaplayın → `top_features` listesini doldurun (`FeatureImpact.impact` = normalize SHAP değeri).
4. `AnomalyResult` döndürün — diğer hiçbir dosyaya dokunmadan sistem çalışır.

`routers/events.py` içindeki import satırı:

```python
from services.ai_stub import process_event  # ← bu satırı değiştirin
```

### 5.2 Simülatör Ekibi — `schemas/events.py`'ı Referans Alın

Simülatörden gönderilecek JSON payload'ının şeması:

```json
{
  "entity_id": "Forklift-01",
  "entity_type": "forklift",
  "timestamp": "2026-03-24T10:42:13Z",
  "features": {
    "proximity": 0.8,
    "speed": 12.0,
    "direction": "kuzey",
    "zone": "restricted-A",
    "vibration_rms": 0.3,
    "stop_duration": null
  }
}
```

- Tüm `features` alanları isteğe bağlıdır (`Optional[float/str]`). Bilinmeyen alanlar `null` gönderilebilir.
- `timestamp` isteğe bağlıdır; verilmezse sunucu UTC anını kullanır.
- `entity_id` ve `entity_type` zorunludur.

Test için `curl`:

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "Forklift-01",
    "entity_type": "forklift",
    "features": {"proximity": 0.8, "speed": 12.0}
  }'
```

### 5.3 Backend Ekibi — Kalıcılık Katmanını Bağlama

`apps/api/api/database.py` dosyasında SQLite tabanlı kalıcılık zaten mevcuttur. Sprint 2'de `routers/events.py` içindeki `ingest_event` fonksiyonuna şu satır eklenecektir:

```python
from api.database import insert_event

async def ingest_event(event: EventIn) -> AnomalyResult:
    result = process_event(event)
    await insert_event({...})   # ← eklenecek
    ...
```

### 5.4 Frontend Ekibi — Yeni Bileşen Ekleme

Dashboard düzeni `pages/Dashboard.jsx` içinde `space-y-5` flex container ile yönetilmektedir. Yeni bir panel eklemek için:

1. `components/dashboard/` altına yeni bileşen oluşturun.
2. `Dashboard.jsx` içindeki `events` ve `useMemo` türevlerini prop olarak geçirin.
3. Varsa `ui/Card.jsx` sarmalayıcısını kullanın — tutarlı stil otomatik gelir.

---

## 6. Bilinen Limitasyonlar ve Sprint 3'e Bırakılanlar

### 6.1 Mevcut Limitasyonlar

| Konu | Durum | Açıklama |
|---|---|---|
| **Kalıcı depolama yok** | Biliniyor | Olaylar yalnızca bellekte tutulur (`deque(maxlen=50)`). Sunucu yeniden başladığında tüm geçmiş kaybolur. |
| **Anomali skoru sahte** | Bilerek | `ai_stub.py` rastgele değer üretir. Gerçek model sprint 2'de entegre edilecek. |
| **trendData zaman ekseni** | Kısmi | Aynı dakikaya ait birden fazla olay grafik üzerinde üst üste görünür (tekil zaman damgası gösterimi). |
| **WebSocket kimlik doğrulama yok** | Biliniyor | WS endpoint herkese açıktır. JWT veya token bazlı doğrulama sprint 3'e bırakıldı. |
| **CORS tüm originlere açık** | Geliştirme için OK | `allow_origins=["*"]` yalnızca geliştirme ortamı içindir. Production'da `CORS_ORIGINS` env değişkeniyle kısıtlanacak. |
| **İstemci tarafı filtreleme yok** | Eksik | EventTable tüm şiddet seviyelerini gösterir; severity veya zaman bazlı filtreleme Sprint 3'e bırakıldı. |
| **Mobil uyumluluk** | Test edilmedi | Sidebar sabit genişlikte (`w-56`); küçük ekranlarda düzen bozulabilir. Responsive tasarım Sprint 3 kapsamında. |
| **Mock veri field uyumsuzluğu** | Kısmen çözüldü | `mockData.js` içindeki olaylar `id` ve `entity` alanlarını kullanır; API `event_id` ve `entity_id` döndürür. Dashboard her iki formatı destekler. |

### 6.2 Sprint 3'e Bırakılanlar

- [ ] SQLite kalıcılık katmanının `routers/events.py`'a bağlanması
- [ ] Gerçek Isolation Forest + SHAP entegrasyonu (`ai_stub.py` → `ai_pipeline.py`)
- [ ] `GET /events` için timestamp/severity bazlı sorgu parametreleri
- [ ] Dashboard'a olay filtresi (severity dropdown, tarih aralığı)
- [ ] WebSocket bağlantısı için JWT kimlik doğrulaması
- [ ] TopBar'daki WebSocket göstergesine bağlı sensör sayısı
- [ ] TrendChart için dinamik zaman penceresi seçimi (10dk / 1sa / 24sa)
- [ ] Sidebar responsive hamburger menü (mobil)
- [ ] Production CORS kısıtlaması ve `.env` şablonu güncellemesi
- [ ] `/events` ve `/settings` sayfalarının implementasyonu (şu an "yakında" placeholder)

---

## 7. Kurulum Adımları

### 7.1 Ön Gereksinimler

- Python 3.11+
- Node.js 18+
- npm 9+

### 7.2 Backend (FastAPI)

```bash
# Proje kök dizininden başlayın
cd apps/api

# Sanal ortam oluşturun
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Ortam değişkenlerini ayarlayın
cp .env.example .env
# .env dosyasında gerekirse API_HOST ve API_PORT değerlerini düzenleyin

# API'yi başlatın
uvicorn main:app --reload --port 8000
# veya
python main.py
```

API başarıyla başladığında:
- REST API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Sağlık kontrolü: `http://localhost:8000/health`

### 7.3 Frontend (React + Vite)

```bash
# Yeni terminal açın
cd apps/dashboard

# Bağımlılıkları yükleyin
npm install

# Geliştirme sunucusunu başlatın
npm run dev
# Dashboard: http://localhost:5173

# Production build (isteğe bağlı)
npm run build
npm run preview
```

### 7.4 Uçtan Uca Test

Her iki servis çalışırken test olayı gönderin:

```bash
# Basit test
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"Forklift-01","entity_type":"forklift","features":{"proximity":0.8,"speed":12.0}}'

# Kritik senaryo (zone ihlali)
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"Human-03","entity_type":"human","features":{"zone":"restricted-A","proximity":1.2}}'

# Vibrasyon alarmı
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"Sensor-Rack-B","entity_type":"sensor","features":{"vibration_rms":4.5}}'

# Son 50 olayı listele
curl http://localhost:8000/events | python -m json.tool
```

Her `curl` komutu sonrasında `http://localhost:5173` adresindeki dashboard'da EventTable'a yeni satır eklenmeli, StatusCards değerleri güncellemeli ve TrendChart'a yeni veri noktası eklenmelidir.

### 7.5 Sadece Frontend (API olmadan — Mock Mod)

`Dashboard.jsx` içindeki WebSocket URL'sini `null` yaparak mock modda çalıştırabilirsiniz:

```js
// src/pages/Dashboard.jsx — geçici değişiklik
const { events, setEvents, status } = useWebSocket(null); // mock mod
```

Bu durumda `src/lib/mockData.js` içindeki 5 örnek olay yüklenir ve dashboard API bağlantısı olmadan görüntülenebilir.

---

*Rapor sonu. Sorular için: proje Kanban panosu → Sprint 1 sütunu.*
