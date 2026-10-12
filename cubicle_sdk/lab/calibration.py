#!/usr/bin/env python3
"""Score a forecaster's stated probabilities against what actually happened.

The counter to dossier §7.3: a model's "78% confident" is a speech style, not
a probability. RLHF post-training degrades calibration toward overconfidence
(GPT-4 Technical Report Fig. 8), and verbalized confidence clusters in the
80-100% band in round multiples of 5 regardless of accuracy (Xiong et al.,
ICLR 2024, arXiv 2306.13063). Kelly-sizing off such a number inherits the
overconfidence directly into position size.

This script does not fix calibration. It measures it, so that a size rule can
read a MEASURED frequency instead of a stated one:

    Brier score       mean squared error of the probability itself
    reliability       E[(stated - observed)^2] per bin -- the miscalibration
    resolution        E[(observed - base_rate)^2]     -- the discrimination
    ECE              expected calibration error, |stated - observed| by bin
    round-number tell fraction of forecasts on multiples of 0.05
    band tell         fraction of forecasts in [0.8, 1.0]

Murphy's decomposition is the load-bearing part: Brier = reliability
- resolution + uncertainty. A forecaster can be well-calibrated and useless
(reliability ~ 0, resolution ~ 0: it always says the base rate). Reporting
Brier alone hides which one you have, so all three are always printed.

Input: JSON array or JSONL of {"p": <float 0..1>, "outcome": <0|1>}, or `-`
for stdin. Deterministic; no randomness anywhere.

Exit codes: 0 scored, 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys

# Bin edges for reliability/ECE. Ten equal bins is the convention in the
# calibration literature and keeps each bin's count legible in the output.
N_BINS = 10


def _err(kind: str, detail: str) -> int:
    """Typed error envelope -- callers route on `kind`, never on the message."""
    json.dump({"ok": False, "error": {"kind": kind, "detail": detail}}, sys.stdout)
    sys.stdout.write("\n")
    return 2


def load_forecasts(raw: str) -> list[tuple[float, int]]:
    """Parse a JSON array or JSONL of {p, outcome}. Raises ValueError."""
    raw = raw.strip()
    if not raw:
        raise ValueError("empty input")

    records: list[dict] = []
    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("top-level JSON must be an array")
        records = parsed
    else:
        for i, line in enumerate(raw.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {i}: {exc}") from exc

    out: list[tuple[float, int]] = []
    for i, r in enumerate(records, 1):
        if not isinstance(r, dict) or "p" not in r or "outcome" not in r:
            raise ValueError(f"record {i}: needs both `p` and `outcome`")
        p = float(r["p"])
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"record {i}: p={p} outside [0,1]")
        o = r["outcome"]
        # An outcome must be binary. Accepting a truthy float here would let a
        # continuous return sneak in and silently become "1".
        if o not in (0, 1, True, False):
            raise ValueError(f"record {i}: outcome must be 0 or 1, got {o!r}")
        out.append((p, int(o)))
    return out


def score(forecasts: list[tuple[float, int]]) -> dict:
    """Brier + Murphy decomposition + ECE + the two overconfidence tells."""
    n = len(forecasts)
    base_rate = sum(o for _, o in forecasts) / n
    brier = sum((p - o) ** 2 for p, o in forecasts) / n

    # Bin by stated probability. Index min()-clamped so p == 1.0 lands in the
    # top bin rather than one past the end.
    bins: list[list[tuple[float, int]]] = [[] for _ in range(N_BINS)]
    for p, o in forecasts:
        bins[min(int(p * N_BINS), N_BINS - 1)].append((p, o))

    reliability = 0.0
    resolution = 0.0
    ece = 0.0
    bin_rows = []
    for idx, b in enumerate(bins):
        if not b:
            continue
        k = len(b)
        mean_p = sum(p for p, _ in b) / k
        obs = sum(o for _, o in b) / k
        reliability += k * (mean_p - obs) ** 2
        resolution += k * (obs - base_rate) ** 2
        ece += k * abs(mean_p - obs)
        bin_rows.append(
            {
                "bin": f"{idx / N_BINS:.1f}-{(idx + 1) / N_BINS:.1f}",
                "n": k,
                "mean_stated": round(mean_p, 4),
                "observed": round(obs, 4),
                "gap": round(mean_p - obs, 4),
            }
        )

    reliability /= n
    resolution /= n
    ece /= n
    uncertainty = base_rate * (1 - base_rate)

    # The two tells from Xiong et al.: confidence that is a speech style
    # clusters on round numbers and in the top band.
    round_tell = sum(1 for p, _ in forecasts if abs(p * 20 - round(p * 20)) < 1e-9) / n
    band_tell = sum(1 for p, _ in forecasts if p >= 0.8) / n

    mean_stated = sum(p for p, _ in forecasts) / n

    return {
        "n": n,
        "base_rate": round(base_rate, 6),
        "mean_stated": round(mean_stated, 6),
        "overconfidence": round(mean_stated - base_rate, 6),
        "brier": round(brier, 6),
        "reliability": round(reliability, 6),
        "resolution": round(resolution, 6),
        "uncertainty": round(uncertainty, 6),
        # Murphy: brier == reliability - resolution + uncertainty. Emitted so a
        # consumer can assert the identity rather than trust it.
        "murphy_residual": round(brier - (reliability - resolution + uncertainty), 9),
        "ece": round(ece, 6),
        "round_number_fraction": round(round_tell, 4),
        "top_band_fraction": round(band_tell, 4),
        "bins": bin_rows,
    }


def verdict(s: dict) -> dict:
    """Turn the numbers into the one thing a sizing rule needs to know.

    Deliberately conservative: `usable_for_sizing` is true only when the
    forecaster both tracks reality (low reliability error) AND discriminates
    (non-trivial resolution). A forecaster that always says the base rate is
    perfectly calibrated and carries no information; sizing off it is sizing
    off noise.
    """
    # A forecaster with no resolution is a constant predictor dressed up.
    discriminates = s["resolution"] > 0.005
    tracks = s["ece"] <= 0.05
    reasons = []
    if not tracks:
        reasons.append(f"ECE {s['ece']:.3f} > 0.05 -- stated probabilities do not track observed frequency")
    if not discriminates:
        reasons.append(f"resolution {s['resolution']:.4f} <= 0.005 -- no discrimination beyond the base rate")
    if s["overconfidence"] > 0.10:
        reasons.append(f"mean stated exceeds base rate by {s['overconfidence']:.3f}")
    if s["round_number_fraction"] > 0.8 and s["top_band_fraction"] > 0.8:
        reasons.append(
            "round-number + top-band clustering: the signature of verbalized "
            "confidence as speech style (Xiong et al. 2306.13063)"
        )
    return {
        "usable_for_sizing": bool(tracks and discriminates),
        "reasons": reasons or ["calibrated and discriminating on this window"],
        "rule": "size on the observed frequency in the bin, never on the stated probability",
    }


def self_test() -> int:
    """Three fixtures with known-by-construction answers."""
    # 1. A perfectly calibrated, discriminating forecaster: p in {0.2, 0.8},
    #    and outcomes occur at exactly those rates.
    perfect: list[tuple[float, int]] = []
    for _ in range(20):
        perfect += [(0.2, 1)] + [(0.2, 0)] * 4      # 20% of 5
        perfect += [(0.8, 1)] * 4 + [(0.8, 0)]      # 80% of 5
    s = score(perfect)
    assert abs(s["ece"]) < 1e-9, f"perfect forecaster ECE {s['ece']}"
    assert s["resolution"] > 0.05, f"should discriminate, got {s['resolution']}"
    assert verdict(s)["usable_for_sizing"], "perfect forecaster must be usable"

    # 2. The overconfident forecaster: always says 0.9, right half the time.
    over = [(0.9, i % 2) for i in range(100)]
    s2 = score(over)
    assert abs(s2["overconfidence"] - 0.4) < 1e-9, s2["overconfidence"]
    assert abs(s2["ece"] - 0.4) < 1e-9, s2["ece"]
    assert not verdict(s2)["usable_for_sizing"], "overconfident must be refused"

    # 3. The base-rate parrot: perfectly calibrated, zero information. This is
    #    the case Brier alone would pass and Murphy catches.
    parrot = [(0.5, i % 2) for i in range(100)]
    s3 = score(parrot)
    assert abs(s3["ece"]) < 1e-9, s3["ece"]
    assert s3["resolution"] < 1e-9, s3["resolution"]
    assert not verdict(s3)["usable_for_sizing"], "a base-rate parrot must be refused"

    # Murphy's identity must hold on every fixture, or the decomposition is wrong.
    for st in (s, s2, s3):
        assert abs(st["murphy_residual"]) < 1e-9, st["murphy_residual"]

    json.dump({"ok": True, "self_test": "pass", "fixtures": 3}, sys.stdout)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", help="JSON array or JSONL of {p, outcome}; `-` for stdin")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.file:
        return _err("usage", "--file is required (or --self-test)")

    try:
        raw = sys.stdin.read() if args.file == "-" else open(args.file).read()
    except OSError as exc:
        return _err("io", str(exc))

    try:
        forecasts = load_forecasts(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return _err("bad_input", str(exc))

    # Below ~30 forecasts the bins are too thin for reliability to mean
    # anything. Refusing is the honest answer; a number here would be noise.
    if len(forecasts) < 30:
        return _err(
            "insufficient_data",
            f"{len(forecasts)} forecasts; calibration needs >= 30 for bins to carry signal",
        )

    s = score(forecasts)
    s["verdict"] = verdict(s)
    s["ok"] = True
    json.dump(s, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
