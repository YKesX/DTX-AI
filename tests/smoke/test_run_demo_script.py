import subprocess
from pathlib import Path


def test_run_demo_help_contains_required_flags():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "run_demo.sh"
    completed = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = completed.stdout
    # Legacy --scenario / --mode flags were removed when the synthetic-scenario
    # seeder was retired in favour of dataset-replay + Isaac Sim only.
    assert "--split" in out
    assert "--model" in out
    assert "--strict-replay" in out
    assert "--no-seed" in out
    assert "--count" in out
