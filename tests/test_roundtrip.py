"""The test oracle: the twin generates its own ground truth.

Almost no software project has ground truth.  This one *generates* it - every
parameter SHRUTI is asked to recover is an input to the synthesiser.  So a
property-based test can draw a random configuration, render it, analyse it, and
assert that the recovered values fall inside their own stated bounds.

**Millions of labelled test cases, for free, with no annotation effort.**  That
is the software-engineering form of the whole thesis:

    "We can't run out of test data, because the thing we built to analyse
     signals is the same thing that makes them."
"""

from __future__ import annotations

import numpy as np
import pytest

from shruti.cartridge import load_library
from shruti.core.bits import bits_to_bytes, hard_decision, text_to_bits
from shruti.l4_twin.chain import SynthConfig, synthesise
from shruti.l5_demod import soft_demodulate
from shruti.l6_fec.match import decode_with_cartridge

LIB = load_library()
ALL_IDS = [c.id for c in LIB]
MESSAGE = "SHRUTI round trip. "


def _payload(n: int = 220) -> np.ndarray:
    return text_to_bits(MESSAGE * n)


def _best_decode(cart, samples, fs, sps, rolloff):
    """Sweep the ambiguity set and keep the hypothesis the code accepts."""
    best = None
    for d in soft_demodulate(samples, cart.build_mapper(), sps, fs, rolloff):
        try:
            res = decode_with_cartridge(cart, d.llr)
        except Exception:                                      # noqa: BLE001
            continue
        txt = bits_to_bytes(res.payload_bits).decode("utf-8", errors="replace")
        score = (2 if txt.startswith(MESSAGE[:12]) else 0) + (1 if res.ok else 0)
        if best is None or score > best[0]:
            best = (score, res, txt)
    return best


def test_library_loads_without_errors():
    assert len(LIB) >= 8
    assert LIB.errors == [], f"cartridges failed to load: {LIB.errors}"


@pytest.mark.parametrize("cart_id", ALL_IDS)
def test_payload_round_trips(cart_id):
    """synth -> demod -> decode must return the exact payload, with a certificate."""
    cart = LIB.by_id(cart_id)
    r = synthesise(cart, _payload(), SynthConfig(sps=8, snr_db=25, cfo_hz=137.0, seed=3))
    best = _best_decode(cart, r.samples, r.fs, r.sps, cart.rolloff)
    assert best is not None, f"{cart_id}: no hypothesis decoded at all"
    _, res, txt = best
    assert txt.startswith(MESSAGE[:12]), f"{cart_id}: payload not recovered ({txt[:40]!r})"
    assert res.ok, f"{cart_id}: payload recovered but no decode certificate issued"


@pytest.mark.parametrize("cart_id", ALL_IDS)
def test_demodulates_to_zero_ber(cart_id):
    """The channel bits must come back exactly under some ambiguity hypothesis."""
    cart = LIB.by_id(cart_id)
    r = synthesise(cart, _payload(120), SynthConfig(sps=8, snr_db=25, cfo_hz=137.0, seed=3))
    truth = r.stages["channel_bits"]
    best = 1.0
    for d in soft_demodulate(r.samples, cart.build_mapper(), r.sps, r.fs, cart.rolloff):
        rec = hard_decision(d.llr)
        n = min(len(rec), len(truth)) - 32
        if n > 100:
            best = min(best, float(np.count_nonzero(rec[:n] != truth[:n]) / n))
    assert best == 0.0, f"{cart_id}: best hypothesis still had BER {best:.5f}"


@pytest.mark.parametrize("cfo", [0.0, 5.0, 137.0, 900.0])
def test_cfo_estimation_including_zero(cfo):
    """CFO near zero is the case a naive M-th power estimator silently fails on."""
    cart = LIB.by_id("generic/qpsk-9600-conv")
    r = synthesise(cart, _payload(120), SynthConfig(sps=8, snr_db=25, cfo_hz=cfo, seed=3))
    truth = r.stages["channel_bits"]
    best = 1.0
    for d in soft_demodulate(r.samples, cart.build_mapper(), r.sps, r.fs, cart.rolloff):
        rec = hard_decision(d.llr)
        n = min(len(rec), len(truth)) - 32
        if n > 100:
            best = min(best, float(np.count_nonzero(rec[:n] != truth[:n]) / n))
    assert best == 0.0, f"CFO {cfo} Hz: BER {best:.5f}"


