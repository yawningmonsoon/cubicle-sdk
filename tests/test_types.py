"""The invariants that must not drift from the Rust crate."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cubicle_sdk.types import GateState, HonestyBlock, ReceiptBody, SignedReceipt


def test_unknown_gate_degrades_to_draft():
    # The fail-closed property: a typo cannot mint a price.
    for s in ["", "   ", None, "live", "RESELLER_ELIGIBLE", "Certified"]:
        assert GateState.parse(s) is GateState.DRAFT, s


def test_only_reseller_eligible_may_be_priced():
    assert GateState.RESELLER_ELIGIBLE.may_be_priced
    for g in [GateState.DRAFT, GateState.BACKTESTED, GateState.DURABLE,
              GateState.PARITY, GateState.SHADOW, GateState.LIVE]:
        # Live dispatches real money and STILL may not earn.
        assert not g.may_be_priced, g


def test_ladder_is_seven_rungs_in_order():
    assert GateState.DRAFT.rank() == 0
    assert GateState.RESELLER_ELIGIBLE.rank() == 6
    assert GateState.SHADOW.rank() > GateState.PARITY.rank()


def test_enclave_containment_lifts_at_shadow():
    assert not GateState.PARITY.may_execute_outside_enclave
    assert GateState.SHADOW.may_execute_outside_enclave


def test_durable_predicate_names_the_corpus_flag():
    # DSR corrects for selection, not leakage — the corpus clause must survive.
    p = GateState.BACKTESTED.blocking_predicate()
    assert "corpus flag" in p and "post_cutoff" in p and "clock-stamped" in p
    assert "null panel" in p and "deflated Sharpe" in p


def test_an_empty_honesty_block_reports_every_channel_unmeasured():
    # None means NOT RUN, never "passed".
    assert set(HonestyBlock().unmeasured()) == {
        "determinism", "one_switch", "pass_k", "corpus"}


def test_pre_cutoff_corpus_is_not_clean():
    assert HonestyBlock(corpus="post_cutoff").corpus_is_clean
    for c in ("pre_cutoff", "unknown_model", ""):
        assert not HonestyBlock(corpus=c).corpus_is_clean, c


def test_unsigned_receipt_is_reported_as_unsigned():
    r = SignedReceipt(
        body=ReceiptBody(session_id="s", market="NQ", window="w"),
        sha3_hex="", signature_hex="", signer_address="")
    problems = r.verify_shape()
    assert any("unsigned" in p for p in problems)


def test_verify_shape_flags_unrun_honesty_channels():
    r = SignedReceipt(
        body=ReceiptBody(session_id="s", market="NQ", window="w"),
        sha3_hex="a" * 64, signature_hex="ab", signer_address="0x1")
    assert any("not run" in p for p in r.verify_shape())


def test_a_complete_receipt_has_no_shape_problems():
    r = SignedReceipt(
        body=ReceiptBody(
            session_id="s", market="NQ", window="w",
            honesty=HonestyBlock(determinism_ok=True, one_switch_delta_r=0.0,
                                 corpus="post_cutoff", pass_k=(8, 8))),
        sha3_hex="a" * 64, signature_hex="ab", signer_address="0x1")
    assert r.verify_shape() == []
