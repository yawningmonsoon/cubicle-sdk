#!/usr/bin/env python3
"""lab-session pass^k — consistency across identical sealed reruns (R7, local tier).

The τ-bench lesson applied to trading: the best GPT-4o agent passed the
SAME task 8-of-8 times less than 25% of the time. A desk metric must be
pass^k, not best-of-k — the same window must produce the same book.

Contract: same calls-contract as lab-one-switch — the strategy reads the
candle window on stdin and emits {"calls": [-1|0|+1 per bar]}; the harness
pays against the true tape. This harness runs the IDENTICAL window k times
and reports:
  identical_runs  every call-vector byte-identical
  agreement       mean pairwise per-bar call agreement
  scores          min / median / max paid score across runs
  verdict         deterministic | consistent (>= --agree-floor) | inconsistent

Reporting rule: min and max are shown together, never the best run alone —
cherry-picking the best of k is the selection fallacy this lab exists to
kill. Self-test: --self-test (deterministic strategy => identical; unseeded
random strategy => inconsistent).
"""

import argparse
import json
import statistics
import subprocess
import sys


def load_candles(text: str):
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def rets(candles):
    cl = [float(c["c"]) for c in candles]
    return [cl[i + 1] - cl[i] for i in range(len(cl) - 1)]


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


def dispersion(scores: list) -> dict:
    """Is the reported edge inside its own run-to-run noise?

    High call agreement is not enough. The peer-reviewed TradingAgents
    replication (ACM ICAIF 2026, DOI 10.1145/3800973.3801029) found LLM agents
    at 18.1% and 15.8% cumulative return with run-to-run SD of 9.4% and 9.0% —
    roughly HALF the reported return was sampling noise, and both configurations
    lost to a 19.1% buy-and-hold. A single-seed backtest of a stochastic agent
    carries approximately zero information.

    So the score spread gets a verdict of its own. `edge_over_noise` is the
    mean score in units of its own standard deviation across runs; below 1.0
    the reported number is not distinguishable from the harness re-rolling.

    Sample SD (n-1) throughout: with k small, the population form would flatter
    the strategy, and this panel exists to do the opposite.
    """
    k = len(scores)
    mean = sum(scores) / k
    if k < 2:
        return {
            "mean": round(mean, 6),
            "stdev": None,
            "edge_over_noise": None,
            "note": "k=1 — a single run has no dispersion; this is the uninterpretable case",
        }
    var = sum((s - mean) ** 2 for s in scores) / (k - 1)
    sd = var ** 0.5
    # A perfectly deterministic strategy has sd == 0. Its edge is not "infinite"
    # — it is simply not noise-limited, and saying so beats emitting a sentinel.
    ratio = None if sd == 0 else round(mean / sd, 4)
    return {
        "mean": round(mean, 6),
        "stdev": round(sd, 6),
        "edge_over_noise": ratio,
        "note": (
            "deterministic across runs — score is not noise-limited"
            if sd == 0
            else "mean score in units of its own run-to-run SD; < 1.0 is indistinguishable from noise"
        ),
    }


