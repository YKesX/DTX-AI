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
    assert "--scenario" in out
    assert "--mode" in out
    assert "--model" in out
    assert "--strict-replay" in out
    assert "--no-seed" in out
