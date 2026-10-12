#!/usr/bin/env python3
"""Demo: a deliberately LEAKY strategy for lesson L5.

Call i = the sign of the bar i -> i+1 return — it reads the NEXT bar to
"predict" it. On a pristine window it scores near-perfectly; under the
lag1 toggle its crystal ball becomes yesterday's paper. This is the same
mechanism as XAMD's 98%-WR label leak, reduced to five lines.
"""
import json
import sys

candles = [json.loads(l) for l in sys.stdin.read().splitlines() if l.strip()]
closes = [float(c["c"]) for c in candles]
calls = []
for i in range(len(closes) - 1):
    r = closes[i + 1] - closes[i]
    calls.append(1 if r > 0 else (-1 if r < 0 else 0))
print(json.dumps({"calls": calls}))
