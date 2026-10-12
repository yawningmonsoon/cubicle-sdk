"""The lab counters — every failure mode gets a runnable counter, not prose.

Each module is a standalone CLI (``python3 -m cubicle_sdk.lab.null_panel
--self-test``) and stdlib-only. They are deliberately scripts rather than a
library API: the discipline they encode is "report only numbers a scorer
emitted", and a script that prints JSON is harder to launder than a function
whose return value a caller can reword.

  null_panel        always-up / random(seed) / with-prev / buy-and-hold
  deflated_sharpe   E[max SR] under N trials + DSR
  calibration       Brier + Murphy reliability/resolution + ECE
  pushback          flip rate under pressure vs a control panel
  pass_k            agreement + score dispersion over identical reruns
  corpus_flag       evaluation window vs declared model cutoff
  one_switch        toggle one input; if alpha vanishes it was never alpha
"""

COUNTERS = [
    "null_panel", "deflated_sharpe", "calibration",
    "pushback", "pass_k", "corpus_flag", "one_switch",
]

__all__ = ["COUNTERS"]
