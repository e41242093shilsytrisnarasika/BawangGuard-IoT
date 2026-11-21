from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SensorPayload(BaseModel):
    node_id: str = "NODE-01"
    soil_moisture: float = Field(..., ge=0, le=100, description="Kelembapan tanah %")
    soil_temp: float = Field(..., description="Suhu tanah °C")
    soil_ph: float = Field(..., ge=0, le=14)
    air_temp: float | None = None
    air_humidity: float | None = Field(None, ge=0, le=100)
    rainfall_mm: float | None = 0.0
    drainage_score: float | None = Field(0.7, ge=0, le=1)
    organic_carbon: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    cec: float | None = None
    season: str | None = None
    method: Literal["fuzzy", "random_forest", "decision_tree"] = "fuzzy"


class LabPayload(BaseModel):
    organic_carbon: float | None = None
    nitrogen: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    cec: float | None = None
    texture: str | None = None
    slope: float | None = None
    drainage: str | None = None
    notes: str | None = None


class AnalyzeResponse(BaseModel):
    id: int | None = None
    status: str
    status_label: str
    score: float
    method: str
    season: str | None = None
    factors: list[dict[str, Any]]
    limiting_factors: list[dict[str, Any]]
    recommendations: dict[str, Any]
    ml: dict[str, Any] | None = None
    reading: dict[str, Any] | None = None
    created_at: datetime | None = None
