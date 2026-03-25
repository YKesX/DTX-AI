# Demo Script — DTX-AI Current Stage

**Audience:** Capstone supervisors, stakeholders  
**Duration:** ~10 minutes  
**Prerequisites:** `bash scripts/setup.sh` completed, API and dashboard running

---

## Part 1 — Introduction (2 min)

> "DTX-AI is a smart warehouse AI monitoring platform. Today we show two
> software demo modes: synthetic plumbing and dataset replay validation. The
> replay mode is the proof that real trained models are driving predictions."

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

## Part 3 — Synthetic mode smoke (2 min)

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

## Part 4 — Dataset replay validation mode (3 min)

Run:

```bash
bash scripts/run_demo.sh --mode replay --model random_forest --split test --count 30 --delay 0.4 --strict-replay
```

Narration points:

- input source is dataset replay (`source=dataset_replay`)
- selected model is shown (`runtime_model`)
- each event includes ground truth vs predicted label
- dashboard shows correct/wrong and running replay accuracy
- `/metrics/live` increments during replay

## Part 5 — Manual anomaly event (2 min)

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

## Part 6 — Seed batch events (1 min)

```bash
python scripts/seed_events.py
```

> "We can inject a batch of pre-defined events in one command — useful for
> stakeholder demos and testing the full pipeline."

---

## Part 7 — Wrap-Up (1 min)

Highlight the architecture slide and outline next milestones:
- Keep improving replay validation quality and reporting.
- Add Isaac Sim integration in the later stage.
- Add hardware sensor stream integration in the later stage.
