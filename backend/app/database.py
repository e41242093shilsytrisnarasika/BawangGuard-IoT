from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bawang_merah.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(64), default="NODE-01", index=True)
    soil_moisture = Column(Float, nullable=False)
    soil_temp = Column(Float, nullable=False)
    soil_ph = Column(Float, nullable=False)
    air_temp = Column(Float, nullable=True)
    air_humidity = Column(Float, nullable=True)
    rainfall_mm = Column(Float, nullable=True, default=0.0)
    drainage_score = Column(Float, nullable=True, default=0.7)
    organic_carbon = Column(Float, nullable=True)
    nitrogen = Column(Float, nullable=True)
    phosphorus = Column(Float, nullable=True)
    potassium = Column(Float, nullable=True)
    cec = Column(Float, nullable=True)
    season = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False)
    score = Column(Float, nullable=False)
    limiting_factors = Column(Text, nullable=True)
    recommendations_json = Column(Text, nullable=True)
    method = Column(String(32), default="fuzzy")
    created_at = Column(DateTime, default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    channel = Column(String(32), default="web")
    role = Column(String(64), default="petani")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow, index=True)


class LabInput(Base):
    __tablename__ = "lab_inputs"

    id = Column(Integer, primary_key=True, index=True)
    organic_carbon = Column(Float, nullable=True)
    nitrogen = Column(Float, nullable=True)
    phosphorus = Column(Float, nullable=True)
    potassium = Column(Float, nullable=True)
    cec = Column(Float, nullable=True)
    texture = Column(String(64), nullable=True)
    slope = Column(Float, nullable=True)
    drainage = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
