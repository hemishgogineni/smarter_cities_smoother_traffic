"""Traffic state, signal timing, and comparison metrics for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

import numpy as np

from traffic_model import DIRECTIONS, optimize_signal_plan, predict_with_confidence


@dataclass
class Vehicle:
    position: float
    lane: int
    color: str


@dataclass
class DirectionState:
    vehicle_count: int = 10
    waiting_time: float = 0.0
    average_speed: float = 28.0
    traffic_density: float = 0.2
    congestion: str = "LOW"
    queue_length: float = 0.0
    pedestrian_count: int = 0
    incident: bool = False
    emergency: bool = False
    vehicles: List[Vehicle] = field(default_factory=list)


class TrafficSimulation:
    # Fallback stop-line fraction used before the canvas geometry is known.
    STOP_LINE_POSITION = 0.32
    INITIAL_STOP_BUFFER = 0.05
    # Spacing between queued vehicles and how many we draw per approach.
    QUEUE_GAP = 0.05
    MAX_VISUAL_VEHICLES = 8

    def __init__(self, model, seed: int = 12):
        self.model = model
        self.rng = np.random.default_rng(seed)
        self.states: Dict[str, DirectionState] = {
            direction: DirectionState(vehicle_count=int(value))
            for direction, value in zip(DIRECTIONS, (35, 28, 12, 8))
        }
        self.fixed_durations = {direction: 30 for direction in DIRECTIONS}
        self.green_durations = dict(self.fixed_durations)
        self.mode = "FIXED SIGNAL MODE"
        self.manual_control = False
        self.auto_ai = False
        self.weather = "CLEAR"
        self.emergency_direction = None
        self.emergency_elapsed = 0.0
        self.incident_direction = None
        self.ai_elapsed = 0.0
        self.priority = "NORTH"
        self.phase_index = 0
        self.phase_elapsed = 0.0
        self.time_elapsed = 0.0
        # Per-approach stop-line position (0..1 along the approach); the dashboard
        # updates these from the real canvas geometry on every redraw.
        self.stop_fraction = {direction: self.STOP_LINE_POSITION for direction in DIRECTIONS}
        self.history = []
        self.predictions = {direction: "LOW" for direction in DIRECTIONS}
        self.confidences = {direction: 0.0 for direction in DIRECTIONS}
        self.forecast = ["LOW", "LOW", "LOW"]
        self.decision_log = []
        self.vehicles_cleared = 0
        self.fixed_wait_total = 0.0
        self.ai_wait_total = 0.0
        self.fixed_idle_total = 0.0
        self.ai_idle_total = 0.0
        self.fixed_cleared = 0
        self.ai_cleared = 0
        self.reset_vehicle_visuals()
        self.update_predictions()

    @property
    def active_direction(self) -> str:
        return DIRECTIONS[self.phase_index]

    def reset_vehicle_visuals(self) -> None:
        colors = ("#5eead4", "#fbbf24", "#60a5fa", "#fb7185")
        for index, direction in enumerate(DIRECTIONS):
            state = self.states[direction]
            anchor = self.stop_fraction[direction]
            state.vehicles = [
                Vehicle(
                    position=float(self.rng.uniform(0.06, max(0.1, anchor - 0.03))),
                    lane=index % 2,
                    color=colors[index],
                )
                for _ in range(min(state.vehicle_count, self.MAX_VISUAL_VEHICLES))
            ]

    def update_predictions(self) -> None:
        for direction, state in self.states.items():
            state.traffic_density = min(1.0, state.vehicle_count / 60)
            weather_penalty = {"CLEAR": 0, "RAIN": 5, "FOG": 10}[self.weather]
            state.average_speed = max(4.0, 42 - state.traffic_density * 28 - state.waiting_time * 0.12 - weather_penalty)
            state.queue_length = float(np.clip(state.vehicle_count * 0.72 + state.waiting_time * 0.45, 0, 80))
            prediction, confidence = predict_with_confidence(self.model, self.feature_state(state))
            state.congestion = prediction
            self.predictions[direction] = prediction
            self.confidences[direction] = confidence
        self.forecast = self._forecast_labels()

    def feature_state(self, state: DirectionState) -> Dict[str, float]:
        return {
            "vehicle_count": state.vehicle_count,
            "average_speed": state.average_speed,
            "waiting_time": state.waiting_time,
            "traffic_density": state.traffic_density,
            "time_of_day": 17,
            "day_of_week": 2,
            "queue_length": state.queue_length,
            "pedestrian_count": state.pedestrian_count,
            "weather_condition": {"CLEAR": 0, "RAIN": 1, "FOG": 2}[self.weather],
            "road_incident": int(state.incident),
            "emergency": int(state.emergency),
        }

    def update(self, seconds: float = 0.5) -> None:
        self.time_elapsed += seconds
        self.phase_elapsed += seconds
        self.ai_elapsed += seconds
        if self.emergency_direction:
            self.emergency_elapsed += seconds
            if self.emergency_elapsed >= 15:
                self.clear_emergency()
        if self.auto_ai and not self.manual_control and self.ai_elapsed >= 7:
            self.ai_elapsed = 0.0
            self.optimize()
        if not self.manual_control and self.phase_elapsed >= self.green_durations[self.active_direction]:
            self.phase_index = (self.phase_index + 1) % len(DIRECTIONS)
            self.phase_elapsed = 0.0

        for direction, state in self.states.items():
            weather_arrival_bonus = {"CLEAR": 0.0, "RAIN": 0.04, "FOG": 0.08}[self.weather]
            arrivals = int(self.rng.random() < 0.25 + weather_arrival_bonus)
            if self.rng.random() < 0.08:
                arrivals += 1
            departures = 0
            if direction == self.active_direction and self.phase_elapsed > 2:
                capacity_factor = 0.45 if state.incident else 1.0
                departures = min(state.vehicle_count, int(self.rng.integers(0, 3) * capacity_factor))
                self.vehicles_cleared += departures
                self.ai_cleared += departures
            state.vehicle_count = max(0, min(80, state.vehicle_count + arrivals - departures))
            if direction == self.active_direction:
                state.waiting_time = max(0.0, state.waiting_time - seconds * 0.25)
            else:
                state.waiting_time = min(120.0, state.waiting_time + seconds * state.vehicle_count / 75 * (1.25 if state.incident else 1.0))
            state.pedestrian_count = int(np.clip(state.pedestrian_count + self.rng.integers(-1, 2), 0, 40))
            self._move_visual_vehicles(direction, state, seconds)
        self.update_predictions()
        self._record_comparison(seconds)
        self._record_history()

    def _move_visual_vehicles(self, direction: str, state: DirectionState, seconds: float) -> None:
        # Only a GREEN or clearing YELLOW approach lets vehicles roll forward.
        moving = self.signal_status(direction) in ("GREEN", "YELLOW")
        step = 0.20 * seconds
        anchor = self.stop_fraction[direction]
        if moving:
            for vehicle in state.vehicles:
                vehicle.position += step
        else:
            # Red approach: any vehicle that already reached the stop line has
            # cleared the junction, the rest wait in a staggered queue behind it.
            state.vehicles = [vehicle for vehicle in state.vehicles if vehicle.position <= anchor + 0.02]
            queue = sorted(state.vehicles, key=lambda vehicle: vehicle.position, reverse=True)
            for slot, vehicle in enumerate(queue):
                limit = max(0.0, anchor - slot * self.QUEUE_GAP)
                if vehicle.position > limit:
                    vehicle.position = limit
        state.vehicles = [vehicle for vehicle in state.vehicles if vehicle.position < 1.05]
        while len(state.vehicles) < min(state.vehicle_count, self.MAX_VISUAL_VEHICLES):
            state.vehicles.append(
                Vehicle(
                    position=float(self.rng.uniform(0.0, 0.1)),
                    lane=int(self.rng.integers(0, 2)),
                    color="#dbeafe",
                )
            )

    def add_traffic(self) -> None:
        for direction in DIRECTIONS:
            increase = int(self.rng.integers(2, 7))
            self.states[direction].vehicle_count = min(80, self.states[direction].vehicle_count + increase)
        self.update_predictions()
        self._record_history()

    def set_auto_ai(self, enabled: bool) -> None:
        self.auto_ai = enabled
        if enabled:
            self.manual_control = False
            self.mode = "AI AUTO MODE"
            self.optimize()
        else:
            self.mode = "AI OPTIMIZED MODE" if self.priority else "FIXED SIGNAL MODE"
        self._log("AUTO AI", "enabled" if enabled else "disabled")

    def set_weather(self, weather: str) -> None:
        if weather not in ("CLEAR", "RAIN", "FOG"):
            raise ValueError(f"Unknown weather: {weather}")
        self.weather = weather
        self.update_predictions()
        self._log("WEATHER", f"{weather} simulated effects active")

    def set_incident(self, direction: str) -> None:
        self.clear_incident()
        self.incident_direction = direction
        self.states[direction].incident = True
        self.states[direction].waiting_time = min(120, self.states[direction].waiting_time + 5)
        self.update_predictions()
        self._log("INCIDENT", f"{direction} capacity reduced")

    def clear_incident(self) -> None:
        if self.incident_direction:
            self.states[self.incident_direction].incident = False
        self.incident_direction = None

    def trigger_emergency(self, direction: str) -> None:
        self.clear_emergency()
        self.emergency_direction = direction
        self.states[direction].emergency = True
        self.manual_control = False
        self.phase_index = DIRECTIONS.index(direction)
        self.phase_elapsed = 0.0
        self.emergency_elapsed = 0.0
        self.green_durations[direction] = 15
        self.mode = "EMERGENCY PRIORITY"
        self.priority = direction
        self._log("EMERGENCY", f"{direction} priority activated")

    def clear_emergency(self) -> None:
        if self.emergency_direction:
            self.states[self.emergency_direction].emergency = False
        self.emergency_direction = None
        self.emergency_elapsed = 0.0
        self.optimize()

    def apply_scenario(self, scenario: str) -> None:
        self.reset()
        if scenario == "Rush Hour":
            for state in self.states.values():
                state.vehicle_count = min(80, state.vehicle_count + 22)
        elif scenario == "Emergency Vehicle":
            self.trigger_emergency("EAST")
        elif scenario == "Road Incident":
            self.set_incident("WEST")
        elif scenario == "Heavy Rain":
            self.set_weather("RAIN")
        self.reset_vehicle_visuals()
        self.update_predictions()

    def _forecast_labels(self) -> List[str]:
        average = self.average_congestion
        trend = np.mean([point[2] for point in self.history[-5:]]) if self.history else average
        return [self._label_from_score(np.clip(trend + step * (average - trend) * 0.35, 1, 3)) for step in (1, 2, 3)]

    @staticmethod
    def _label_from_score(score: float) -> str:
        return "LOW" if score < 1.5 else "MEDIUM" if score < 2.35 else "HIGH"

    def optimize(self) -> None:
        self.manual_control = False
        feature_states = {direction: self.feature_state(state) for direction, state in self.states.items()}
        self.priority, predictions, durations = optimize_signal_plan(feature_states, self.model)
        if self.emergency_direction:
            self.priority = self.emergency_direction
            self.phase_index = DIRECTIONS.index(self.priority)
        self.green_durations = durations
        self.mode = "EMERGENCY PRIORITY" if self.emergency_direction else ("AI AUTO MODE" if self.auto_ai else "AI OPTIMIZED MODE")
        for direction, prediction in predictions.items():
            self.states[direction].congestion = prediction
        self._log(self.priority, f"{predictions[self.priority]} congestion | green {durations[self.priority]} sec")
        self._record_history()

    def set_manual_control(self, enabled: bool) -> None:
        self.manual_control = enabled
        self.phase_elapsed = 0.0
        self.mode = "MANUAL CONTROL MODE" if enabled else "FIXED SIGNAL MODE"
        self._record_history()

    def set_manual_direction(self, direction: str) -> None:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unknown direction: {direction}")
        self.manual_control = True
        self.phase_index = DIRECTIONS.index(direction)
        self.phase_elapsed = 0.0
        self.priority = direction
        self.mode = "MANUAL CONTROL MODE"
        self._record_history()

    def reset(self) -> None:
        self.__init__(self.model)

    def signal_status(self, direction: str) -> str:
        if direction != self.active_direction:
            return "RED"
        if self.manual_control:
            return "GREEN"
        return "YELLOW" if self.phase_elapsed >= self.green_durations[direction] - 3 else "GREEN"

    def _record_history(self) -> None:
        average_wait = self.average_waiting_time
        average_congestion = sum({"LOW": 1, "MEDIUM": 2, "HIGH": 3}[state.congestion] for state in self.states.values()) / 4
        average_queue = sum(state.queue_length for state in self.states.values()) / len(self.states)
        self.history.append((self.time_elapsed, average_wait, average_congestion, average_queue))
        self.history = self.history[-60:]

    def _record_comparison(self, seconds: float) -> None:
        fixed_direction = DIRECTIONS[int(self.time_elapsed // 30) % len(DIRECTIONS)]
        fixed_wait = sum(state.vehicle_count for direction, state in self.states.items() if direction != fixed_direction) * seconds / 75
        self.fixed_wait_total += fixed_wait
        self.ai_wait_total += self.average_waiting_time * seconds / 10
        self.fixed_idle_total += fixed_wait * max(1, self.total_vehicles)
        self.ai_idle_total += self.idle_time * seconds / 10
        self.fixed_cleared += 1 if fixed_direction == self.active_direction and self.total_vehicles else 0

    @property
    def average_waiting_time(self) -> float:
        return sum(state.waiting_time for state in self.states.values()) / len(self.states)

    @property
    def average_congestion(self) -> float:
        return sum({"LOW": 1, "MEDIUM": 2, "HIGH": 3}[state.congestion] for state in self.states.values()) / len(self.states)

    @property
    def total_vehicles(self) -> int:
        return sum(state.vehicle_count for state in self.states.values())

    @property
    def idle_time(self) -> float:
        return sum(state.waiting_time * state.vehicle_count for state in self.states.values())

    @property
    def emission_reduction(self) -> float:
        baseline_idle = max(1.0, self.fixed_idle_total)
        return float(np.clip((baseline_idle - self.ai_idle_total) / baseline_idle * 100, 0, 100))

    def comparison(self) -> Dict[str, Dict[str, float]]:
        return {
            "fixed": {"wait": self.fixed_wait_total, "congestion": min(3, self.average_congestion), "idle": self.fixed_idle_total, "cleared": self.fixed_cleared},
            "optimized": {"wait": self.ai_wait_total, "congestion": self.average_congestion, "idle": self.ai_idle_total, "cleared": self.ai_cleared},
        }

    def _log(self, subject: str, detail: str) -> None:
        self.decision_log.append(f"{datetime.now():%H:%M:%S}  {subject}  {detail}")
        self.decision_log = self.decision_log[-12:]
