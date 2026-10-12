#!/usr/bin/env python3
"""Reconstruct a strategy found on the internet: take it apart, build it, run it over recorded bars.

    python3 examples/reconstruct.py examples/strategies/opening-range-breakout.txt --market NQ --accept

The same as `cubicle reconstruct <file> --market NQ --accept`. The chain is the studio's own and the server decides
every gate; `Cubicle.reconstruct` only follows it: reverse (nothing is run) → read (the seven parts, from the rule's own
words) → the studio's moves → forge → rehearse on the last week of real bars.

`--accept` is yours to give: it accepts the parts as the reader read them and builds from the gates the tape can
measure. Without it the run stops at the first move and prints it. A rehearsal is the past, not a forecast, and the
published win rate of the strategy you found is a claim until this number exists.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cubicle_sdk.mcp import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["reconstruct", *sys.argv[1:]]))
