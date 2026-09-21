"""Unit tests for the primitives everything else stands on."""

from __future__ import annotations

import numpy as np
import pytest

from shruti.core.bits import bits_to_bytes, bytes_to_bits, column_entropy, hard_decision
from shruti.core.gf2 import BitMatrix, is_codeword, nullspace, pack, rank, rank_profile, unpack
from shruti.core.stats import binomial_bias_test, goodness_of_fit, os_cfar, whiteness_test
from shruti.l4_twin.modulation import FSK, PSK, QAM
from shruti.l4_twin.shaping import rrc_taps
from shruti.l6_fec.conv import standard_code
from shruti.l6_fec.interleave import (
    BlockInterleaver, ConvolutionalInterleaver, DiagonalInterleaver, PseudoRandomInterleaver,
)
from shruti.l6_fec.ldpc import LDPCCode
from shruti.l6_fec.rs import RS_255_223, RS_255_239, ReedSolomon
from shruti.l6_fec.scramble import CCSDS_RANDOMISER, SelfSyncScrambler
from shruti.l7_bits import analyse_frames, profile_fields


# ------------------------------------------------------------------- GF(2)

def test_pack_unpack_roundtrip():
    x = np.random.default_rng(0).integers(0, 2, (7, 150)).astype(np.uint8)
    assert (unpack(pack(x), 150) == x).all()


def test_nullspace_is_the_dual_code():
    rng = np.random.default_rng(0)
    k, n, N = 5, 12, 40
    G = rng.integers(0, 2, (k, n)).astype(np.uint8)
    while rank(BitMatrix.from_bits(G)) < k:
        G = rng.integers(0, 2, (k, n)).astype(np.uint8)
    cw = (rng.integers(0, 2, (N, k)).astype(np.uint8) @ G) & 1

    assert rank(BitMatrix.from_bits(cw)) == k
    H = nullspace(BitMatrix.from_bits(cw))
    assert H.shape == (n - k, n)
    assert is_codeword(cw, H).all()
    bad = cw.copy()
    bad[0, 0] ^= 1
    assert not is_codeword(bad, H)[0]


def test_rank_profile_finds_codeword_length():
    """Rank deficiency at the true n is the blind code-detection mechanism."""
    rng = np.random.default_rng(1)
    k, n = 5, 12
    G = rng.integers(0, 2, (k, n)).astype(np.uint8)
    while rank(BitMatrix.from_bits(G)) < k:
        G = rng.integers(0, 2, (k, n)).astype(np.uint8)
    stream = ((rng.integers(0, 2, (60, k)).astype(np.uint8) @ G) & 1).reshape(-1)

    _, rk_true = rank_profile(stream, n)
    assert rk_true == k
    for wrong in (10, 11, 13):
        _, rk = rank_profile(stream, wrong)
        assert rk == wrong, f"n={wrong} should be full rank, got {rk}"


# --------------------------------------------------------------- convolutional

@pytest.mark.parametrize(
    "name", ["ccsds-k7-r12", "nasa-k7-r12", "k9-r12", "k5-r12", "k3-r12",
             "ccsds-k7-r23", "ccsds-k7-r34", "ccsds-k7-r78"],
)
@pytest.mark.parametrize("length", [500, 2000, 4097])
def test_convolutional_roundtrip(name, length):
    from shruti.l6_fec.conv import decode_hard
    rng = np.random.default_rng(1)
    c = standard_code(name)
    msg = rng.integers(0, 2, length).astype(np.uint8)
    dec = decode_hard(c, c.encode(msg))
    assert len(dec) == len(msg)
    assert (dec == msg).all()


def test_soft_viterbi_gives_coding_gain():
    rng = np.random.default_rng(7)
    c = standard_code("ccsds-k7-r12")
    msg = rng.integers(0, 2, 8000).astype(np.uint8)
    enc = c.encode(msg)
    sigma = np.sqrt(1 / (2 * (10 ** 0.4) * c.code_rate))     # 4 dB Eb/N0
    rx = (1 - 2 * enc.astype(float)) + rng.normal(0, sigma, len(enc))
    dec, _ = c.decode(2 * rx / sigma ** 2)
    assert np.count_nonzero(dec != msg) == 0


# ------------------------------------------------------------------------- RS

