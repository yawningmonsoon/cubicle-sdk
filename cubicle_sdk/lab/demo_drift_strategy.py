#!/usr/bin/env python3
"""Demo: a structure-free DRIFT-RIDER for lesson L5.

Always long. No lookahead (survives lag1 perfectly), no structure (its
"edge" is the window's drift). The flip toggle exposes it: mirrored
prices negate its score exactly. Any strategy whose one-switch profile
matches this one has rediscovered buy-and-hold.
"""
import json
import sys

n = len([l for l in sys.stdin.read().splitlines() if l.strip()])
print(json.dumps({"calls": [1] * max(0, n - 1)}))
