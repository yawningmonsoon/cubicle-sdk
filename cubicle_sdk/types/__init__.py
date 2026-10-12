"""Cubicle wire types — the vocabulary every plane speaks.

A faithful Python mirror of `cubicle-protocol` (Rust). Types only, by design:
this package never counts, never signs, and never talks to a venue. The
orderbook counts and signs against these shapes; this is what a consumer
reads.

Honesty is structural here, and two rules are load-bearing:

1. **`None` means NOT RUN — never "passed".** Every field of
   :class:`HonestyBlock` is optional, and an unmeasured channel must read as
   absent rather than clean. Code that treats `None` as a pass is the bug this
   design exists to make obvious.
2. **Nothing may present an unsigned receipt as signed.** There is no default
   signer in this package, exactly as there is none in the Rust crate. See
   :class:`SignedReceipt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateState(str, Enum):
    """The seven-rung promotion ladder.

    Ordering is the ladder order, so ``rung >= GateState.SHADOW`` is a
    meaningful capability check via :meth:`rank`.
    """

    DRAFT = "Draft"
    BACKTESTED = "Backtested"
    DURABLE = "Durable"
    PARITY = "Parity"
    SHADOW = "Shadow"
    LIVE = "Live"
    RESELLER_ELIGIBLE = "ResellerEligible"

    @classmethod
    def parse(cls, s: str | None) -> "GateState":
        """Parse a wire spelling. Unknown input is NOT an error — it is DRAFT.

        Deliberate, and mirrors the Rust `GateState::parse`. Every caller is
        deciding what an algo may do; returning an error tempts callers into
        ``or SOMETHING_PERMISSIVE``. Degrading to the least-privileged rung
        means a typo, a truncated file, or a future rung this version does not
        know about all fail in the safe direction.
        """
        try:
            return cls((s or "").strip())
        except ValueError:
            return cls.DRAFT

    def rank(self) -> int:
        return _LADDER.index(self)

    @property
    def may_be_priced(self) -> bool:
        """Whether a skill at this rung may carry a price.

        Exactly one rung qualifies. Note that ``LIVE`` — dispatching real
        money — still may not earn: that requires receipted expectancy, not
        merely permission to trade.
        """
        return self is GateState.RESELLER_ELIGIBLE

    @property
    def may_execute_outside_enclave(self) -> bool:
        """Vendor code stays sandboxed until Shadow (OWASP AST09)."""
        return self.rank() >= GateState.SHADOW.rank()

    def blocking_predicate(self) -> str:
        """The evidence the NEXT rung requires, in the gate's own vocabulary.

        Every predicate names something a script can decide — never a
        reviewer's opinion.
        """
        return _PREDICATES[self]


_LADDER = [
    GateState.DRAFT,
    GateState.BACKTESTED,
    GateState.DURABLE,
    GateState.PARITY,
    GateState.SHADOW,
    GateState.LIVE,
    GateState.RESELLER_ELIGIBLE,
]

_PREDICATES = {
    GateState.DRAFT: "a backtest exists over a declared window",
    # The corpus clause is load-bearing: DSR corrects for SELECTION, not
    # leakage. Run it over a pre-cutoff window and it deflates the wrong
    # thing, certifying a memorized backtest.
    GateState.BACKTESTED: (
        "corpus flag is post_cutoff (clock-stamped, not prompt-asserted) "
        "AND null panel ran on the SAME window "
        "AND deflated Sharpe > 0 at the trial count from the registry"
    ),
    GateState.DURABLE: "replay(tape).fingerprint == tape.fingerprint (determinism)",
    GateState.PARITY: "shadow-dispatched against live tape with no real orders",
    GateState.SHADOW: "an operator armed it for real dispatch",
    GateState.LIVE: "receipted expectancy clears the bar: signed receipt, n and sum-R stated",
    GateState.RESELLER_ELIGIBLE: "nothing — top of the ladder",
}


@dataclass(frozen=True)
class HonestyBlock:
    """What makes a receipt worth anything.

    Every field states its own absence honestly: ``None`` = not run, never
    "passed". :meth:`unmeasured` names the gaps so a consumer can refuse rather
    than assume.
    """

    #: replay(tape).fingerprint == tape.fingerprint
    determinism_ok: bool | None = None
    #: alpha delta with one input channel toggled (None = not run)
    one_switch_delta_r: float | None = None
    #: "post_cutoff" | "pre_cutoff" | "unknown_model" | "not_a_model"
    corpus: str = "unknown_model"
    #: (passes, runs) across identical sealed reruns
    pass_k: tuple[int, int] | None = None

    def unmeasured(self) -> list[str]:
        """Channels that were not run. A non-empty list is not a failure —
        it is the honest statement that the receipt does not cover them."""
        gaps = []
        if self.determinism_ok is None:
            gaps.append("determinism")
        if self.one_switch_delta_r is None:
            gaps.append("one_switch")
        if self.pass_k is None:
            gaps.append("pass_k")
        if self.corpus in ("unknown_model", ""):
            gaps.append("corpus")
        return gaps

    @property
    def corpus_is_clean(self) -> bool:
        """True only for an explicitly post-cutoff window.

        A pre-cutoff window is contaminated: directional accuracy collapses
        99.26% -> 52.94% across a model cutoff (arXiv 2504.14765), and a
        prompt-imposed cutoff does not help (~98% retained). Only a data-layer
        control counts.
        """
        return self.corpus == "post_cutoff"


@dataclass(frozen=True)
class CausalityBlock:
    """Three-actor cross-check: dispatcher <-> strategy <-> book."""

    ticks_dispatched: int = 0
    decisions: int = 0
    orphan_decisions: int = 0
    fills: int = 0
    causality_ok: bool = False


@dataclass(frozen=True)
class SkillLine:
    skill_id: str
    unit: str
    calls: int
    usdc_micros: int = 0


@dataclass(frozen=True)
class ReceiptBody:
    """The receipt's content, before any signature."""

    session_id: str
    market: str
    window: str
    speed_x: int = 1
    causality: CausalityBlock = field(default_factory=CausalityBlock)
    honesty: HonestyBlock = field(default_factory=HonestyBlock)
    skills: list[SkillLine] = field(default_factory=list)
    pnl_r: float | None = None
    #: Always "attributed" until real-money accounting says otherwise.
    pnl_basis: str = "attributed"


