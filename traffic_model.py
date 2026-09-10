"""Explainable ML model and signal optimization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

DIRECTIONS = ("NORTH", "SOUTH", "EAST", "WEST")
CONGESTION_ORDER = ("LOW", "MEDIUM", "HIGH")
FEATURES = [
    "vehicle_count",
    "average_speed",
    "waiting_time",
    "traffic_density",
    "time_of_day",
    "day_of_week",
    "queue_length",
    "pedestrian_count",
    "weather_condition",
    "road_incident",
]

WEATHER_ENCODING = {"CLEAR": 0, "RAIN": 1, "FOG": 2}


def build_training_data(samples: int = 360, seed: int = 7) -> pd.DataFrame:
    """Create reproducible synthetic examples suitable for a classroom demo."""
    rng = np.random.default_rng(seed)
    vehicle_count = rng.integers(0, 81, samples)
    average_speed = np.clip(rng.normal(35 - vehicle_count * 0.22, 5, samples), 3, 55)
    waiting_time = np.clip(vehicle_count * 0.28 + rng.normal(2, 2.5, samples), 0, 45)
    traffic_density = np.clip(vehicle_count / 80 + rng.normal(0, 0.06, samples), 0, 1)
    time_of_day = rng.integers(0, 24, samples)
    day_of_week = rng.integers(0, 7, samples)
    queue_length = np.clip(vehicle_count * 0.7 + waiting_time * 0.6 + rng.normal(0, 3, samples), 0, 80)
    pedestrian_count = rng.integers(0, 31, samples)
    weather_condition = rng.integers(0, 3, samples)
    road_incident = rng.integers(0, 2, samples)
    score = (
        vehicle_count * 0.5
        + waiting_time * 1.4
        + traffic_density * 35
        - average_speed * 0.25
        + queue_length * 0.25
        + pedestrian_count * 0.08
        + weather_condition * 3
        + road_incident * 12
    )
    congestion = np.select([score < 36, score < 68], ["LOW", "MEDIUM"], default="HIGH")
    return pd.DataFrame(
        {
            "vehicle_count": vehicle_count,
            "average_speed": average_speed.round(2),
            "waiting_time": waiting_time.round(2),
            "traffic_density": traffic_density.round(3),
            "time_of_day": time_of_day,
            "day_of_week": day_of_week,
            "queue_length": queue_length.round(2),
            "pedestrian_count": pedestrian_count,
            "weather_condition": weather_condition,
            "road_incident": road_incident,
            "congestion": congestion,
        }
    )


def train_model(training_data: pd.DataFrame | None = None) -> DecisionTreeClassifier:
    """Train a shallow decision tree so the AIML decision remains explainable."""
    data = training_data if training_data is not None else build_training_data()
    model = DecisionTreeClassifier(max_depth=4, random_state=7)
    model.fit(data[FEATURES], data["congestion"])
    return model


def load_or_create_training_data(csv_path: Path) -> pd.DataFrame:
    if csv_path.exists():
        data = pd.read_csv(csv_path)
        if set(FEATURES + ["congestion"]).issubset(data.columns):
            return data
    data = build_training_data()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(csv_path, index=False)
    return data


def predict_congestion(model: DecisionTreeClassifier, state: Dict[str, float]) -> str:
    values = pd.DataFrame([{feature: state.get(feature, 0) for feature in FEATURES}])
    return str(model.predict(values)[0])


def predict_with_confidence(model: DecisionTreeClassifier, state: Dict[str, float]) -> Tuple[str, float]:
    values = pd.DataFrame([{feature: state.get(feature, 0) for feature in FEATURES}])
    prediction = str(model.predict(values)[0])
    probabilities = model.predict_proba(values)[0]
    class_index = list(model.classes_).index(prediction)
    return prediction, float(probabilities[class_index])


def congestion_score(label: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(label, 1)


def optimize_signal_plan(
    direction_states: Dict[str, Dict[str, float]], model: DecisionTreeClassifier
) -> Tuple[str, Dict[str, str], Dict[str, int]]:
    """Choose the most congested approach and allocate a safe 15-60 second green."""
    predictions = {
        direction: predict_congestion(model, state)
        for direction, state in direction_states.items()
    }
    def priority_score(direction: str) -> float:
        state = direction_states[direction]
        return (
            congestion_score(predictions[direction]) * 40
            + min(30, state.get("vehicle_count", 0) / 2)
            + min(20, state.get("waiting_time", 0))
            + min(20, state.get("queue_length", 0) / 2)
            + (100 if state.get("emergency", 0) else 0)
        )

    priority = max(direction_states, key=priority_score)
    durations = {}
    for direction, state in direction_states.items():
        demand = (
            state.get("vehicle_count", 0)
            + state.get("waiting_time", 0) * 0.8
            + state.get("queue_length", 0) * 0.5
            + state.get("pedestrian_count", 0) * 0.15
        )
        base = 15 if predictions[direction] == "LOW" else 30 if predictions[direction] == "MEDIUM" else 45
        durations[direction] = int(np.clip(base + demand * 0.12, 15, 60))
    durations[priority] = min(60, durations[priority] + 8)
    return priority, predictions, durations
