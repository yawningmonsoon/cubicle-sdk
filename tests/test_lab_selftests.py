"""Every counter must pass its own self-test, from a clean checkout."""
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "cubicle_sdk" / "lab"
COUNTERS = ["null_panel", "deflated_sharpe", "calibration",
            "pushback", "pass_k", "corpus_flag", "one_switch"]


def test_every_counter_self_tests():
    failures = []
    for name in COUNTERS:
        r = subprocess.run([sys.executable, str(LAB / f"{name}.py"), "--self-test"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            failures.append(f"{name}: exit {r.returncode} {r.stdout[:160]}")
    assert not failures, failures
