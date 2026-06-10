---
id: index
title: DTX-AI Overview
slug: /overview
sidebar_position: 1
---

# DTX-AI — Smart Warehouse Anomaly Detection

**Version:** v2.1 &nbsp;|&nbsp; **Branch:** `main` &nbsp;|&nbsp; **Date:** June 2026

---

## What is DTX-AI?

DTX-AI is a full-stack AI system for smart warehouse anomaly detection with built-in **Explainable AI (XAI)**. It ingests 19-channel Isaac-Sim-style telemetry from warehouse equipment, runs it through trained machine-learning models to detect faults, generates human-readable SHAP-based explanations, and surfaces everything to operators through a live React dashboard.

```
Sensor frame → FastAPI → AI Pipeline (SHAP + ML) → SQLite + WebSocket → React Dashboard
                                                        │
                                                        └─► TwinUpdate ─► Isaac Sim
```

---

## Key Features

| Feature | Details |
|---|---|
| **Real-time anomaly detection** | 7 model families: Random Forest / LightGBM / XGBoost / TabNet / CNN / Bi-LSTM / LSTM-AE with classification head |
| **6-class fault taxonomy** | `nominal`, `bearing_wear`, `overheat`, `overload`, `pressure_fault`, `wheel_slip` |
| **Explainable AI** | SHAP TreeExplainer — per-feature attribution for every prediction |
| **Live dashboard** | React + WebSocket push — zero-refresh operator UI, with a Demo Control panel to start/stop demos |
| **Operator workflow** | Acknowledge → Assign → Escalate → Resolve |
| **Dataset replay validation** | Replay the leakage-safe per-episode temporal demo holdout, track running accuracy vs ground truth |
| **IRL hardware demo** | ESP32 + DS18B20 + BMP280 node (`HW/`) streams live readings through the same pipeline |
| **Isaac Sim ready** | 19-channel `EventIn` schema matches the sim's joint / IMU / drive outputs |

---

## System at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  Data Sources                                               │
│  scripts/replay_dataset_demo.py ──► POST /events/  (HTTP)   │
│  HW/ ESP32 ─► scripts/hw_demo_bridge.py ─► POST /events/    │
│  Isaac Sim adapter              ──► POST /events/  (HTTP)   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP :8000
┌──────────────────────────▼──────────────────────────────────┐
│  apps/api  (FastAPI + uvicorn)                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  services/ai  (in-process)                           │   │
│  │  pipeline → detector → explainer → SHAP              │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────────────────────────┘
           │ WebSocket + HTTP
┌──────────▼──────────────────────────────────────────────────┐
│  apps/dashboard  (React + Vite :5173)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, uvicorn, aiosqlite, Pydantic v2 |
| ML — trees | LightGBM 4.6, XGBoost 3.2, scikit-learn 1.8 |
| ML — deep | PyTorch 2.11 + CUDA 12.8, pytorch-tabnet ≥ 4.1 |
| XAI | SHAP TreeExplainer |
| Frontend | React 18, Vite, TailwindCSS, Recharts, React Router v6 |
| Database | SQLite (dev) |
| Schemas | Pydantic v2 shared package (`dtx-ai-shared`) |

---

## Quick Start

```bash
git clone https://github.com/YKesX/DTX-AI.git
cd DTX-AI
bash scripts/setup.sh
# PyTorch separately, from the official CUDA wheel index:
source .venv/bin/activate && pip install torch --index-url https://download.pytorch.org/whl/cu128
bash scripts/run_dev.sh
```

Dashboard → `http://localhost:5173`
API docs → `http://localhost:8000/docs`

Replay the leakage-safe demo holdout (the temporal tail of every fault run) through the live pipeline:

```bash
bash scripts/run_demo.sh
```

Or start a demo from the dashboard's AI Validation page via the **Demo Control** panel — including the IRL hardware demo ([Hardware Demo](/docs/hardware-demo)).

---

## Project Context

Graduation project at **Atılım University, Computer Engineering**, developed as a multi-person capstone team. The `main` branch contains the active 19-channel schema, 7 retrained model families on the leakage-safe canonical split, the dataset replay validation flow, and the ESP32 hardware demo.
