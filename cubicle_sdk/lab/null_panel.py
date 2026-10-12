#!/usr/bin/env python3
"""lab-null-panel — null-model baselines over a candle window.

The rule this enforces (LAB_ROADMAP practice 2): no harness result counts
until these nulls ran on the same window. If a "strategy" barely beats
always_up, it rediscovered the drift; if a harness scores random() near
60%, the harness leaks.

Input: candles as JSON lines or a JSON array on --file/stdin, each candle
{"t": <ms>, "o": <f>, "h": <f>, "l": <f>, "c": <f>}. Prediction task: sign
of the next bar's close-to-close return (flat bars are excluded from WR
denominators — a call on a zero return is neither right nor wrong).

Output (single JSON object, schema stable):
  {"n_bars", "n_scored", "base_rate_up",
   "nulls": {"always_up": wr, "always_down": wr, "random_seed42": wr,
             "with_prev": wr},
   "buy_and_hold_return_pct", "note"}

Deterministic: randomness is seeded (default 42); no wall-clock anywhere.
Self-test: run with --self-test (exits 0/1).
"""

import argparse
import json
import random
import sys


def load_candles(text: str):
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def panel(candles, seed: int = 42):
    closes = [float(c["c"]) for c in candles]
    n = len(closes)
    if n < 3:
        return {"error": "insufficient", "detail": "need >= 3 candles"}
    rets = [closes[i + 1] - closes[i] for i in range(n - 1)]

    rng = random.Random(seed)
    hits = {"always_up": 0, "always_down": 0, "random_seed%d" % seed: 0, "with_prev": 0}
    scored = {k: 0 for k in hits}

    # with_prev needs a previous return, so score from the second return on
    # for that null only; the others score every non-flat return.
    for i, r in enumerate(rets):
        if r == 0.0:
            continue
        up = r > 0
        for key, call in (("always_up", True),
                          ("always_down", False),
                          ("random_seed%d" % seed, rng.random() < 0.5)):
            scored[key] += 1
            hits[key] += 1 if call == up else 0
        if i >= 1 and rets[i - 1] != 0.0:
            scored["with_prev"] += 1
            hits["with_prev"] += 1 if (rets[i - 1] > 0) == up else 0

    ups = sum(1 for r in rets if r > 0)
    nonflat = sum(1 for r in rets if r != 0.0)
    return {
        "n_bars": n,
        "n_scored": nonflat,
        "base_rate_up": round(ups / nonflat, 4) if nonflat else None,
        "nulls": {k: (round(hits[k] / scored[k], 4) if scored[k] else None)
                  for k in hits},
        "buy_and_hold_return_pct": round((closes[-1] / closes[0] - 1.0) * 100, 4),
        "note": "a strategy WR is evidence only relative to these nulls on the SAME window",
    }


def self_test() -> int:
    # Deterministic drifting series: up-biased random walk, seeded.
    rng = random.Random(7)
    px, candles = 100.0, []
    for i in range(2000):
        px *= 1.0 + (0.0002 + rng.gauss(0.0, 0.004))
        candles.append({"t": i, "o": px, "h": px, "l": px, "c": px})
    out = panel(candles)
    ok = True
    # always_up WR must equal the base rate exactly.
    ok &= abs(out["nulls"]["always_up"] - out["base_rate_up"]) < 1e-9
    # up + down partition every scored bar.
    ok &= abs(out["nulls"]["always_up"] + out["nulls"]["always_down"] - 1.0) < 1e-9
    # seeded random sits near a coin flip on 2k bars.
    ok &= abs(out["nulls"]["random_seed42"] - 0.5) < 0.05
    # determinism: same input, same output.
    ok &= panel(candles) == out
    print(json.dumps({"self_test": "ok" if ok else "FAIL", "panel": out}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="-", help="candles JSON/JSONL ('-' = stdin)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    text = sys.stdin.read() if args.file == "-" else open(args.file).read()
    out = panel(load_candles(text), seed=args.seed)
    print(json.dumps(out))
    return 0 if "error" not in out else 2


if __name__ == "__main__":
    raise SystemExit(main())
