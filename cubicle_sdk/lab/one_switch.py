#!/usr/bin/env python3
"""lab-one-switch — toggle one input channel; if the alpha vanishes, it was
never alpha (R5, local tier).

CONTRACT (the seam that keeps this honest): the strategy-under-test is any
command that reads a candle window as JSON lines on stdin and emits
{"calls": [c_0 .. c_{n-2}]} with c_i in {-1, 0, +1} — the position held
over the bar i -> i+1 return. The HARNESS pays the calls against the TRUE
tape; a toggle alters only what the strategy SEES, never what it is paid
on. Decisions come from the strategy, accounting from the harness — the
same separation the venue enforces.

Toggles (one per run — that is the point):
  lag1            the strategy sees the window delayed one bar (bar i shows
                  bar i-1's OHLC). An edge that dies here was reading the
                  CURRENT bar to "predict" it — lookahead.
  shuffle-returns the return sequence is permuted (seeded). An edge that
                  SURVIVES here reads no temporal structure — it is long
                  the drift, not skill.
  flip            prices mirrored (returns negated). A genuine long/short
                  edge roughly negates; an "edge" that stays positive is
                  harness bias or drift-riding.

Output: one JSON object with base/toggled scores, ratio, and a verdict.
Deterministic (seeded). Self-test runs the two bundled demo strategies and
asserts the leaky one dies under lag1 and the drift-rider dies under flip.
"""

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_candles(text: str):
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def closes(candles):
    return [float(c["c"]) for c in candles]


def rets(candles):
    cl = closes(candles)
    return [cl[i + 1] - cl[i] for i in range(len(cl) - 1)]


def toggle_window(candles, toggle: str, seed: int):
    if toggle == "none":
        return candles
    if toggle == "lag1":
        # bar i shows bar i-1's OHLC; bar 0 repeats itself. Timestamps keep
        # their slots so the strategy's indexing is unchanged.
        out = []
        for i, c in enumerate(candles):
            src = candles[max(0, i - 1)]
            out.append({**c, "o": src["o"], "h": src["h"], "l": src["l"], "c": src["c"]})
        return out
    if toggle in ("shuffle-returns", "flip"):
        r = rets(candles)
        if toggle == "shuffle-returns":
            rng = random.Random(seed)
            rng.shuffle(r)
        else:
            r = [-x for x in r]
        px = float(candles[0]["c"])
        out = [dict(candles[0])]
        for i, dr in enumerate(r):
            px += dr
            c = dict(candles[i + 1])
            c.update(o=px - dr, h=max(px, px - dr), l=min(px, px - dr), c=px)
            out.append(c)
        return out
    raise SystemExit(json.dumps({"error": "usage", "detail": f"unknown toggle {toggle}"}))


def run_strategy(cmd, candles) -> list:
    payload = "\n".join(json.dumps(c) for c in candles)
    p = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise SystemExit(json.dumps({"error": "strategy", "detail": p.stderr.strip()[-300:]}))
    for line in reversed(p.stdout.strip().splitlines()):
        if line.strip().startswith("{"):
            calls = json.loads(line).get("calls")
            if isinstance(calls, list):
                return calls
    raise SystemExit(json.dumps({"error": "contract", "detail": 'strategy must emit {"calls": [...]}'}))


def pay(calls, true_rets) -> float:
    n = min(len(calls), len(true_rets))
    return round(sum(int(calls[i]) * true_rets[i] for i in range(n)), 6)


INTERPRET = {
    "lag1": ("alpha survives information delay",
             "alpha VANISHED under a one-bar delay — suspect lookahead/same-bar leak"),
    "shuffle-returns": ("edge reads temporal structure (dies when shuffled) — expected",
                        "edge SURVIVES shuffled returns — it is drift-riding, not structure"),
    "flip": ("edge roughly negates under mirrored prices — direction-honest",
             "edge stays positive under mirrored prices — harness bias or drift-riding"),
}


