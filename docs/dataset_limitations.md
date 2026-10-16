# Dataset limitations — DTX-AI v3.0 Final

The final release includes the 19-channel warehouse telemetry dataset,
seven trained model families, and their validation artifacts under
`services/ai/ai/models/shared/`.

Training and evaluation use per-episode temporal splits. The demo holdout
is the last 20% of every contiguous fault run, separated from the training
pool by a 60-row purge gap. The train/validation split also uses temporal
separation. See `services/ai/preprocessing.py` for the canonical implementation.

High holdout scores do not establish performance on arbitrary real equipment:

- Fault runs are long and internally homogeneous.
- Per-class feature distributions have little overlap.
- There are no gradual fault precursors or transition regimes.
- Labels represent one fault at a time; compound faults are outside the data.
- Environmental noise is limited, although sensor dropouts are present.

`sanity_baselines.json` records simple-feature baselines; `leaderboard.json`
and each model's `metadata.json` retain the measured validation and holdout
results. These artifacts are retained as evidence, not renamed or retrained
as part of the final release cleanup.

The ESP32 demo measures temperature and barometric pressure. Other model
channels are derived or synthesized, with their provenance recorded in each
event's metadata. Hardware predictions are demonstrations, without measured
ground-truth accuracy. See [hardware_demo.md](hardware_demo.md).

The simulator adapter is retained, with logging hooks awaiting host scene integration. Telemetry generation
in the source dataset does not imply a running digital-twin integration.
