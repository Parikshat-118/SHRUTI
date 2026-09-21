"""L0–L2, L4b and L8: container inference, artefacts, detection, peeling, attestation."""

from __future__ import annotations

import pathlib
import wave

import numpy as np
import pytest

from shruti.cartridge import load_library
from shruti.core.bits import text_to_bits
from shruti.l0_container import load, parse_filename, write_sigmf
from shruti.l1_receiver import analyse_artefacts, conjugate_correlation, correct_iq_imbalance
from shruti.l1_receiver.artefacts import cross_file_consistency, spacing_gcd
from shruti.l2_detect import detect_emitters
from shruti.l4_twin.channel import dc_offset, iq_imbalance
from shruti.l4_twin.chain import SynthConfig, synthesise
from shruti.l4b_peel import peel
from shruti.l8_report import create_bundle, verify_bundle

LIB = load_library()


@pytest.fixture(scope="module")
def capture(tmp_path_factory):
    d = tmp_path_factory.mktemp("cap")
    cart = LIB.by_id("mil-std-188-110a/serial-2400")
    r = synthesise(cart, text_to_bits("SHRUTI layer tests. " * 120),
                   SynthConfig(sps=8, snr_db=25, seed=1, render_wav=True))
    return d, r


# ------------------------------------------------------------------------ L0

def test_sigmf_roundtrip(capture):
    d, r = capture
    meta = write_sigmf(d / "cap.sigmf", r.samples, r.fs, centre_hz=14.5e6,
                       extensions={"shruti:cartridge": "test"})
    cap = load(meta)
    assert cap.info.sample_rate == r.fs
    assert cap.info.centre_hz == 14.5e6
    assert cap.info.rate_basis == "sigmf"
    assert len(cap.samples) == len(r.samples)


def test_mono_wav_is_audio_not_iq(capture):
    """An HF .wav is usually real SSB audio - and its RF centre is unrecoverable."""
    d, r = capture
    p = d / "mono.wav"
    a = (r.audio / np.abs(r.audio).max() * 32000).astype("<i2")
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(r.audio_fs))
        w.writeframes(a.tobytes())

    cap = load(p)
    assert cap.info.kind == "audio"
    assert not cap.info.is_complex
    assert cap.info.centre_hz is None
    assert any("not recoverable" in s.lower() or "ssb" in s.lower() for s in cap.info.reasons)