def one_switch(cmd, candles, toggle, seed=42, survive_frac=0.5) -> dict:
    """Two toggle classes, deliberately different payoff rules:
    - INFORMATION toggle (lag1): the strategy sees the altered window but is
      paid on the TRUE tape — tests what it knew, not what happened.
    - TAPE toggles (flip, shuffle-returns): the whole experiment runs on the
      counterfactual tape (seen AND paid) — tests whether the edge is
      temporal structure or just the window's marginal drift."""
    true_r = rets(candles)
    base = pay(run_strategy(cmd, candles), true_r)
    toggled_window = toggle_window(candles, toggle, seed)
    pay_r = true_r if toggle == "lag1" else rets(toggled_window)
    toggled = pay(run_strategy(cmd, toggled_window), pay_r)
    ratio = round(toggled / base, 4) if base not in (0, 0.0) else None
    if toggle == "lag1":
        survived = ratio is not None and ratio >= survive_frac
        verdict = INTERPRET["lag1"][0] if survived else INTERPRET["lag1"][1]
    elif toggle == "shuffle-returns":
        survived = ratio is not None and ratio >= survive_frac  # surviving is BAD here
        verdict = INTERPRET["shuffle-returns"][1] if survived else INTERPRET["shuffle-returns"][0]
    else:  # flip
        survived = ratio is not None and ratio >= 0.0  # staying positive is BAD
        verdict = INTERPRET["flip"][1] if (toggled > 0 and base > 0) else INTERPRET["flip"][0]
    return {"toggle": toggle, "n_bars": len(candles),
            "score_base": base, "score_toggled": toggled, "ratio": ratio,
            "verdict": verdict,
            "note": "one toggle per run — that is the point; report only these numbers"}


def synth(seed=7, n=1500, drift=0.0003):
    rng = random.Random(seed)
    px, out = 100.0, []
    for i in range(n):
        px *= 1.0 + drift + rng.gauss(0.0, 0.004)
        out.append({"t": i, "o": px, "h": px, "l": px, "c": px})
    return out


def self_test() -> int:
    w = synth()
    leaky = [sys.executable, str(HERE / "demo_leaky_strategy.py")]
    drifty = [sys.executable, str(HERE / "demo_drift_strategy.py")]
    r1 = one_switch(leaky, w, "lag1")
    r2 = one_switch(drifty, w, "flip")
    r3 = one_switch(drifty, w, "lag1")
    ok = r1["score_base"] > 0 and (r1["ratio"] is None or r1["ratio"] < 0.5)  # leak dies
    ok &= r2["score_base"] > 0 and r2["score_toggled"] < 0                     # drift flips
    ok &= r3["ratio"] is not None and r3["ratio"] > 0.9                        # drift immune to lag
    print(json.dumps({"self_test": "ok" if ok else "FAIL",
                      "leaky_under_lag1": r1, "drift_under_flip": r2,
                      "drift_under_lag1_ratio": r3["ratio"]}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", nargs="+", help="strategy command (reads candles on stdin)")
    ap.add_argument("--file", default="-", help="candles JSON/JSONL ('-' = stdin)")
    ap.add_argument("--toggle", choices=["lag1", "shuffle-returns", "flip"], default="lag1")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--survive-frac", type=float, default=0.5)
    ap.add_argument("--experiment", default=None,
                    help="log this run's (cmd, toggle, seed) as a trial variant "
                         "in the trials registry (R10)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.cmd:
        print(json.dumps({"error": "usage", "detail": "--cmd required"}))
        return 2
    text = sys.stdin.read() if args.file == "-" else open(args.file).read()
    out = one_switch(args.cmd, load_candles(text), args.toggle,
                     args.seed, args.survive_frac)
    if args.experiment is not None:
        sys.path.insert(0, str(HERE.parents[1]))
        from trials_registry import log_trial
        variant = f"cmd={' '.join(args.cmd)}|toggle={args.toggle}|seed={args.seed}"
        out["trial"] = log_trial(args.experiment, variant, source="lab-one-switch")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
