#!/usr/bin/env python3
"""lab-session corpus flag — window vs model-training-cutoff verdict.

Stamped at session start; travels on the receipt (HonestyBlock.corpus).
Grounding: pre-cutoff recall is exact and post-cutoff recall drops to zero
(arXiv 2504.14765); lookahead propensity collapses AT the cutoff
(2512.23847). An in-window evaluation is therefore non-identified — the
receipt says so instead of hiding it.

Verdicts: post_cutoff | pre_cutoff | unknown_model | not_a_model
Rule: pre_cutoff whenever ANY part of the window is <= cutoff month-end.

The cutoffs table is DATA (maintain it; entries are conservative "knowledge
through" months, not release dates). --cutoff YYYY-MM overrides the table.
Self-test: --self-test.
"""

import argparse
import json

# Conservative knowledge-cutoff months. Maintained data, not code.
KNOWN_CUTOFFS = {
    "claude-fable-5": "2026-01",
    "claude-opus-5": "2026-01",
    "claude-sonnet-5": "2026-01",
    "claude-haiku-4-5": "2025-02",
    "gpt-5": "2024-10",
    "deepseek-v3.1": "2024-07",
    "qwen3-max": "2024-12",
    "nemotron-algotrada": "2024-06",
}


def flag(window_start: str, window_end: str, model: str | None,
         cutoff: str | None = None) -> dict:
    if model is None and cutoff is None:
        return {"corpus": "not_a_model",
                "detail": "no model declared — rules engines cannot memorize the future"}
    cut = cutoff or KNOWN_CUTOFFS.get((model or "").lower())
    if cut is None:
        return {"corpus": "unknown_model", "model": model,
                "detail": "model not in cutoffs table and no --cutoff given; "
                          "treat as pre_cutoff for any pre-2027 window"}
    ws, we = window_start[:7], window_end[:7]
    if ws > we:
        return {"corpus": "error", "detail": "window_start after window_end"}
    verdict = "post_cutoff" if ws > cut else "pre_cutoff"
    return {"corpus": verdict, "model": model, "cutoff_month": cut,
            "window": [window_start, window_end],
            "detail": ("window entirely after the cutoff — memorization ruled out"
                       if verdict == "post_cutoff" else
                       "window overlaps the corpus — in-window results are non-identified "
                       "(recall vs inference indistinguishable)")}


def self_test() -> int:
    ok = flag("2026-05-01", "2026-05-30", "gpt-5")["corpus"] == "post_cutoff"
    ok &= flag("2024-01-01", "2024-12-31", "gpt-5")["corpus"] == "pre_cutoff"
    # straddling the cutoff is pre_cutoff — partial overlap already leaks
    ok &= flag("2024-09-01", "2025-01-31", "gpt-5")["corpus"] == "pre_cutoff"
    ok &= flag("2026-05-01", "2026-05-30", "some-new-model")["corpus"] == "unknown_model"
    ok &= flag("2026-05-01", "2026-05-30", None)["corpus"] == "not_a_model"
    ok &= flag("2026-05-01", "2026-05-30", "x", cutoff="2026-04")["corpus"] == "post_cutoff"
    print(json.dumps({"self_test": "ok" if ok else "FAIL"}))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="window start YYYY-MM-DD")
    ap.add_argument("--end", help="window end YYYY-MM-DD")
    ap.add_argument("--model", default=None)
    ap.add_argument("--cutoff", default=None, help="override cutoff YYYY-MM")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.start or not args.end:
        print(json.dumps({"error": "usage", "detail": "--start --end required"}))
        return 2
    print(json.dumps(flag(args.start, args.end, args.model, args.cutoff)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
