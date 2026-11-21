"""Rule-based / Fuzzy logic untuk kesesuaian lahan bawang merah.

Ambang ideal (literatur agronomi bawang merah):
- Kelembapan tanah: 50–70%
- Suhu tanah/udara: 25–32°C
- pH: 5,5–6,5
- Drainase: baik (>= 0.6)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STATUS_COCOK = "COCOK"
STATUS_KURANG = "KURANG_COCOK"
STATUS_TIDAK = "TIDAK_COCOK"

STATUS_LABEL = {
    STATUS_COCOK: "COCOK UNTUK DITANAMKAN",
    STATUS_KURANG: "KURANG COCOK",
    STATUS_TIDAK: "TIDAK COCOK",
}


@dataclass
class FactorResult:
    name: str
    label: str
    value: float | None
    unit: str
    ideal_min: float
    ideal_max: float
    membership: float  # 0..1 (1 = ideal)
    severity: str  # ok | warn | bad
    cause: str
    actions: list[str] = field(default_factory=list)


def _tri_membership(value: float, low: float, ideal_low: float, ideal_high: float, high: float) -> float:
    """Trapezoidal membership: 1 in [ideal_low, ideal_high], slopes outside."""
    if value is None:
        return 0.5
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value <= low or value >= high:
        return 0.0
    if value < ideal_low:
        return max(0.0, (value - low) / (ideal_low - low))
    return max(0.0, (high - value) / (high - ideal_high))


def _severity(m: float) -> str:
    if m >= 0.75:
        return "ok"
    if m >= 0.4:
        return "warn"
    return "bad"


def evaluate_moisture(v: float) -> FactorResult:
    m = _tri_membership(v, 20, 50, 70, 90)
    cause = "Kelembapan tanah dalam rentang ideal (50–70%)."
    actions: list[str] = []
    if v < 50:
        cause = "Kelembapan tanah rendah — risiko kekeringan umbi."
        actions = [
            "Lakukan irigasi tetes (drip irrigation) secara terjadwal.",
            "Mulsa organik untuk menahan evaporasi.",
            "Sirami pagi/sore; hindari genangan.",
        ]
    elif v > 70:
        cause = "Kelembapan tanah tinggi — risiko busuk umbi & jamur."
        actions = [
            "Buat bedengan tinggi dan saluran drainase.",
            "Kurangi frekuensi irigasi.",
            "Perbaiki aerasi tanah dengan penggemburan ringan.",
        ]
    return FactorResult("soil_moisture", "Kelembapan Tanah", v, "%", 50, 70, m, _severity(m), cause, actions)


def evaluate_temp(v: float) -> FactorResult:
    m = _tri_membership(v, 15, 25, 32, 40)
    cause = "Suhu dalam rentang ideal bawang merah (25–32°C)."
    actions: list[str] = []
    if v < 25:
        cause = "Suhu terlalu rendah — pertumbuhan vegetatif lambat."
        actions = [
            "Tunda tanam hingga musim lebih hangat.",
            "Gunakan mulsa plastik hitam untuk menaikkan suhu bedengan.",
            "Pilih lokasi dengan paparan matahari penuh.",
        ]
    elif v > 32:
        cause = "Suhu terlalu tinggi — stres panas & penurunan hasil."
        actions = [
            "Pasang naungan paranet 30–40% pada siang hari.",
            "Perbanyak irigasi ringan untuk pendinginan.",
            "Tanam pada musim kemarau dengan manajemen air ketat.",
        ]
    return FactorResult("soil_temp", "Suhu Tanah", v, "°C", 25, 32, m, _severity(m), cause, actions)


def evaluate_ph(v: float) -> FactorResult:
    m = _tri_membership(v, 4.0, 5.5, 6.5, 8.0)
    cause = "pH tanah ideal untuk bawang merah (5,5–6,5)."
    actions: list[str] = []
    if v < 5.5:
        cause = "pH asam (< 5,5) — ketersediaan hara terganggu."
        actions = [
            "Aplikasikan kapur dolomit (1–2 ton/ha, sesuaikan uji tanah).",
            "Tambahkan bahan organik / kompos matang.",
            "Ulangi uji pH 2–4 minggu setelah pengapuran.",
        ]
    elif v > 6.5:
        cause = "pH agak alkalis (> 6,5) — koreksi dengan bahan organik."
        actions = [
            "Tambahkan bahan organik (kompos, pupuk kandang matang).",
            "Hindari kapur; koreksi lanjut berdasarkan analisis laboratorium.",
            "Pantau ketersediaan mikronutrien (Fe, Zn, Mn).",
        ]
    return FactorResult("soil_ph", "pH Tanah", v, "", 5.5, 6.5, m, _severity(m), cause, actions)


def evaluate_drainage(v: float) -> FactorResult:
    """drainage_score 0..1 (1 = sangat baik)."""
    m = max(0.0, min(1.0, (v - 0.2) / 0.6)) if v is not None else 0.5
    if v is None:
        v = 0.7
    cause = "Drainase tanah baik."
    actions: list[str] = []
    if v < 0.6:
        cause = "Drainase buruk — genangan merusak umbi bawang merah."
        actions = [
            "Buat bedengan tinggi (30–40 cm) dan saluran antarbedengan.",
            "Tambahkan pasir/sekam untuk memperbaiki porositas.",
            "Kurangi irigasi pada musim hujan.",
        ]
    return FactorResult("drainage", "Drainase", round(v, 2), "skor", 0.6, 1.0, m, _severity(m), cause, actions)


def evaluate_npk(n: float | None, p: float | None, k: float | None) -> list[FactorResult]:
    results: list[FactorResult] = []
    # Ambang kasar relatif (mg/kg atau status relatif 0-100 skala demo)
    specs = [
        ("nitrogen", "Nitrogen (N)", n, 40, 80, "N rendah → pupuk N / kompos dan pemupukan berimbang."),
        ("phosphorus", "Fosfor (P)", p, 30, 70, "P rendah → SP-36 / pupuk P sesuai uji tanah."),
        ("potassium", "Kalium (K)", k, 40, 80, "K rendah → KCl / abu organik / pupuk K berimbang."),
    ]
    for key, label, val, lo, hi, tip in specs:
        if val is None:
            continue
        m = _tri_membership(val, 0, lo, hi, 120)
        actions: list[str] = []
        cause = f"{label} dalam kisaran cukup."
        if val < lo:
            cause = tip
            actions = [
                "Gunakan pupuk kandang/kompos matang sebagai sumber hara dasar.",
                "Pemupukan berimbang N-P-K sesuai dosis rekomendasi uji tanah.",
                "Split aplikasi: dasar + susulan sesuai fase pertumbuhan.",
            ]
        results.append(
            FactorResult(key, label, val, "rel", lo, hi, m, _severity(m), cause, actions)
        )
    return results


def classify_from_memberships(memberships: list[float]) -> tuple[str, float]:
    if not memberships:
        return STATUS_KURANG, 0.5
    # Geometric-ish aggregation: weakest link matters for shallot
    score = sum(memberships) / len(memberships)
    worst = min(memberships)
    composite = 0.55 * score + 0.45 * worst
    if composite >= 0.75 and worst >= 0.55:
        return STATUS_COCOK, composite
    if composite >= 0.45:
        return STATUS_KURANG, composite
    return STATUS_TIDAK, composite


def analyze_soil(
    soil_moisture: float,
    soil_temp: float,
    soil_ph: float,
    drainage_score: float = 0.7,
    organic_carbon: float | None = None,
    nitrogen: float | None = None,
    phosphorus: float | None = None,
    potassium: float | None = None,
    season: str | None = None,
    air_temp: float | None = None,
    air_humidity: float | None = None,
) -> dict[str, Any]:
    factors = [
        evaluate_moisture(soil_moisture),
        evaluate_temp(soil_temp if soil_temp is not None else (air_temp or 28)),
        evaluate_ph(soil_ph),
        evaluate_drainage(drainage_score if drainage_score is not None else 0.7),
    ]
    factors.extend(evaluate_npk(nitrogen, phosphorus, potassium))

    if organic_carbon is not None:
        m = _tri_membership(organic_carbon, 0.5, 1.5, 4.0, 8.0)
        cause = "Karbon organik memadai."
        actions: list[str] = []
        if organic_carbon < 1.5:
            cause = "Bahan organik rendah — struktur & retensi air lemah."
            actions = [
                "Tambah kompos / pupuk kandang matang 10–20 ton/ha.",
                "Rotasi dengan tanaman penutup tanah.",
            ]
        factors.append(
            FactorResult(
                "organic_carbon",
                "C-Organik",
                organic_carbon,
                "%",
                1.5,
                4.0,
                m,
                _severity(m),
                cause,
                actions,
            )
        )

    status, score = classify_from_memberships([f.membership for f in factors])
    limiting = [f for f in factors if f.severity != "ok"]
    limiting.sort(key=lambda x: x.membership)

    recommendations = build_recommendations(status, limiting, season)

    return {
        "method": "fuzzy",
        "status": status,
        "status_label": STATUS_LABEL[status],
        "score": round(score * 100, 1),
        "season": season,
        "factors": [
            {
                "name": f.name,
                "label": f.label,
                "value": f.value,
                "unit": f.unit,
                "ideal_min": f.ideal_min,
                "ideal_max": f.ideal_max,
                "membership": round(f.membership, 3),
                "severity": f.severity,
                "cause": f.cause,
                "actions": f.actions,
            }
            for f in factors
        ],
        "limiting_factors": [
            {"name": f.name, "label": f.label, "cause": f.cause, "severity": f.severity}
            for f in limiting
        ],
        "recommendations": recommendations,
        "air_temp": air_temp,
        "air_humidity": air_humidity,
    }


def build_recommendations(
    status: str,
    limiting: list[FactorResult],
    season: str | None,
) -> dict[str, Any]:
    if status == STATUS_COCOK:
        return {
            "summary": "Kondisi tanah cocok untuk ditanami bawang merah.",
            "fertilizers": [
                "Pupuk dasar: kompos/pupuk kandang matang 10–15 ton/ha",
                "Pemupukan berimbang NPK sesuai dosis lokal (uji tanah bila ada)",
            ],
            "ameliorants": ["Pertahankan mulsa organik untuk menjaga kelembapan"],
            "methods": [
                "Bedengan standar dengan drainase baik",
                "Irigasi tetes / siram sesuai kebutuhan 50–70% kelembapan",
                "Tanam pada musim kemarau dengan air irigasi terkontrol",
            ],
            "planting_window": _planting_window(season, ok=True),
            "priority_actions": ["Lanjutkan monitoring sensor harian", "Siapkan bibit umbi sehat"],
        }

    fertilizers: list[str] = []
    ameliorants: list[str] = []
    methods: list[str] = []
    priority: list[str] = []

    for f in limiting:
        priority.extend(f.actions[:2])
        if f.name == "soil_ph" and f.value is not None and f.value < 5.5:
            ameliorants.append("Kapur dolomit + bahan organik")
            fertilizers.append("Setelah pH naik: NPK berimbang + kompos")
        elif f.name == "soil_ph" and f.value is not None and f.value > 6.5:
            ameliorants.append("Bahan organik (kompos/pupuk kandang matang)")
        elif f.name == "soil_moisture" and f.value is not None and f.value < 50:
            methods.append("Drip irrigation / penyiraman terjadwal")
            ameliorants.append("Mulsa organik penahan evaporasi")
        elif f.name == "soil_moisture" and f.value is not None and f.value > 70:
            methods.append("Bedengan tinggi + saluran drainase")
            methods.append("Kurangi frekuensi irigasi")
        elif f.name == "drainage":
            methods.append("Perbaikan drainase: bedengan & saluran")
            ameliorants.append("Pasir/sekam untuk porositas")
        elif f.name in {"nitrogen", "phosphorus", "potassium"}:
            fertilizers.append("Pupuk kandang/kompos + pemupukan berimbang NPK sesuai uji tanah")
        elif f.name == "organic_carbon":
            fertilizers.append("Kompos / pupuk kandang matang 10–20 ton/ha")
            ameliorants.append("Bahan organik untuk struktur tanah")
        elif f.name == "soil_temp":
            methods.append("Manajemen naungan/mulsa sesuai suhu ekstrem")

    # Deduplicate preserving order
    def uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    summary = (
        "Tanah kurang cocok — perbaiki faktor pembatas utama sebelum tanam."
        if status == STATUS_KURANG
        else "Tanah tidak cocok — perlu tindakan ameliorasi dan perbaikan budidaya."
    )

    return {
        "summary": summary,
        "fertilizers": uniq(fertilizers) or ["Pemupukan berimbang sesuai hasil uji tanah"],
        "ameliorants": uniq(ameliorants) or ["Bahan organik untuk perbaikan sifat tanah"],
        "methods": uniq(methods) or ["Perbaiki drainase dan manajemen air bedengan"],
        "planting_window": _planting_window(season, ok=False),
        "priority_actions": uniq(priority)[:6],
    }


def _planting_window(season: str | None, ok: bool) -> str:
    season = (season or "").lower()
    if ok:
        if "hujan" in season:
            return "Musim hujan: tanam di bedengan tinggi; pantau drainase ketat. Ideal tetap musim kemarau."
        return "Jendela tanam baik — utamakan musim kemarau dengan irigasi terkontrol (April–Oktober tergantung wilayah)."
    if "hujan" in season:
        return "Tunda tanam hingga faktor pembatas diperbaiki; musim hujan memperbesar risiko genangan."
    return "Perbaiki tanah 2–4 minggu sebelum tanam; targetkan musim kemarau dengan irigasi."


def current_indonesia_season(month: int | None = None) -> str:
    from datetime import datetime

    month = month or datetime.now().month
    # Sederhana: Oktober–Maret cenderung hujan, April–September kemarau (variasi wilayah)
    if month in (10, 11, 12, 1, 2, 3):
        return "Musim Hujan"
    return "Musim Kemarau"