@dataclass(frozen=True)
class SignedReceipt:
    """A receipt plus its signature.

    There is deliberately **no signer in this package**. Signing happens
    venue-side with the settlement key; a client-side signer would let anything
    mint a receipt, which defeats the entire point. :meth:`verify_shape` checks
    the envelope is well-formed — it does NOT verify the cryptography, and
    says so rather than implying otherwise.
    """

    body: ReceiptBody
    sha3_hex: str
    signature_hex: str
    signer_address: str

    def verify_shape(self) -> list[str]:
        """Structural problems with this receipt. Empty means well-formed.

        This is NOT signature verification. A well-formed envelope with a
        forged signature passes this check — verification requires the venue's
        public key and is not implemented here.
        """
        problems = []
        if not self.signature_hex or not self.signer_address:
            problems.append("unsigned: no signature or signer address")
        if len(self.sha3_hex) != 64:
            problems.append(f"sha3_hex is {len(self.sha3_hex)} chars, expected 64")
        if self.body.pnl_basis != "attributed" and self.body.pnl_r is not None:
            problems.append(f"pnl_basis {self.body.pnl_basis!r} with a pnl_r — check the accounting")
        gaps = self.body.honesty.unmeasured()
        if gaps:
            problems.append("honesty channels not run: " + ", ".join(gaps))
        return problems


def gate_from_metadata(metadata: dict[str, Any]) -> GateState:
    """Read the gate from a skill's frontmatter metadata, failing closed."""
    return GateState.parse(metadata.get("cubicle-gate"))


__all__ = [
    "GateState",
    "HonestyBlock",
    "CausalityBlock",
    "SkillLine",
    "ReceiptBody",
    "SignedReceipt",
    "gate_from_metadata",
]
