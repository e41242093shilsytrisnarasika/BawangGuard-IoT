# BawangGuard IoT - SoilWise ESP32 & FastAPI Monitoring

Sistem pemantauan kelembapan tanah, suhu, dan kelembapan udara berbasis ESP32 yang terintegrasi dengan backend FastAPI.

## Simulasi Rangkaian (Velxio)
- Tautan Simulasi: https://velxio.dev/e41241679/soilwise/

## Cara Menjalankan Backend Lokal
1. Masuk ke folder backend dan aktifkan virtual environment:
   cd backend
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
2. Jalankan server FastAPI:
   python -m uvicorn app.main:app --reload --port 8000
3. Jalankan tunnel publik (cloudflared tunnel --url http://127.0.0.1:8000) dan pasang URL tunnel ke variabel API_URL pada esp32/sketch.ino.
