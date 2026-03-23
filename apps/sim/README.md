# apps/sim — NVIDIA Isaac Sim Digital-Twin Adapter

## Purpose

This module bridges DTX-AI backend events with the NVIDIA Isaac Sim
digital-twin scene.  It is **deliberately isolated** — the rest of the project
runs without Isaac Sim installed.

## Architecture

```
apps/sim/
├── sim/
│   ├── adapter.py      # Public entry point: notify(TwinUpdate)
│   ├── scene.py        # Isaac Sim scene / USD stage helpers
│   └── hooks.py        # Simulation event hooks (on_start, on_stop, on_step)
├── .env.example
├── requirements.txt
└── README.md
```

## Setup (requires NVIDIA Isaac Sim 4.x)

1. Install Isaac Sim following the NVIDIA Omniverse documentation.
2. Set `ISAAC_SIM_PATH` in `.env` to your Isaac Sim installation root.
3. Run the adapter standalone:

```bash
cd apps/sim
python sim/adapter.py
```

## Running without Isaac Sim

The adapter raises an `ImportError` if Isaac Sim is not installed.
`apps/api` catches this and continues normally — the digital-twin sync
is silently skipped.