def pass_k(cmd, candles, k: int, agree_floor: float = 0.9) -> dict:
    true_r = rets(candles)
    books = [run_strategy(cmd, candles) for _ in range(k)]
    scores = sorted(pay(b, true_r) for b in books)
    identical = all(b == books[0] for b in books[1:])
    agreements = []
    for i in range(k):
        for j in range(i + 1, k):
            n = min(len(books[i]), len(books[j]))
            if n:
                agreements.append(sum(1 for x in range(n) if books[i][x] == books[j][x]) / n)
    agreement = round(sum(agreements) / len(agreements), 4) if agreements else 1.0
    if identical:
        verdict = "deterministic"
    elif agreement >= agree_floor:
        verdict = f"consistent (agreement {agreement} >= {agree_floor})"
    else:
        verdict = (f"inconsistent — pass^{k} failure: the same window produced "
                   f"different books (agreement {agreement})")
    disp = dispersion(scores)
    # A strategy can agree with itself on nearly every bar and still report a
    # return that lives inside its own seed noise. Both verdicts are emitted;
    # neither substitutes for the other.
    if disp["edge_over_noise"] is not None and disp["edge_over_noise"] < 1.0:
        score_verdict = (
            f"inside the noise — mean score {disp['mean']} vs run-to-run SD "
            f"{disp['stdev']} (edge/noise {disp['edge_over_noise']} < 1.0); "
            "report a seed distribution, never a single run"
        )
    else:
        score_verdict = "score exceeds its own run-to-run dispersion"
    return {"k": k, "n_bars": len(candles),
            "identical_runs": identical, "agreement": agreement,
            "score_min": scores[0], "score_median": scores[k // 2], "score_max": scores[-1],
            "dispersion": disp,
            "verdict": verdict,
            "score_verdict": score_verdict,
            "note": "min and max shown together — never report the best of k"}


def synth(n=400):
    # deterministic synthetic window (no RNG needed: deterministic zigzag+drift)
    px, out = 100.0, []
    for i in range(n):
        px += 0.05 + (0.9 if i % 3 == 0 else -0.4)
        out.append({"t": i, "o": px, "h": px, "l": px, "c": px})
    return out


DET = ("import sys,json; n=len([l for l in sys.stdin.read().splitlines() if l.strip()]); "
       "print(json.dumps({'calls': [1]*(n-1)}))")
FLAKY = ("import sys,json,random; n=len([l for l in sys.stdin.read().splitlines() if l.strip()]); "
         "print(json.dumps({'calls': [random.choice([-1,1]) for _ in range(n-1)]}))")


def self_test() -> int:
    w = synth()
    det = pass_k([sys.executable, "-c", DET], w, 5)
    flk = pass_k([sys.executable, "-c", FLAKY], w, 5)
    ok = det["identical_runs"] and det["agreement"] == 1.0
    ok &= det["score_min"] == det["score_max"]
    ok &= not flk["identical_runs"] and flk["agreement"] < 0.9
    ok &= "inconsistent" in flk["verdict"]

    # A deterministic strategy has zero dispersion: edge_over_noise is None
    # (not a sentinel), and the score verdict must not claim it is noise.
    ok &= det["dispersion"]["stdev"] == 0.0
    ok &= det["dispersion"]["edge_over_noise"] is None
    ok &= "inside the noise" not in det["score_verdict"]

    # The dispersion maths, checked against a hand-computed fixture rather than
    # against whatever the harness happens to produce.
    d = dispersion([1.0, 3.0])          # mean 2.0, sample SD 1.4142...
    ok &= d["mean"] == 2.0 and abs(d["stdev"] - 2 ** 0.5) < 1e-6  # stdev is rounded to 6dp
    ok &= abs(d["edge_over_noise"] - 2.0 / 2 ** 0.5) < 1e-4
    ok &= dispersion([5.0])["edge_over_noise"] is None   # k=1 is uninterpretable

    # The case the ICAIF replication describes: a real-looking mean sitting
    # inside its own seed noise must be called out, not reported as an edge.
    noisy = dispersion([18.1, 2.0, 30.0, -5.0, 25.0])
    ok &= noisy["edge_over_noise"] is not None and noisy["edge_over_noise"] < 1.0

    print(json.dumps({"self_test": "ok" if ok else "FAIL",
                      "deterministic": det["verdict"], "flaky": flk["verdict"],
                      "flaky_agreement": flk["agreement"],
                      "det_dispersion": det["dispersion"],
                      "noise_case_edge_over_noise": noisy["edge_over_noise"]}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", nargs="+", help="strategy command (reads candles on stdin)")
    ap.add_argument("--file", default="-", help="candles JSON/JSONL ('-' = stdin)")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--agree-floor", type=float, default=0.9)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.cmd:
        print(json.dumps({"error": "usage", "detail": "--cmd required"}))
        return 2
    text = sys.stdin.read() if args.file == "-" else open(args.file).read()
    print(json.dumps(pass_k(args.cmd, load_candles(text), args.k, args.agree_floor)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
