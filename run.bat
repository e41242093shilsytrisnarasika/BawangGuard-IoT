@echo off
cd /d D:\IOT\backend
if not exist .venv (
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate
)
echo.
echo BawangGuard IoT berjalan di http://127.0.0.1:8000
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