@pytest.mark.parametrize("rs", [RS_255_223, RS_255_239, ReedSolomon(n=63, k=55)])
def test_rs_corrects_to_t_and_declines_beyond(rs):
    rng = np.random.default_rng(3)
    msg = rng.integers(0, 256, rs.k).astype(np.uint8)
    cw = rs.encode_block(msg)
    assert (cw[: rs.k] == msg).all(), "RS must be systematic"

    r = rs.decode_block(cw)
    assert r.ok and r.corrected == 0

    for nerr in (1, max(1, rs.t // 2), rs.t):
        bad = cw.copy()
        pos = rng.choice(rs.n, nerr, replace=False)
        bad[pos] ^= rng.integers(1, 256, nerr).astype(np.uint8)
        res = rs.decode_block(bad)
        assert res.ok and (res.message == msg).all(), f"failed at {nerr} errors"

    bad = cw.copy()
    pos = rng.choice(rs.n, rs.t + 1, replace=False)
    bad[pos] ^= rng.integers(1, 256, rs.t + 1).astype(np.uint8)
    # Beyond t it must DECLINE, not miscorrect into a confident wrong answer.
    assert not rs.decode_block(bad).ok


# ----------------------------------------------------------------------- LDPC

def test_ldpc_is_regular_and_decodes():
    c = LDPCCode(n=504, wc=3, wr=6, seed=42)
    H = c.parity_checks()
    assert set(H.sum(1).tolist()) == {6}, "row weights must be regular"
    assert set(H.sum(0).tolist()) == {3}, "weight-0 columns are bits in no check at all"

    ov = H.astype(np.int32) @ H.T.astype(np.int32)
    np.fill_diagonal(ov, 0)
    assert int((ov >= 2).sum()) == 0, "4-cycles cripple belief propagation"

    rng = np.random.default_rng(9)
    msg = rng.integers(0, 2, c.k).astype(np.uint8)
    cw = c.encode(msg)
    assert int(((H @ cw) & 1).sum()) == 0
    assert (c.extract_message(cw) == msg).all()

    sigma = np.sqrt(1 / (2 * (10 ** 0.4) * c.rate))
    rx = (1 - 2 * cw.astype(float)) + rng.normal(0, sigma, c.n)
    res = c.decode(2 * rx / sigma ** 2, max_iter=50)
    assert res.converged and (res.message == msg).all()


# --------------------------------------------------------------- interleavers

@pytest.mark.parametrize(
    "il",
    [BlockInterleaver(40, 72), DiagonalInterleaver(40, 72),
     BlockInterleaver(5, 255, 8), PseudoRandomInterleaver(1152, seed=0xBAD)],
)
def test_interleaver_roundtrip(il):
    bits = np.random.default_rng(5).integers(0, 2, il.period * 3).astype(np.uint8)
    assert (il.deinterleave(il.interleave(bits)) == bits).all()
    assert np.count_nonzero(il.interleave(bits) != bits) > 0, "must actually permute"


def test_symbol_wise_interleaver_preserves_byte_boundaries():
    """CCSDS RS interleaving permutes GF(256) symbols, not bits."""
    b = BlockInterleaver(5, 255, symbol_bits=8)
    p = b.permutation()
    assert sorted(p.tolist()) == list(range(len(p)))
    assert all((p[i * 8:(i + 1) * 8] // 8 == p[i * 8] // 8).all() for i in range(len(p) // 8))


def test_block_and_diagonal_differ():
    """Same period, different in-period pattern - that is the discriminator."""
    a = BlockInterleaver(24, 36).permutation()
    d = DiagonalInterleaver(24, 36).permutation()
    assert len(a) == len(d)
    assert not (a == d).all()


def test_convolutional_interleaver_has_no_frame_boundary():
    ci = ConvolutionalInterleaver(branches=6, delay=4)
    bits = np.random.default_rng(5).integers(0, 2, 4000).astype(np.uint8)
    z = ci.deinterleave(ci.interleave(bits))
    lat = ci.latency
    assert (z[lat:len(bits)] == bits[:len(bits) - lat]).all()
    with pytest.raises(NotImplementedError):
        ci.permutation()


# ----------------------------------------------------------------- scramblers

def test_additive_scrambler_is_an_involution():
    bad = np.concatenate([np.zeros(600, np.uint8), np.ones(600, np.uint8)])
    y = CCSDS_RANDOMISER.apply(bad)
    assert (CCSDS_RANDOMISER.descramble(y) == bad).all()
    # Its job is transition density; check it actually delivers.
    assert np.count_nonzero(np.diff(y)) / len(y) > 0.4


def test_self_sync_scrambler_multiplies_errors():
    ss = SelfSyncScrambler((18, 23))
    rng = np.random.default_rng(0)
    y = ss.apply(rng.integers(0, 2, 4000).astype(np.uint8))
    y2 = y.copy()
    y2[2000] ^= 1
    n = np.count_nonzero(ss.descramble(y) != ss.descramble(y2))
    assert n == len(ss.taps) + 1, "one channel error must become taps+1"


# --------------------------------------------------------------- modulations

@pytest.mark.parametrize(
    "mod",
    [PSK(2), PSK(4), PSK(8), PSK(4, differential=True), PSK(4, pi4=True),
     QAM(16), QAM(32), QAM(64)],
)
def test_modulation_noiseless_roundtrip(mod):
    rng = np.random.default_rng(2)
    n = 6000 // mod.bits_per_symbol * mod.bits_per_symbol
    bits = rng.integers(0, 2, n).astype(np.uint8)
    rec = hard_decision(mod.demap_llr(mod.map(bits), 0.01))[:n]
    assert (rec == bits[:len(rec)]).all(), f"{mod.describe()} failed"


def test_fsk_renders_constant_envelope():
    f = FSK(4, h=1.0)
    x = f.render(np.random.default_rng(0).integers(0, 2, 1000).astype(np.uint8),
                 sps=8, symbol_rate=1200, fs=9600)
    assert np.allclose(np.abs(x), 1.0)
    assert not f.is_linear


def test_rrc_is_nyquist():
    """Cascaded RRC must have zero ISI at the symbol instants."""
    h = rrc_taps(8, 0.35, 10)
    assert abs(np.sum(h ** 2) - 1.0) < 1e-9
    rc = np.convolve(h, h)
    c = len(rc) // 2
    taps = np.abs(rc[c - 24:c + 25:8])
    taps[3] = 0
    assert taps.max() < 1e-3


# ------------------------------------------------------------------ statistics

def test_goodness_of_fit_separates_noise_from_structure():
    rng = np.random.default_rng(0)
    nv = 0.01
    noise = np.sqrt(nv / 2) * (rng.normal(size=4000) + 1j * rng.normal(size=4000))
    good = goodness_of_fit(noise, nv)
    assert good.p_value > 0.01 and good.consistent_with_noise

    structured = noise + 0.35 * np.exp(2j * np.pi * 0.05 * np.arange(4000))
    bad = goodness_of_fit(structured, nv)
    assert bad.p_value < 0.01 and not bad.consistent_with_noise


def test_binomial_test_detects_syndrome_bias():
    assert binomial_bias_test(500, 1000) > 0.05          # chance
    assert binomial_bias_test(900, 1000) < 1e-30         # a real parity check


def test_whiteness_test_flags_structure():
    rng = np.random.default_rng(0)
    _, p_white = whiteness_test(rng.normal(size=3000))
    t = np.arange(3000)
    _, p_tone = whiteness_test(np.sin(2 * np.pi * 0.03 * t))
    assert p_white > 0.01
    assert p_tone < 0.01


def test_os_cfar_finds_a_peak_not_the_noise():
    rng = np.random.default_rng(0)
    p = np.abs(rng.normal(size=2000)) ** 2
    p[900:906] += 60.0
    det, _ = os_cfar(p)
    assert det[900:906].any()
    assert det.sum() < 60, "CFAR should not fire all over the noise floor"


# ------------------------------------------------------------------------- L7

def test_frame_and_field_recovery():
    """The header/payload boundary must land exactly where it was built."""
    rng = np.random.default_rng(1)
    sync = np.unpackbits(np.frombuffer(bytes.fromhex("1ACFFC1D"), np.uint8))
    frames = []
    for i in range(80):
        ctr = np.unpackbits(np.array([i >> 8, i & 255], np.uint8))
        addr = np.unpackbits(np.frombuffer(bytes.fromhex("00A5"), np.uint8))
        frames.append(np.concatenate([sync, ctr, addr,
                                      rng.integers(0, 2, 192).astype(np.uint8)]))
    stream = np.concatenate(frames)

    fa = analyse_frames(stream)
    assert fa.period_bits == 256, f"expected the fundamental 256, got {fa.period_bits}"
    assert fa.n_frames == 80
    assert fa.sync_hex().startswith("1ACFFC1D")

    fm = profile_fields(stream, fa.period_bits)
    payload = [f for f in fm.fields if f.kind.value in ("payload", "encrypted_or_compressed")]
    assert payload, "no payload region identified"
    assert payload[-1].start + payload[-1].length == 256
    assert fm.payload_entropy > 0.95


def test_column_entropy_matches_construction():
    rng = np.random.default_rng(0)
    period = 32
    m = np.zeros((200, period), dtype=np.uint8)
    m[:, 16:] = rng.integers(0, 2, (200, 16))
    ent = column_entropy(m.reshape(-1), period)
    assert ent[:16].max() < 0.01
    assert ent[16:].min() > 0.9


def test_bytes_bits_roundtrip():
    data = b"SHRUTI"
    assert bits_to_bytes(bytes_to_bits(data)) == data
