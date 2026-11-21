# BawangGuard IoT — Monitoring Kesesuaian Lahan Bawang Merah

Sistem **IoT + AI** untuk memantau suhu tanah, kelembapan, pH, dan kondisi lahan agar cocok untuk budidaya **bawang merah**, sesuai arsitektur proposal IDTC 2026.

## Cara kerja

1. **Node sensor lapangan (ESP32)** mengukur kelembapan, suhu, pH, DHT22, dll.
2. Data dikirim via **Wi-Fi / MiFi 4G** (MQTT atau HTTPS).
3. Backend **FastAPI** menyimpan data (SQLite lokal / siap PostgreSQL) dan menjalankan AI:
   - **Fuzzy / rule-based** — mudah dijelaskan ke petani  
     Ideal: kelembapan 50–70%, suhu 25–32°C, pH 5,5–6,5, drainase baik → **COCOK UNTUK DITANAMKAN**
   - **Machine Learning** — Random Forest / Decision Tree → COCOK / KURANG COCOK / TIDAK COCOK
4. Dashboard menampilkan status, faktor pembatas, rekomendasi pupuk, amelioran, metode, dan jendela tanam.
5. Notifikasi untuk petani / penyuluh / kelompok tani.

## Menjalankan website

```bash
cd D:\IOT\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Buka: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## API untuk ESP32

`POST /api/sensors/ingest`

```json
{
  "node_id": "NODE-01",
  "soil_moisture": 58.5,
  "soil_temp": 27.2,
  "soil_ph": 6.1,
  "air_temp": 29.0,
  "air_humidity": 70,
  "drainage_score": 0.8,
  "method": "fuzzy"
}
```

## Struktur

```
backend/app/
  main.py              # FastAPI + dashboard
  ai/fuzzy_engine.py   # Rule-based / fuzzy
  ai/ml_engine.py      # Random Forest & Decision Tree
  templates/index.html # Monitoring web
  static/              # CSS & JS
```
