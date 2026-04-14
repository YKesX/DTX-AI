---
id: index
title: DTX-AI Overview
slug: /overview
sidebar_position: 1
---

# DTX-AI — Smart Warehouse Anomaly Detection

**Version:** 0.2.0 &nbsp;|&nbsp; **Branch:** `feat/dashboard-ops-validation` &nbsp;|&nbsp; **Date:** April 2026

---

## What is DTX-AI?

DTX-AI is a full-stack AI system for smart warehouse anomaly detection with built-in **Explainable AI (XAI)**. It ingests real-time sensor telemetry from warehouse equipment, runs it through trained machine-learning models to detect faults, generates human-readable SHAP-based explanations, and surfaces everything to warehouse operators through a live React dashboard.

```
Sensor Event → FastAPI → AI Pipeline (SHAP + ML) → SQLite + WebSocket → React Dashboard
```

---

## Key Features

| Feature | Details |
|---|---|
| **Real-time anomaly detection** | LightGBM, XGBoost, Random Forest, LSTM-AE |
| **Explainable AI** | SHAP TreeExplainer — per-feature attribution scores |
| **Live dashboard** | React + WebSocket push — zero-refresh operator UI |
| **Operator workflow** | Acknowledge → Assign → Escalate → Resolve |
| **Dataset replay validation** | Replay held-out rows, track accuracy vs ground truth live |
| **Digital twin ready** | Isaac Sim adapter (currently stubbed) |

---

## System at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  Data Sources                                               │
│  seed scripts / dataset replayer ──► POST /events/ (HTTP)  │
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
| ML Models | LightGBM, XGBoost, scikit-learn RF, PyTorch LSTM-AE |
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
bash scripts/run_dev.sh
```

Dashboard → http://localhost:5173  
API → http://localhost:8000/docs

---

## Project Context

Graduation project at **Atılım University, Computer Engineering**, developed as a multi-person capstone team. This documentation covers the `feat/dashboard-ops-validation` branch which includes the complete dataset replay validation system and operator workflow.
