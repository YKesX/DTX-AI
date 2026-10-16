# Simulator adapter — v3.0 Final

`sim.adapter.notify()` receives asset status updates from the event pipeline.
`sim.adapter.move_entity()` receives entity positions from `POST /positions/`.
The latest positions are available at `GET /positions/latest` for simulator polling.
The development launch scripts include this package on `PYTHONPATH`.

By default, the adapter logs updates. Set `ISAAC_SIM_ENABLED=true` in the API
environment to invoke `sim.scene` hooks. The supplied hooks log their calls;
connect them to your host's USD stage to perform scene changes. The scene and
forklift scripts under `apps/isaac-sim/` require an Isaac Sim installation.

To send the included position scenario while the API is running:

```bash
source .venv/bin/activate
python apps/sim/sim/playback.py --scenario apps/sim/scenarios/forklift_patrol.json
```

Playback requires `requests` (`pip install requests`). Scene execution must be
validated inside Isaac Sim; the ordinary API tests cover adapter dispatch only.
