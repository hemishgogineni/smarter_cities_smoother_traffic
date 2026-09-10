# Smarter Cities, Smoother Traffic

An offline Python/Tkinter AIML demonstration for **Smart Traffic Intelligence & Adaptive Signal Control**. It simulates a four-way junction, classifies congestion with an explainable Decision Tree, and adapts one safe signal phase at a time.

## Project Overview

This is a classroom simulation, not a real traffic-control system. Traffic demand, vehicle movement, weather effects, incidents, pedestrians, and training data are synthetic and generated locally.

## Problem Statement

Fixed signals can give the same green time to every road even when demand is uneven. This creates longer queues, waiting, idling, and estimated emissions.

## Objectives

- Demonstrate an explainable AIML traffic pipeline.
- Predict LOW, MEDIUM, or HIGH congestion for every approach.
- Allocate safe 15-60 second green durations from live simulated demand.
- Compare measured simulation outcomes with a fixed-signal baseline.

## Existing Features

- Dark smart-city dashboard with four traffic cards.
- Animated vehicles, signals, junction canvas, chart, and live metrics.
- Start/Pause, Add Traffic, AI Optimize, Manual Control, speed selection, and Reset.

## Advanced Features

- Auto AI Mode re-evaluates traffic every seven simulated seconds.
- Prediction confidence from `predict_proba()`.
- Live "Why did AI choose this?" explanation and decision log.
- Queue length, pedestrian demand, weather, road incidents, and emergency priority.
- Short-term forecast for the next 30, 60, and 90 simulated seconds.
- Demo scenarios for normal traffic, rush hour, emergency, incidents, and heavy rain.
- Fixed versus AI accumulators for waiting, idle time, and vehicles cleared.

## AIML Architecture

```text
Simulated traffic data
        |
Decision Tree congestion prediction + confidence
        |
Normalized priority analysis
        |
Adaptive one-direction signal timing
        |
Simulated traffic response and measured comparison
```

## Decision Tree

`traffic_model.py` trains a shallow scikit-learn `DecisionTreeClassifier`. Features are `vehicle_count`, `average_speed`, `waiting_time`, `traffic_density`, `time_of_day`, `day_of_week`, `queue_length`, `pedestrian_count`, `weather_condition`, and `road_incident`. Weather and categorical values use simple numeric encodings. The generated CSV is synthetic training data, never real city data.

## Adaptive Signal Optimization

The optimizer predicts each direction, then scores congestion, vehicles, waiting time, queue length, pedestrian demand, and emergency status. Green times remain between 15 and 60 seconds. Only the active direction is green; its final three seconds are yellow. Auto AI waits for its evaluation interval rather than recalculating every animation frame.

## Optional Q-learning

Q-learning was intentionally not placed in the live controller. The current weighted optimizer is deterministic, explainable, and reliable for a short CIA demonstration. A future experiment can compare a NumPy Q-table against this baseline without replacing the Decision Tree.

## Emergency Priority

The emergency controls immediately select a direction, keep other approaches red, and show an emergency reason in the AI panel. Clearing emergency priority returns control to Auto AI when it is enabled.

## Incident Handling

A road incident marks one direction, reduces its simulated departure capacity, and increases waiting time. The incident indicator and congestion prediction use the same current state.

## Weather Simulation

CLEAR is normal. RAIN lowers speed and slightly increases arrivals. FOG lowers speed further and increases congestion pressure. These are simulated effects, not weather measurements.

## Traffic Forecasting

The dashboard uses recent congestion history and the current trend to produce lightweight explainable labels for 30, 60, and 90 simulated seconds. It is not a deep-learning forecast.

## Fixed vs AI Evaluation

Every update adds current state costs to both a fixed 30-second rotation baseline and the active simulation policy. Waiting, idle time, and cleared vehicles accumulate from simulation events instead of being multiplied by arbitrary percentages. The two policies share the same generated arrivals and environment conditions as closely as this single-run simulation allows.

## Emission Estimation

Estimated emission reduction is derived only from the difference between accumulated simulated idle-time costs. It is explicitly an estimate, not measured pollution or a real-world emissions result.

## Installation

Python 3.10 or newer is recommended.

```bash
cd ~/Documents/Smarter_Cities_Smoother_Traffic
python -m pip install -r requirements.txt
```

Tkinter is included with most macOS Python installations.

## How to Run

```bash
cd ~/Documents/Smarter_Cities_Smoother_Traffic
python main.py
```

## CIA Demo Procedure

1. Start the simulation and point out the four approach cards and live junction.
2. Press **AI OPTIMIZE** and explain the prediction, confidence, priority score, and green duration.
3. Enable **AUTO AI MODE**, press **ADD TRAFFIC**, and show the decision log changing after the evaluation interval.
4. Choose **Rush Hour** or **Heavy Rain** and compare the forecast and metrics.
5. Trigger an emergency direction, then demonstrate **Road Incident** and **CLEAR INCIDENT**.
6. Show Fixed vs AI, estimated idle reduction, and the chart before pressing **RESET**.

## Limitations

This is an offline educational simulation. It does not use cameras, sensors, real-time city data, real pollution measurements, cloud services, or production safety validation. The fixed comparison is a same-run simulated baseline, not a controlled real-world experiment.

## Future Enhancements

- Add a separately evaluated NumPy Q-learning policy.
- Add richer turn lanes and a dedicated pedestrian phase.
- Compare repeated seeded runs statistically.
- Train and validate against an appropriately documented public dataset.