@pytest.mark.parametrize("seed", range(6))
def test_property_random_configuration(seed):
    """Draw a random cartridge and channel; the payload must survive."""
    rng = np.random.default_rng(seed)
    cart = LIB.by_id(str(rng.choice(ALL_IDS)))
    cfg = SynthConfig(
        sps=8,
        snr_db=float(rng.uniform(22, 32)),
        cfo_hz=float(rng.uniform(-0.01, 0.01) * cart.symbol_rate),
        timing_offset=float(rng.uniform(0, 1)),
        seed=int(rng.integers(1 << 20)),
    )
    r = synthesise(cart, _payload(), cfg)
    best = _best_decode(cart, r.samples, r.fs, r.sps, cart.rolloff)
    assert best is not None
    assert best[2].startswith(MESSAGE[:12]), (
        f"{cart.id} @ SNR {cfg.snr_db:.1f} dB, CFO {cfg.cfo_hz:.1f} Hz: "
        f"payload lost ({best[2][:40]!r})"
    )


def test_reencode_agreement_discriminates():
    """The right code reproduces the stream; a wrong one lands near the covering radius.

    This is the scoring signal the whole library match rests on, so the gap
    between right and wrong is worth asserting rather than assuming.
    """
    cart = LIB.by_id("generic/qpsk-9600-conv")
    r = synthesise(cart, _payload(), SynthConfig(sps=8, snr_db=25, cfo_hz=137.0, seed=3))
    hyps = soft_demodulate(r.samples, cart.build_mapper(), r.sps, r.fs, cart.rolloff)

    def best_agreement(candidate):
        out = 0.0
        for d in hyps:
            try:
                res = decode_with_cartridge(candidate, d.llr)
            except Exception:                                  # noqa: BLE001
                continue
            if np.isfinite(res.reencode_agreement):
                out = max(out, res.reencode_agreement)
        return out

    right = best_agreement(cart)
    wrong = max(
        best_agreement(c) for c in LIB
        if c.id != cart.id and c.blocks.get("fec", {}).get("type") == "convolutional"
    )
    assert right > 0.99, f"correct cartridge only reached {right:.3f}"
    assert right - wrong > 0.05, f"gap too small: right {right:.3f} vs wrong {wrong:.3f}"


def test_wrong_coded_cartridge_cannot_outscore_a_correct_uncoded_one():
    """The null for a decoder output is the covering radius, not a coin flip.

    A convolutional decoder returns the nearest codeword even to noise, so a
    WRONG coded cartridge reaches ~0.87 agreement for free. Scored against 0.5
    that looked like strong evidence and beat a CORRECT uncoded cartridge, which
    has no code evidence to offer at all.
    """
    from shruti.l6_fec.match import COVERING_RADIUS, match_library
    from shruti.l5_demod import soft_demodulate

    cart = LIB.by_id("generic/2fsk-1200")
    r = synthesise(cart, _payload(), SynthConfig(sps=8, snr_db=24, cfo_hz=200.0,
                                                 timing_offset=0.6, seed=11))
    best: dict[str, float] = {}
    for c in LIB:
        sps = max(2, int(round(r.fs / c.symbol_rate))) if c.symbol_rate else 8
        if sps > 64:
            continue
        for d in soft_demodulate(r.samples, c.build_mapper(), sps, r.fs, c.rolloff):
            for m in match_library(d.llr, [c], top=1):
                best[m.cartridge_id] = max(best.get(m.cartridge_id, -1e9), m.score)

    assert best, "no cartridge scored at all"
    winner = max(best, key=best.get)
    assert winner == cart.id, f"{winner} outscored the truth: {best}"
    assert 0.8 < COVERING_RADIUS < 0.95
