# Demo Script — DTX-AI MVP

**Audience:** Capstone supervisors, stakeholders  
**Duration:** ~10 minutes  
**Prerequisites:** `bash scripts/setup.sh` completed, API and dashboard running

---

## Part 1 — Introduction (2 min)

> "DTX-AI is a Smart Warehouse Digital Twin powered by AI anomaly detection
> and explainable AI.  Today we'll walk through a live demo of the MVP vertical
> slice: from a synthetic sensor event to a visual alert with a plain-language
> explanation."

Point to the architecture diagram in `docs/architecture.md`.

---

## Part 2 — Start the System (1 min)

```bash
bash scripts/run_dev.sh
```

Open two browser tabs:
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs

---

## Part 3 — Send a Normal Event (2 min)

Using the API docs (`POST /events`), send:

```json
{
  "asset_id": "conveyor-belt-01",
  "zone_id": "zone-A",
  "vibration": 3.0,
  "temperature": 30.0,
  "humidity": 50.0,
  "pressure": 1010.0
}
```

> "The system scores this as low risk — no anomaly.  You can see the event
> logged on the dashboard with an INFO severity."

---

## Part 4 — Trigger an Anomaly (3 min)

Send an anomalous event:

```json
{
  "asset_id": "pump-station-02",
  "zone_id": "zone-A",
  "vibration": 21.0,
  "temperature": 95.0,
  "humidity": 35.0,
  "pressure": 1060.0
}
```

> "The AI pipeline flags this as a CRITICAL anomaly.  Notice the alert
> appears instantly on the dashboard via WebSocket.  Click the alert to
> see the XAI explanation panel, which highlights vibration and temperature
> as the top contributing factors and recommends immediate maintenance."

---

## Part 5 — Seed Batch Events (1 min)

```bash
python scripts/seed_events.py
```

> "We can inject a batch of pre-defined events in one command — useful for
> stakeholder demos and testing the full pipeline."

---

## Part 6 — Wrap-Up (1 min)

Highlight the architecture slide and outline next milestones:
- Sprint 2: Train a real Isolation Forest model on the synthetic data.
- Sprint 3: Connect the Isaac Sim digital-twin scene.
- Sprint 4: Integrate ESP32 real sensor stream.
