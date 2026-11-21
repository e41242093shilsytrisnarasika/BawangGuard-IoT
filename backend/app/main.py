from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .ai.fuzzy_engine import analyze_soil, current_indonesia_season
from .ai.ml_engine import predict_ml, train_models
from .database import (
    LabInput,
    Notification,
    SensorReading,
    get_db,
    init_db,
    utcnow,
)
from .schemas import LabPayload, SensorPayload

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(
    title="BawangGuard IoT — Monitoring Bawang Merah",
    description="Sistem IoT + AI kesesuaian lahan bawang merah (Fuzzy + Random Forest/Decision Tree)",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    train_models(force=False)
    db = next(get_db())
    try:
        if db.query(SensorReading).count() == 0:
            seed_demo_data(db)
    finally:
        db.close()


def run_analysis(payload: SensorPayload) -> dict[str, Any]:
    season = payload.season or current_indonesia_season()
    kwargs = dict(
        soil_moisture=payload.soil_moisture,
        soil_temp=payload.soil_temp,
        soil_ph=payload.soil_ph,
        drainage_score=payload.drainage_score or 0.7,
        organic_carbon=payload.organic_carbon,
        nitrogen=payload.nitrogen,
        phosphorus=payload.phosphorus,
        potassium=payload.potassium,
        season=season,
        air_temp=payload.air_temp,
        air_humidity=payload.air_humidity,
    )
    if payload.method == "fuzzy":
        return analyze_soil(**kwargs)
    model_name = "random_forest" if payload.method == "random_forest" else "decision_tree"
    return predict_ml(**kwargs, model_name=model_name)


def persist_reading(db: Session, payload: SensorPayload, result: dict[str, Any]) -> SensorReading:
    row = SensorReading(
        node_id=payload.node_id,
        soil_moisture=payload.soil_moisture,
        soil_temp=payload.soil_temp,
        soil_ph=payload.soil_ph,
        air_temp=payload.air_temp,
        air_humidity=payload.air_humidity,
        rainfall_mm=payload.rainfall_mm or 0.0,
        drainage_score=payload.drainage_score or 0.7,
        organic_carbon=payload.organic_carbon,
        nitrogen=payload.nitrogen,
        phosphorus=payload.phosphorus,
        potassium=payload.potassium,
        cec=payload.cec,
        season=result.get("season"),
        status=result["status"],
        score=result["score"],
        limiting_factors=json.dumps(result.get("limiting_factors") or [], ensure_ascii=False),
        recommendations_json=json.dumps(result.get("recommendations") or {}, ensure_ascii=False),
        method=result.get("method", payload.method),
        created_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    title_map = {
        "COCOK": "COCOK UNTUK DITANAMKAN",
        "KURANG_COCOK": "KURANG COCOK — Perlu Perbaikan",
        "TIDAK_COCOK": "TIDAK COCOK — Ameliorasi Diperlukan",
    }
    msg = result["recommendations"].get("summary", result["status_label"])
    if result.get("limiting_factors"):
        causes = "; ".join(f["cause"] for f in result["limiting_factors"][:2])
        msg = f"{msg} Faktor: {causes}"
    notif = Notification(
        title=title_map.get(result["status"], result["status_label"]),
        message=msg,
        status=result["status"],
        channel="web",
        role="petani",
        is_read=False,
    )
    db.add(notif)
    db.commit()
    return row


def seed_demo_data(db: Session) -> None:
    scenarios = [
        dict(soil_moisture=60, soil_temp=28, soil_ph=6.0, drainage_score=0.85, organic_carbon=2.2, nitrogen=55, phosphorus=45, potassium=60),
        dict(soil_moisture=35, soil_temp=30, soil_ph=6.1, drainage_score=0.8, organic_carbon=1.8, nitrogen=40, phosphorus=35, potassium=50),
        dict(soil_moisture=78, soil_temp=27, soil_ph=5.2, drainage_score=0.35, organic_carbon=1.1, nitrogen=30, phosphorus=25, potassium=35),
        dict(soil_moisture=55, soil_temp=33, soil_ph=7.0, drainage_score=0.7, organic_carbon=2.0, nitrogen=48, phosphorus=40, potassium=55),
        dict(soil_moisture=62, soil_temp=26, soil_ph=5.8, drainage_score=0.75, organic_carbon=2.5, nitrogen=60, phosphorus=50, potassium=65),
    ]
    now = utcnow()
    for i in range(36):
        base = scenarios[i % len(scenarios)].copy()
        base["soil_moisture"] = max(15, min(95, base["soil_moisture"] + random.uniform(-8, 8)))
        base["soil_temp"] = max(18, min(40, base["soil_temp"] + random.uniform(-2, 2)))
        base["soil_ph"] = max(4.5, min(8, base["soil_ph"] + random.uniform(-0.2, 0.2)))
        base["air_temp"] = base["soil_temp"] + random.uniform(-1, 2)
        base["air_humidity"] = random.uniform(55, 85)
        base["rainfall_mm"] = random.choice([0, 0, 0, 2, 8, 15])
        payload = SensorPayload(node_id=f"NODE-0{(i % 3) + 1}", method="fuzzy", **base)
        result = run_analysis(payload)
        row = SensorReading(
            node_id=payload.node_id,
            soil_moisture=payload.soil_moisture,
            soil_temp=payload.soil_temp,
            soil_ph=payload.soil_ph,
            air_temp=payload.air_temp,
            air_humidity=payload.air_humidity,
            rainfall_mm=payload.rainfall_mm,
            drainage_score=payload.drainage_score,
            organic_carbon=payload.organic_carbon,
            nitrogen=payload.nitrogen,
            phosphorus=payload.phosphorus,
            potassium=payload.potassium,
            season=result.get("season"),
            status=result["status"],
            score=result["score"],
            limiting_factors=json.dumps(result.get("limiting_factors") or [], ensure_ascii=False),
            recommendations_json=json.dumps(result.get("recommendations") or {}, ensure_ascii=False),
            method="fuzzy",
            created_at=now - timedelta(hours=35 - i),
        )
        db.add(row)
    db.add(
        Notification(
            title="Sistem siap — monitoring lahan bawang merah aktif",
            message="Node sensor NODE-01/02/03 terhubung. Engine fuzzy & Random Forest siap menganalisis kesesuaian lahan.",
            status="COCOK",
            channel="web",
            role="penyuluh",
        )
    )
    db.commit()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    try:
        return templates.TemplateResponse(request, "index.html")
    except TypeError:
        # Kompatibilitas Starlette lama
        return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
def health():
    return {"ok": True, "service": "BawangGuard IoT", "season": current_indonesia_season()}


@app.post("/api/analyze")
def analyze(payload: SensorPayload, db: Session = Depends(get_db)):
    result = run_analysis(payload)
    row = persist_reading(db, payload, result)
    return {
        **result,
        "id": row.id,
        "created_at": row.created_at,
        "reading": {
            "node_id": row.node_id,
            "soil_moisture": row.soil_moisture,
            "soil_temp": row.soil_temp,
            "soil_ph": row.soil_ph,
            "air_temp": row.air_temp,
            "air_humidity": row.air_humidity,
            "drainage_score": row.drainage_score,
        },
    }


@app.post("/api/sensors/ingest")
def ingest_sensor(payload: SensorPayload, db: Session = Depends(get_db)):
    """Endpoint untuk ESP32 / MQTT bridge (HTTPS)."""
    return analyze(payload, db)


@app.get("/api/latest")
def latest(db: Session = Depends(get_db)):
    row = db.query(SensorReading).order_by(SensorReading.created_at.desc()).first()
    if not row:
        raise HTTPException(404, "Belum ada data sensor")
    return _serialize_reading(row)


@app.get("/api/readings")
def readings(
    limit: int = Query(48, ge=1, le=500),
    node_id: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(SensorReading).order_by(SensorReading.created_at.desc())
    if node_id:
        q = q.filter(SensorReading.node_id == node_id)
    rows = q.limit(limit).all()
    return [_serialize_reading(r) for r in reversed(rows)]


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    rows = db.query(SensorReading).order_by(SensorReading.created_at.desc()).limit(200).all()
    if not rows:
        return {"total": 0}
    counts = {"COCOK": 0, "KURANG_COCOK": 0, "TIDAK_COCOK": 0}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    latest = rows[0]
    nodes = sorted({r.node_id for r in rows})
    return {
        "total": len(rows),
        "counts": counts,
        "nodes": nodes,
        "season": latest.season or current_indonesia_season(),
        "latest_status": latest.status,
        "latest_score": latest.score,
        "avg_moisture": round(sum(r.soil_moisture for r in rows) / len(rows), 1),
        "avg_temp": round(sum(r.soil_temp for r in rows) / len(rows), 1),
        "avg_ph": round(sum(r.soil_ph for r in rows) / len(rows), 2),
    }


@app.get("/api/notifications")
def notifications(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "status": n.status,
            "channel": n.channel,
            "role": n.role,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]


@app.post("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == notif_id).first()
    if not n:
        raise HTTPException(404, "Notifikasi tidak ditemukan")
    n.is_read = True
    db.commit()
    return {"ok": True}


@app.post("/api/lab")
def save_lab(payload: LabPayload, db: Session = Depends(get_db)):
    row = LabInput(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "message": "Data uji tanah tersimpan — gunakan saat analisis berikutnya"}


@app.get("/api/lab/latest")
def lab_latest(db: Session = Depends(get_db)):
    row = db.query(LabInput).order_by(LabInput.created_at.desc()).first()
    if not row:
        return None
    return {
        "organic_carbon": row.organic_carbon,
        "nitrogen": row.nitrogen,
        "phosphorus": row.phosphorus,
        "potassium": row.potassium,
        "cec": row.cec,
        "texture": row.texture,
        "slope": row.slope,
        "drainage": row.drainage,
        "notes": row.notes,
        "created_at": row.created_at,
    }


@app.post("/api/simulate")
def simulate(
    scenario: str = Query("random", pattern="^(random|ideal|dry|wet|acid|alkaline)$"),
    method: str = Query("fuzzy", pattern="^(fuzzy|random_forest|decision_tree)$"),
    db: Session = Depends(get_db),
):
    presets = {
        "ideal": dict(soil_moisture=60, soil_temp=28, soil_ph=6.0, drainage_score=0.9, organic_carbon=2.4, nitrogen=58, phosphorus=48, potassium=62),
        "dry": dict(soil_moisture=32, soil_temp=34, soil_ph=6.2, drainage_score=0.8, organic_carbon=1.6, nitrogen=42, phosphorus=38, potassium=45),
        "wet": dict(soil_moisture=82, soil_temp=26, soil_ph=5.8, drainage_score=0.3, organic_carbon=2.0, nitrogen=50, phosphorus=40, potassium=55),
        "acid": dict(soil_moisture=58, soil_temp=27, soil_ph=4.9, drainage_score=0.7, organic_carbon=1.2, nitrogen=35, phosphorus=28, potassium=40),
        "alkaline": dict(soil_moisture=55, soil_temp=29, soil_ph=7.4, drainage_score=0.75, organic_carbon=1.8, nitrogen=45, phosphorus=35, potassium=50),
        "random": dict(
            soil_moisture=round(random.uniform(25, 88), 1),
            soil_temp=round(random.uniform(22, 36), 1),
            soil_ph=round(random.uniform(4.8, 7.6), 2),
            drainage_score=round(random.uniform(0.25, 0.95), 2),
            organic_carbon=round(random.uniform(0.8, 3.5), 2),
            nitrogen=round(random.uniform(20, 80), 1),
            phosphorus=round(random.uniform(15, 70), 1),
            potassium=round(random.uniform(20, 80), 1),
        ),
    }
    data = presets[scenario]
    data.update(
        air_temp=round(data["soil_temp"] + random.uniform(-1, 1.5), 1),
        air_humidity=round(random.uniform(50, 90), 1),
        rainfall_mm=round(random.choice([0, 0, 1.5, 6, 12]), 1),
        node_id=random.choice(["NODE-01", "NODE-02", "NODE-03"]),
        method=method,  # type: ignore
    )
    payload = SensorPayload(**data)
    return analyze(payload, db)


def _serialize_reading(row: SensorReading) -> dict[str, Any]:
    return {
        "id": row.id,
        "node_id": row.node_id,
        "soil_moisture": row.soil_moisture,
        "soil_temp": row.soil_temp,
        "soil_ph": row.soil_ph,
        "air_temp": row.air_temp,
        "air_humidity": row.air_humidity,
        "rainfall_mm": row.rainfall_mm,
        "drainage_score": row.drainage_score,
        "organic_carbon": row.organic_carbon,
        "nitrogen": row.nitrogen,
        "phosphorus": row.phosphorus,
        "potassium": row.potassium,
        "season": row.season,
        "status": row.status,
        "status_label": {
            "COCOK": "COCOK UNTUK DITANAMKAN",
            "KURANG_COCOK": "KURANG COCOK",
            "TIDAK_COCOK": "TIDAK COCOK",
        }.get(row.status, row.status),
        "score": row.score,
        "limiting_factors": json.loads(row.limiting_factors or "[]"),
        "recommendations": json.loads(row.recommendations_json or "{}"),
        "method": row.method,
        "created_at": row.created_at,
    }
