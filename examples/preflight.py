#!/usr/bin/env python3
"""Score a claimed edge before believing it.

The shape of a pre-flight: you have a strategy's forecasts and the window it
ran on. Before the number means anything, three questions must be answered —
and this is what answering them looks like.

    python3 examples/preflight.py
"""
import json
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "cubicle_sdk" / "lab"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cubicle_sdk import GateState, HonestyBlock


def run(counter: str, *args) -> dict:
    r = subprocess.run([sys.executable, str(LAB / f"{counter}.py"), *args],
                       capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def main() -> int:
    claim = {"sharpe": 2.5, "variants_tried": 100, "bars": 1250}
    print(f"CLAIM: Sharpe {claim['sharpe']} over {claim['bars']} bars\n")

    # 1. Does it survive the number of variants actually tried?
    dsr = run("deflated_sharpe",
              "--sr", str(claim["sharpe"]),
              "--trials", str(claim["variants_tried"]),
              "--obs", str(claim["bars"]))
    print("1. Selection under", claim["variants_tried"], "trials")
    print("   ", json.dumps({k: v for k, v in dsr.items() if k != "note"}))

    # 2. Was the window one the model could have memorized?
    honesty = HonestyBlock(corpus="pre_cutoff")
    print("\n2. Corpus")
    print(f"    clean={honesty.corpus_is_clean}  unmeasured={honesty.unmeasured()}")

    # 3. What may this earn?
    gate = GateState.parse("Backtested")
    print("\n3. Gate")
    print(f"    at {gate.value}: may_be_priced={gate.may_be_priced}")
    print(f"    next requires: {gate.blocking_predicate()}")

    print("\nVERDICT: unpriceable. The claim is not wrong — it is unsupported,")
    print("which is a different and more useful thing to know.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
