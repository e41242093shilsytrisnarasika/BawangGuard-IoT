"""Machine learning classifier: Random Forest / Decision Tree (pure Python).

Tidak bergantung scikit-learn agar kompatibel Python 3.14+.
Model dilatih dari dataset sintetis berbasis aturan agronomi fuzzy.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .fuzzy_engine import (
    STATUS_COCOK,
    STATUS_KURANG,
    STATUS_LABEL,
    STATUS_TIDAK,
    analyze_soil,
    build_recommendations,
    FactorResult,
)

MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
RF_PATH = MODEL_DIR / "random_forest.json"
DT_PATH = MODEL_DIR / "decision_tree.json"

FEATURE_NAMES = [
    "soil_moisture",
    "soil_temp",
    "soil_ph",
    "drainage_score",
    "organic_carbon",
    "nitrogen",
    "phosphorus",
    "potassium",
]

LABELS = [STATUS_TIDAK, STATUS_KURANG, STATUS_COCOK]


def _entropy(labels: list[str]) -> float:
    n = len(labels)
    if n == 0:
        return 0.0
    counts = Counter(labels)
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c)


def _majority(labels: list[str]) -> str:
    return Counter(labels).most_common(1)[0][0]


def _best_split(rows: list[list[float]], labels: list[str], features: list[int]):
    best_gain = 0.0
    best = None
    base = _entropy(labels)
    n = len(labels)
    for fi in features:
        values = sorted({row[fi] for row in rows})
        if len(values) < 2:
            continue
        # sample thresholds between unique values
        thresholds = []
        for i in range(0, len(values) - 1, max(1, len(values) // 12)):
            thresholds.append((values[i] + values[i + 1]) / 2)
        for thr in thresholds:
            left_idx = [i for i, r in enumerate(rows) if r[fi] <= thr]
            right_idx = [i for i, r in enumerate(rows) if r[fi] > thr]
            if not left_idx or not right_idx:
                continue
            left_y = [labels[i] for i in left_idx]
            right_y = [labels[i] for i in right_idx]
            gain = base - (len(left_y) / n) * _entropy(left_y) - (len(right_y) / n) * _entropy(right_y)
            if gain > best_gain:
                best_gain = gain
                best = (fi, thr, left_idx, right_idx)
    return best, best_gain


def _build_tree(
    rows: list[list[float]],
    labels: list[str],
    depth: int = 0,
    max_depth: int = 6,
    n_features: int | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    rng = rng or random.Random(42)
    if depth >= max_depth or len(set(labels)) == 1 or len(labels) < 8:
        return {"leaf": True, "label": _majority(labels), "counts": dict(Counter(labels))}

    feat_idx = list(range(len(FEATURE_NAMES)))
    if n_features is not None and n_features < len(feat_idx):
        feat_idx = rng.sample(feat_idx, n_features)

    split, gain = _best_split(rows, labels, feat_idx)
    if split is None or gain < 1e-6:
        return {"leaf": True, "label": _majority(labels), "counts": dict(Counter(labels))}

    fi, thr, left_idx, right_idx = split
    left_rows = [rows[i] for i in left_idx]
    left_y = [labels[i] for i in left_idx]
    right_rows = [rows[i] for i in right_idx]
    right_y = [labels[i] for i in right_idx]
    return {
        "leaf": False,
        "feature": fi,
        "feature_name": FEATURE_NAMES[fi],
        "threshold": thr,
        "left": _build_tree(left_rows, left_y, depth + 1, max_depth, n_features, rng),
        "right": _build_tree(right_rows, right_y, depth + 1, max_depth, n_features, rng),
    }


def _predict_tree(tree: dict[str, Any], row: list[float]) -> str:
    node = tree
    while not node.get("leaf"):
        if row[node["feature"]] <= node["threshold"]:
            node = node["left"]
        else:
            node = node["right"]
    return node["label"]


def _predict_tree_proba(tree: dict[str, Any], row: list[float]) -> dict[str, float]:
    node = tree
    while not node.get("leaf"):
        if row[node["feature"]] <= node["threshold"]:
            node = node["left"]
        else:
            node = node["right"]
    counts = node.get("counts") or {node["label"]: 1}
    total = sum(counts.values()) or 1
    return {lab: counts.get(lab, 0) / total for lab in LABELS}


def _synthetic_dataset(n: int = 900, seed: int = 42) -> tuple[list[list[float]], list[str]]:
    rng = random.Random(seed)
    X: list[list[float]] = []
    y: list[str] = []
    for _ in range(n):
        moisture = rng.uniform(15, 95)
        temp = rng.uniform(18, 40)
        ph = rng.uniform(4.2, 8.0)
        drainage = rng.uniform(0.1, 1.0)
        oc = rng.uniform(0.4, 5.5)
        n_val = rng.uniform(10, 100)
        p_val = rng.uniform(5, 90)
        k_val = rng.uniform(10, 100)
        result = analyze_soil(
            soil_moisture=moisture,
            soil_temp=temp,
            soil_ph=ph,
            drainage_score=drainage,
            organic_carbon=oc,
            nitrogen=n_val,
            phosphorus=p_val,
            potassium=k_val,
        )
        X.append([moisture, temp, ph, drainage, oc, n_val, p_val, k_val])
        y.append(result["status"])
    return X, y


def _feature_importance_rf(trees: list[dict[str, Any]]) -> dict[str, float]:
    scores = {name: 0.0 for name in FEATURE_NAMES}

    def walk(node: dict[str, Any]) -> None:
        if node.get("leaf"):
            return
        scores[FEATURE_NAMES[node["feature"]]] += 1.0
        walk(node["left"])
        walk(node["right"])

    for t in trees:
        walk(t)
    total = sum(scores.values()) or 1.0
    return {k: round(v / total, 4) for k, v in scores.items()}


def train_models(force: bool = False) -> dict[str, Any]:
    if RF_PATH.exists() and DT_PATH.exists() and not force:
        return {"trained": False, "message": "Model sudah ada"}

    X, y = _synthetic_dataset()
    rng = random.Random(42)

    dt = _build_tree(X, y, max_depth=6, n_features=None, rng=rng)
    trees = []
    n_features = max(2, int(math.sqrt(len(FEATURE_NAMES))))
    for i in range(25):
        # bootstrap sample
        idx = [rng.randrange(len(X)) for _ in range(len(X))]
        bx = [X[j] for j in idx]
        by = [y[j] for j in idx]
        trees.append(_build_tree(bx, by, max_depth=5, n_features=n_features, rng=random.Random(100 + i)))

    RF_PATH.write_text(
        json.dumps({"features": FEATURE_NAMES, "trees": trees, "labels": LABELS}, ensure_ascii=False),
        encoding="utf-8",
    )
    DT_PATH.write_text(
        json.dumps({"features": FEATURE_NAMES, "tree": dt, "labels": LABELS}, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "trained": True,
        "samples": len(y),
        "class_balance": dict(Counter(y)),
        "n_trees": len(trees),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        train_models(force=True)
    return json.loads(path.read_text(encoding="utf-8"))


def _vector(
    soil_moisture: float,
    soil_temp: float,
    soil_ph: float,
    drainage_score: float = 0.7,
    organic_carbon: float | None = None,
    nitrogen: float | None = None,
    phosphorus: float | None = None,
    potassium: float | None = None,
) -> list[float]:
    return [
        soil_moisture,
        soil_temp,
        soil_ph,
        drainage_score if drainage_score is not None else 0.7,
        organic_carbon if organic_carbon is not None else 2.0,
        nitrogen if nitrogen is not None else 50.0,
        phosphorus if phosphorus is not None else 40.0,
        potassium if potassium is not None else 50.0,
    ]


def predict_ml(
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
    model_name: str = "random_forest",
) -> dict[str, Any]:
    fuzzy = analyze_soil(
        soil_moisture=soil_moisture,
        soil_temp=soil_temp,
        soil_ph=soil_ph,
        drainage_score=drainage_score,
        organic_carbon=organic_carbon,
        nitrogen=nitrogen,
        phosphorus=phosphorus,
        potassium=potassium,
        season=season,
        air_temp=air_temp,
        air_humidity=air_humidity,
    )
    fuzzy_status = fuzzy["status"]
    row = _vector(
        soil_moisture,
        soil_temp,
        soil_ph,
        drainage_score,
        organic_carbon,
        nitrogen,
        phosphorus,
        potassium,
    )

    if model_name == "decision_tree":
        bundle = _load_json(DT_PATH)
        tree = bundle["tree"]
        status = _predict_tree(tree, row)
        proba = _predict_tree_proba(tree, row)
        importances = {FEATURE_NAMES[i]: 0.0 for i in range(len(FEATURE_NAMES))}

        def walk(node: dict[str, Any]) -> None:
            if node.get("leaf"):
                return
            importances[FEATURE_NAMES[node["feature"]]] += 1
            walk(node["left"])
            walk(node["right"])

        walk(tree)
        total = sum(importances.values()) or 1
        importances = {k: round(v / total, 4) for k, v in importances.items()}
    else:
        bundle = _load_json(RF_PATH)
        trees = bundle["trees"]
        votes = [_predict_tree(t, row) for t in trees]
        status = Counter(votes).most_common(1)[0][0]
        proba = {lab: votes.count(lab) / len(votes) for lab in LABELS}
        importances = _feature_importance_rf(trees)

    conf = proba.get(status, 0.0)
    limiting = [
        FactorResult(
            f["name"],
            f["label"],
            f["value"],
            f["unit"],
            f["ideal_min"],
            f["ideal_max"],
            f["membership"],
            f["severity"],
            f["cause"],
            f["actions"],
        )
        for f in fuzzy["factors"]
        if f["severity"] != "ok"
    ]

    fuzzy["method"] = model_name
    fuzzy["status"] = status
    fuzzy["status_label"] = STATUS_LABEL[status]
    fuzzy["score"] = round(conf * 100, 1)
    fuzzy["recommendations"] = build_recommendations(status, limiting, season)
    fuzzy["limiting_factors"] = [
        {"name": f.name, "label": f.label, "cause": f.cause, "severity": f.severity}
        for f in limiting
    ]
    fuzzy["ml"] = {
        "model": model_name,
        "confidence": round(conf * 100, 1),
        "probabilities": {k: round(v * 100, 1) for k, v in proba.items()},
        "feature_importance": importances,
        "fuzzy_status": fuzzy_status,
    }
    return fuzzy
