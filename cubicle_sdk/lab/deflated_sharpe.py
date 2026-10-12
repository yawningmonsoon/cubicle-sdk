#!/usr/bin/env python3
"""lab-deflated-sharpe — the selection-on-noise math, runnable.

Implements Bailey & López de Prado (JPM 2014):
  expected_max_sr(n_trials, sr_std)  — the Sharpe you should expect from the
    BEST of N zero-skill trials. Anchor (their own example): 45 independent
    trials on ~5 years of data (sr_std = 1/sqrt(5)) => E[max SR] ~= 1.0.
  dsr(sr_hat, ...) — Deflated Sharpe Ratio: probability the observed Sharpe
    exceeds the noise-expected maximum, adjusting for track length, skew and
    kurtosis.

Every prompt variant, parameter tweak, and re-run is a trial. If you cannot
state n_trials, you cannot state significance — that absence is the finding.

Output: single JSON object. Deterministic; stdlib only.
Self-test: --self-test (verifies the published N=45 anchor).
"""

import argparse
import json
import math
import sys
from statistics import NormalDist

_ND = NormalDist()
EULER_GAMMA = 0.5772156649015329


def expected_max_sr(n_trials: int, sr_std: float) -> float:
    """E[max SR] over n_trials independent zero-skill strategies whose
    estimated Sharpe has standard deviation sr_std."""
    if n_trials < 2:
        return 0.0
    z1 = _ND.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _ND.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return sr_std * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)


def dsr(sr_hat: float, n_trials: int, n_obs: int,
        skew: float = 0.0, kurtosis: float = 3.0, sr_std: float | None = None) -> dict:
    """Deflated Sharpe Ratio. sr_hat and the benchmark are per-observation
    Sharpe (same frequency as n_obs). sr_std defaults to 1/sqrt(n_obs)."""
    if sr_std is None:
        sr_std = 1.0 / math.sqrt(n_obs)
    sr0 = expected_max_sr(n_trials, sr_std)
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr_hat + (kurtosis - 1.0) / 4.0 * sr_hat ** 2))
    z = (sr_hat - sr0) * math.sqrt(n_obs - 1) / denom
    return {
        "sr_hat": sr_hat,
        "n_trials": n_trials,
        "n_obs": n_obs,
        "expected_max_sr_from_noise": round(sr0, 4),
        "dsr": round(_ND.cdf(z), 4),
        "verdict": ("survives_deflation" if _ND.cdf(z) >= 0.95 else
                    "expected_from_noise"),
        "note": "every variant tried is a trial; unstated n_trials = unstated significance",
    }


def self_test() -> int:
    # Published anchor: N=45 trials, 5 annual observations => E[max SR] ~ 1.0
    e = expected_max_sr(45, 1.0 / math.sqrt(5))
    ok = abs(e - 1.0) < 0.05
    # More trials must never lower the noise ceiling.
    ok &= expected_max_sr(200, 0.447) > expected_max_sr(45, 0.447)
    # A Sharpe equal to the noise-expected max must NOT survive deflation.
    r = dsr(sr_hat=e, n_trials=45, n_obs=5)
    ok &= r["verdict"] == "expected_from_noise"
    print(json.dumps({"self_test": "ok" if ok else "FAIL",
                      "anchor_n45_5y_expected_max_sr": round(e, 4)}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sr", type=float, help="observed Sharpe (per-observation basis)")
    ap.add_argument("--trials", type=int, required=False)
    ap.add_argument("--experiment", default=None,
                    help="read N from the trials registry instead of --trials "
                         "(the denominator as observation, not confession)")
    ap.add_argument("--obs", type=int, help="number of return observations")
    ap.add_argument("--skew", type=float, default=0.0)
    ap.add_argument("--kurtosis", type=float, default=3.0)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    trials = args.trials
    if args.experiment is not None:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
        from trials_registry import count_trials
        trials = count_trials(args.experiment)
        if trials == 0:
            print(json.dumps({"error": "no_trials",
                              "detail": f"experiment '{args.experiment}' has no "
                                        "registered trials — log variants first"}))
            return 2
    if args.sr is None or trials is None or args.obs is None:
        print(json.dumps({"error": "usage",
                          "detail": "--sr --obs and (--trials | --experiment) required"}))
        return 2
    out = dsr(args.sr, trials, args.obs, args.skew, args.kurtosis)
    if args.experiment is not None:
        out["n_trials_source"] = f"registry:{args.experiment}"
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