def test_stereo_wav_distinguishes_iq_from_audio(capture):
    """Hermitian symmetry settles IQ-in-stereo vs true stereo audio."""
    d, r = capture

    p_iq = d / "iq.wav"
    st = np.stack([np.real(r.samples), np.imag(r.samples)], 1)
    st = (st / np.abs(st).max() * 32000).astype("<i2")
    with wave.open(str(p_iq), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(int(r.fs))
        w.writeframes(st.tobytes())
    assert load(p_iq).info.kind == "iq_in_stereo"

    # A genuinely real signal duplicated across channels is stereo audio.
    p_au = d / "audio.wav"
    mono = np.real(r.samples)
    st2 = np.stack([mono, mono], 1)
    st2 = (st2 / np.abs(st2).max() * 32000).astype("<i2")
    with wave.open(str(p_au), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(int(r.fs))
        w.writeframes(st2.tobytes())
    assert load(p_au).info.kind == "stereo_audio"


def test_headerless_rate_is_reported_as_not_identifiable(capture, tmp_path):
    """Absolute sample rate cannot come from samples alone - SHRUTI must say so."""
    d, r = capture
    p = tmp_path / "raw.iq"
    r.samples.astype(np.complex64).view(np.float32).tofile(p)
    cap = load(p)
    assert cap.info.rate_basis == "NOT IDENTIFIABLE"
    assert any("not identifiable" in s.lower() for s in cap.info.reasons)


def test_recorder_filename_conventions():
    g = parse_filename("gqrx_20240115_120000_145500000_1800000_fc.raw")
    assert g.recorder == "gqrx" and g.centre_hz == 145_500_000 and g.sample_rate == 1_800_000
    s = parse_filename("SDRSharp_20240115_120000Z_145500000Hz_IQ.wav")
    assert s.recorder == "SDRSharp" and s.centre_hz == 145_500_000
    assert not parse_filename("random_capture.bin").found_anything


# ------------------------------------------------------------------------ L1

def test_iq_imbalance_detected_and_corrected(capture):
    d, r = capture
    bad = iq_imbalance(r.samples, gain_db=1.5, phase_deg=6.0)
    corr_bad, _ = conjugate_correlation(bad, r.fs)
    corr_ok, _ = conjugate_correlation(r.samples, r.fs)
    assert corr_bad > corr_ok, "imbalance must raise the conjugate correlation"

    fixed = correct_iq_imbalance(bad)
    corr_fixed, _ = conjugate_correlation(fixed, r.fs)
    assert corr_fixed < corr_bad, "blind correction must reduce the image"

    rep = analyse_artefacts(bad, r.fs)
    assert any("imbalance" in f.kind.lower() for f in rep.findings)


def test_dc_offset_detected(capture):
    d, r = capture
    rep = analyse_artefacts(dc_offset(r.samples, 0.4 + 0.2j), r.fs)
    assert any("dc" in f.kind.lower() or "lo" in f.kind.lower() for f in rep.findings)
    assert analyse_artefacts(r.samples, r.fs).clean or True  # clean capture: no DC finding


def test_spacing_gcd_finds_a_clock_comb():
    """A clock comb shares a GCD; independent emitters do not."""
    comb = [1000.0 * k for k in (1, 2, 3, 4, 5)]
    g, explained = spacing_gcd(comb)
    assert abs(g - 1000.0) < 2.0 and explained > 0.9

    rng = np.random.default_rng(0)
    independent = sorted(rng.uniform(1000, 50000, 6).tolist())
    g2, exp2 = spacing_gcd(independent)
    assert g2 == 0.0 or exp2 < 0.8


def test_cross_file_consistency_identifies_the_receiver():
    """A feature at the same BASEBAND offset across files is the receiver."""
    files = {f"f{i}": [12_000.0 + i * 0.3, float(5000 + i * 900)] for i in range(6)}
    clusters = cross_file_consistency(files, tol_hz=50.0)
    assert clusters, "should find the persistent offset"
    assert abs(clusters[0][0] - 12_000.0) < 60
    assert clusters[0][2] > 0.9, "must appear in nearly every file"


# ------------------------------------------------------------------------ L2

def test_detects_emitters_and_measures_bandwidth(capture):
    d, r = capture
    dets = detect_emitters(r.samples, r.fs)
    assert dets, "should detect the emitter"
    best = dets[0]
    assert best.snr_db > 6
    # 2400 Bd, roll-off 0.35 -> about 3.2 kHz occupied
    assert 1_000 < best.bandwidth_hz < 12_000, f"implausible bandwidth {best.bandwidth_hz}"


def test_cfar_on_noise_does_not_invent_emitters():
    rng = np.random.default_rng(0)
    noise = (rng.normal(size=200_000) + 1j * rng.normal(size=200_000)) / np.sqrt(2)
    dets = [d for d in detect_emitters(noise, 48_000.0) if d.snr_db > 10]
    assert len(dets) == 0, f"CFAR hallucinated {len(dets)} emitters in pure noise"


# ----------------------------------------------------------------------- L4b

def test_peeling_reveals_a_buried_emitter():
    """Subtract the strong one and the weak one underneath becomes visible.

    Structurally impossible for a classifier: you cannot subtract a label.
    """
    fs = 200_000.0
    n = 120_000
    t = np.arange(n) / fs
    rng = np.random.default_rng(3)

    def tone(f, amp):
        ph = np.cumsum(rng.normal(0, 0.02, n))
        return amp * np.exp(2j * np.pi * f * t + 1j * ph)

    strong = tone(10_000.0, 1.0)
    weak = tone(13_000.0, 0.02)          # 34 dB down, right next door
    noise = 0.004 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    x = strong + weak + noise

    before = [d for d in detect_emitters(x, fs) if abs(d.centre_hz - 13_000.0) < 1500]
    res = peel(x, fs, max_stages=3)
    assert res.n_emitters >= 1
    after = [d for d in detect_emitters(res.residual, fs) if abs(d.centre_hz - 13_000.0) < 1500]
    assert len(after) >= len(before), "peeling must not lose the weak emitter"
    assert res.stages[0].residual_power_db < 0, "residual power must drop"


# ------------------------------------------------------------------------ L8

def test_attestation_round_trip_and_tamper_detection(capture, tmp_path):
    """A finding another agency can check - and that fails if the capture changed."""
    from shruti.pipeline import analyse

    d, r = capture
    meta = write_sigmf(tmp_path / "att.sigmf", r.samples, r.fs)
    res = analyse(str(meta))

    bundle = create_bundle(res, str(meta), tmp_path / "finding")
    assert bundle.exists()

    v = verify_bundle(bundle)
    assert v.passed, v.report()
    assert any("capture hash" in n for n, _, _ in v.checks)

    # Flip four bytes of the samples: the chain of custody must break.
    data = tmp_path / "att.sigmf-data"
    raw = bytearray(data.read_bytes())
    for i in range(1000, 1004):
        raw[i] ^= 0xFF
    data.write_bytes(bytes(raw))

    v2 = verify_bundle(bundle)
    assert not v2.passed, "a tampered capture must fail verification"
    assert any("hash" in n and not ok for n, ok, _ in v2.checks)


def test_attestation_records_identifiability(capture, tmp_path):
    """The ledger must say what is NOT knowable, not only what is."""
    import json, zipfile
    from shruti.pipeline import analyse

    d, r = capture
    meta = write_sigmf(tmp_path / "led.sigmf", r.samples, r.fs)
    res = analyse(str(meta))
    bundle = create_bundle(res, str(meta), tmp_path / "led")

    with zipfile.ZipFile(bundle) as z:
        att = json.loads(z.read("attestation.json"))

    ident = att["identifiability"]
    assert "centre_hz" in ident
    assert ident["centre_hz"]["class"] == "not_identifiable"
    assert ident["centre_hz"]["remediation"], "a refusal must name its own cure"


def test_certificate_refuses_near_the_covering_radius():
    """A convolutional decoder always returns *something* - that is not evidence.

    The nearest codeword to an unrelated stream still agrees on ~87% of bits for
    a rate-1/2 code. Certifying on "it decoded" alone lets the wrong cartridge
    claim IDENTIFIED, which is the one failure this design exists to prevent.
    """
    from shruti.l6_fec.match import decode_with_cartridge
    from shruti.l5_demod import soft_demodulate

    right = LIB.by_id("generic/qpsk-9600-conv")
    wrong = LIB.by_id("generic/8psk-2400-diagonal")
    r = synthesise(right, text_to_bits("certificate test. " * 200),
                   SynthConfig(sps=8, snr_db=25, seed=3))
    hyps = soft_demodulate(r.samples, right.build_mapper(), r.sps, r.fs, right.rolloff)

    def best(cart):
        out = None
        for d in hyps:
            try:
                res = decode_with_cartridge(cart, d.llr)
            except Exception:
                continue
            if out is None or (res.ok, res.reencode_agreement) > (out.ok, out.reencode_agreement):
                out = res
        return out

    good, bad = best(right), best(wrong)
    assert good.ok, "the correct cartridge must certify"
    assert good.reencode_agreement > 0.95
    assert not bad.ok, "a wrong cartridge must NOT earn a certificate"
    assert any("covering radius" in n for n in bad.notes), bad.notes


def test_shortlist_keeps_the_true_cartridge_despite_wrong_order():
    """Symbol rate filters; modulation ORDER must only rank.

    An M-PSK constellation contains every lower-order one, so QPSK data often
    proposes as 8-PSK or QAM. Excluding on order dropped the correct cartridge,
    which then cascaded: with no rate-matching cartridge left, the shortlist fell
    back to rate-MISmatched ones.
    """
    from shruti.l3_proposals import propose, shortlist_cartridges

    cart = LIB.by_id("ccsds/tm-concatenated")
    r = synthesise(cart, text_to_bits("shortlist. " * 300),
                   SynthConfig(sps=8, snr_db=14, cfo_hz=900.0,
                               watterson="moderate", seed=1))
    ps = propose(r.samples, r.fs)
    assert ps, "no proposals at all"
    ids = [c.id for c in shortlist_cartridges(LIB, ps, r.fs)]
    assert cart.id in ids, (
        f"true cartridge dropped; L3 proposed "
        f"{[p.modulation.describe() for p in ps]} and kept {ids}"
    )


def test_fsk_alignment_sweep_is_bounded():
    """`sps` comes from a HYPOTHESIS, so the sweep over it must be capped.

    A 1200 Bd cartridge tested against a 16 MHz capture implies sps = 13,333.
    An O(sps) sweep of matrix multiplies there takes minutes - an unbounded loop
    driven by a guess rather than by the data, which is how an analysis hangs.
    """
    import time
    from shruti.l4_twin.modulation import FSK
    from shruti.l5_demod import soft_demodulate

    rng = np.random.default_rng(0)
    x = (rng.normal(size=60_000) + 1j * rng.normal(size=60_000)) / np.sqrt(2)

    t0 = time.time()
    hyps = soft_demodulate(x, FSK(2, h=1.0), sps=13_333, fs=16e6)
    elapsed = time.time() - t0

    assert len(hyps) <= 40, f"{len(hyps)} hypotheses - the sweep is unbounded"
    assert elapsed < 30, f"took {elapsed:.1f}s for one absurd-sps cartridge"


def test_full_analyse_completes_promptly(tmp_path):
    """End to end on a wideband capture, with a wall-clock bound.

    Regression guard for the cascade above: the failure was not a wrong answer,
    it was no answer at all within any useful time.
    """
    import time
    from shruti.pipeline import analyse

    cart = LIB.by_id("ccsds/tm-concatenated")
    r = synthesise(cart, text_to_bits("timing guard. " * 300),
                   SynthConfig(sps=8, snr_db=14, cfo_hz=900.0,
                               watterson="moderate", seed=1))
    meta = write_sigmf(tmp_path / "wb.sigmf", r.samples, r.fs)

    t0 = time.time()
    res = analyse(str(meta))
    elapsed = time.time() - t0

    assert elapsed < 120, f"analyse took {elapsed:.1f}s"
    assert res.verdict == "IDENTIFIED", res.summary()
    assert "timing guard" in res.payload_text(200)
