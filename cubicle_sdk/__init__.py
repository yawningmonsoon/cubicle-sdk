"""cubicle-sdk — the Cubicle evidence toolkit.

Three things:

- :mod:`cubicle_sdk.mcp` — the Cubicle MCP server from Python or a terminal: join, reverse-engineer what was
  posted, read, forge, rehearse on recorded bars.
- :mod:`cubicle_sdk.types` — the wire vocabulary (gate ladder, honesty block,
  receipt shapes), mirroring the Rust `cubicle-protocol` crate.
- :mod:`cubicle_sdk.lab` — the runnable counters. Every one is stdlib-only,
  deterministic, and ships a ``--self-test``.

What is NOT here, and why: there is no signer and no session driver. Receipts are signed venue-side; a client-side signer would let
anything mint one. Shipping an inert stub would be worse than shipping
nothing, so this package ships nothing there until the wire exists.
"""

__version__ = "0.2.0"

from cubicle_sdk.types import (  # noqa: F401
    CausalityBlock,
    GateState,
    HonestyBlock,
    ReceiptBody,
    SignedReceipt,
    SkillLine,
    gate_from_metadata,
)

__all__ = [
    "GateState", "HonestyBlock", "CausalityBlock",
    "ReceiptBody", "SignedReceipt", "SkillLine",
    "gate_from_metadata", "__version__",
]
