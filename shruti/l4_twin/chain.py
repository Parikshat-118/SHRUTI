"""The twin's forward pass: cartridge + payload -> samples.

This is the generative model at the centre of SHRUTI.  Running it forward
synthesises a capture; inverting it against an unknown capture is the analysis.

Two properties fall out of having it, and neither is available to a design that
only classifies:

* **Verification by resynthesis.**  After analysis, re-encode the recovered bits,
  re-render, and difference against the original samples.  When that difference
  is noise, the analysis is demonstrated rather than asserted.
* **The test oracle.**  Every recovered parameter is an input here, so a
  property-based test can draw a random configuration, render it, analyse it and
  assert the recovered values land inside their own stated error bars.

Every intermediate stage is retained in :class:`SynthResult.stages`.  That is not
debugging convenience - it is what makes **provenance brushing** possible: click
a decoded byte in the GUI and the exact symbols and samples that carried it light
up, because the mapping between layers was recorded when they were built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..cartridge.schema import Cartridge
from ..core.bits import bits_to_bytes, bytes_to_bits
from . import channel as chan
from .modulation import FSK
from .shaping import filter_delay, pulse_shape
from .ssb import to_ssb_audio

__all__ = ["SynthResult", "SynthConfig", "synthesise", "insert_sync", "strip_sync"]


@dataclass
class SynthConfig:
    """Channel and front-end conditions for one render."""

    fs: float | None = None            #: sample rate; default = sps * symbol_rate
    sps: int = 8                       #: samples per symbol
    snr_db: float = 20.0
    cfo_hz: float = 0.0
    phase0: float = 0.0
    timing_offset: float = 0.0         #: fractional-sample delay
    freq_offset_hz: float = 0.0        #: where in the band to place the emitter
    watterson: str | None = None       #: ITU-R F.1487 condition name
    iq_imbalance: tuple[float, float] | None = None    #: (gain dB, phase deg)
    dc_offset: complex | None = None
    phase_noise_dbc: float | None = None
    render_wav: bool = False           #: also produce the SSB-audio view
    seed: int = 0

    def rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed)


@dataclass
class SynthResult:
    """A rendered capture plus the ground truth that produced it."""

    samples: np.ndarray
    fs: float
    sps: int
    truth: dict[str, Any] = field(default_factory=dict)
    stages: dict[str, np.ndarray] = field(default_factory=dict)
    audio: np.ndarray | None = None
    audio_fs: float | None = None

    @property
    def n_samples(self) -> int:
        return len(self.samples)

    @property
    def duration_s(self) -> float:
        return len(self.samples) / self.fs

    def summary(self) -> str:
        t = self.truth
        return (
            f"{t.get('cartridge_id','?')}: {t.get('modulation','?')} @ "
            f"{t.get('symbol_rate_bd',0):g} Bd, {self.duration_s:.2f} s, "
            f"{self.n_samples} samples @ {self.fs:g} Hz, SNR {t.get('snr_db','?')} dB"
        )


def insert_sync(bits: np.ndarray, marker: np.ndarray, period_bits: int) -> np.ndarray:
    """Prepend `marker` to each frame, so markers recur every `period_bits`.

    This is CCSDS's Attached Sync Marker arrangement, and it is what makes
    frame-structure recovery tractable: a fixed pattern at a fixed period produces a comb
    of autocorrelation peaks whose spacing is the frame length.
    """
    bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
    marker = np.asarray(marker, dtype=np.uint8).reshape(-1)
    payload_per_frame = max(1, period_bits - len(marker))
    nframes = int(np.ceil(len(bits) / payload_per_frame))
    pad = nframes * payload_per_frame - len(bits)
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, np.uint8)])
    frames = bits.reshape(nframes, payload_per_frame)
    out = np.concatenate([np.tile(marker, (nframes, 1)), frames], axis=1)
    return out.reshape(-1)


def strip_sync(bits: np.ndarray, marker_len: int, period_bits: int) -> np.ndarray:
    """Inverse of :func:`insert_sync`, tolerating a partial final frame.

    A real demodulator returns slightly fewer bits than were transmitted - the
    filter tails and timing recovery cost a few symbols at each end.  So the
    received stream is almost never an exact multiple of the frame period, and a
    ``len // period`` that rounds to zero would pass the sync marker straight
    through as if it were payload.  That failure is nearly invisible: the payload
    is still there, offset by exactly the marker length.
    """
    bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if period_bits <= marker_len:
        return bits
    out = [bits[i + marker_len : i + period_bits] for i in range(0, len(bits), period_bits)]
    return np.concatenate(out) if out else bits


def _encode_bits(code, bits: np.ndarray) -> np.ndarray:
    """Run a FEC encoder, adapting bit-oriented and symbol-oriented codes."""
    from ..l6_fec.conv import ConvCode
    from ..l6_fec.ldpc import LDPCCode
    from ..l6_fec.rs import ReedSolomon

    if isinstance(code, ConvCode):
        return code.encode(bits)
    if isinstance(code, LDPCCode):
        return code.encode_stream(bits)
    if isinstance(code, ReedSolomon):
        # RS works on GF(256) symbols, so bits must become bytes and back.
        data = np.frombuffer(bits_to_bytes(bits), dtype=np.uint8)
        return bytes_to_bits(code.encode(data).tobytes())
    raise TypeError(f"cannot encode with {type(code).__name__}")


def synthesise(
    cartridge: Cartridge,
    payload_bits: np.ndarray,
    config: SynthConfig | None = None,
) -> SynthResult:
    """Render a capture from a cartridge and a payload.

    The stage order follows the cartridge's declared chain, which is the order
    real systems use - and which for CCSDS is
    ``RS -> interleave -> randomise -> ASM -> convolutional``.
    """
    cfg = config or SynthConfig()
    rng = cfg.rng()
    stages: dict[str, np.ndarray] = {}

    bits = np.asarray(payload_bits, dtype=np.uint8).reshape(-1)
    stages["payload"] = bits.copy()

    # ---- bit layer, in cartridge order --------------------------------------
    outer = cartridge.build_fec_outer()
    if outer is not None:
        bits = _encode_bits(outer, bits)
        stages["fec_outer"] = bits.copy()

    il_outer = cartridge.build_interleaver_outer()
    if il_outer is not None:
        bits = il_outer.interleave(bits)
        stages["interleaver_outer"] = bits.copy()

    scr = cartridge.build_scrambler()
    if scr is not None:
        bits = scr.apply(bits)
        stages["scrambler"] = bits.copy()

    marker = cartridge.sync_word()
    if marker is not None:
        period = cartridge.sync_period or (len(marker) * 32)
        bits = insert_sync(bits, marker, period)
        stages["sync"] = bits.copy()

    inner = cartridge.build_fec()
    if inner is not None:
        bits = _encode_bits(inner, bits)
        stages["fec"] = bits.copy()

    il = cartridge.build_interleaver()
    if il is not None:
        bits = il.interleave(bits)
        stages["interleaver"] = bits.copy()

    scr_post = cartridge.build_scrambler_post()
    if scr_post is not None:
        bits = scr_post.apply(bits)
        stages["scrambler_post"] = bits.copy()

    stages["channel_bits"] = bits.copy()

    # ---- physical layer ------------------------------------------------------
    mapper = cartridge.build_mapper()
    symbol_rate = cartridge.symbol_rate
    sps = int(cfg.sps)
    fs = float(cfg.fs) if cfg.fs else symbol_rate * sps

    if isinstance(mapper, FSK):
        x = mapper.render(bits, sps=sps, symbol_rate=symbol_rate, fs=fs)
        stages["symbols"] = np.zeros(0, np.complex128)
        rrc_delay = 0
    else:
        syms = mapper.map(bits)
        stages["symbols"] = syms.copy()
        rolloff = cartridge.rolloff
        x = pulse_shape(syms, sps, rolloff, offset_q=getattr(mapper, "offset", False))
        rrc_delay = filter_delay(sps)

    stages["clean"] = x.copy()

    # ---- channel -------------------------------------------------------------
    if cfg.watterson:
        x = chan.WattersonChannel.from_condition(cfg.watterson).apply(x, fs, rng)
    if cfg.timing_offset:
        x = chan.apply_timing_offset(x, cfg.timing_offset)
    if cfg.freq_offset_hz or cfg.cfo_hz or cfg.phase0:
        x = chan.apply_cfo(x, cfg.freq_offset_hz + cfg.cfo_hz, fs, cfg.phase0)
    if cfg.phase_noise_dbc is not None:
        x = chan.add_phase_noise(x, cfg.phase_noise_dbc, fs, rng)
    if cfg.iq_imbalance:
        x = chan.iq_imbalance(x, *cfg.iq_imbalance)
    if cfg.dc_offset:
        x = chan.dc_offset(x, cfg.dc_offset)
    x = chan.awgn(x, cfg.snr_db, rng)

    truth = {
        "cartridge_id": cartridge.id,
        "cartridge_digest": cartridge.digest(),
        "modulation": mapper.describe(),
        "modulation_order": mapper.order,
        "bits_per_symbol": mapper.bits_per_symbol,
        "symbol_rate_bd": symbol_rate,
        "fs": fs,
        "sps": sps,
        "rolloff": cartridge.rolloff,
        "snr_db": cfg.snr_db,
        "cfo_hz": cfg.cfo_hz,
        "freq_offset_hz": cfg.freq_offset_hz,
        "timing_offset": cfg.timing_offset,
        "watterson": cfg.watterson,
        "rrc_delay": rrc_delay,
        "seed": cfg.seed,
        "payload_bits": int(len(stages["payload"])),
        "channel_bits": int(len(stages["channel_bits"])),
        "fec": inner.describe() if inner is not None else "none",
        "fec_outer": outer.describe() if outer is not None else "none",
        "interleaver": il.describe() if il is not None else "none",
        "interleaver_outer": il_outer.describe() if il_outer is not None else "none",
        "scrambler": scr.describe() if scr is not None else "none",
        "scrambler_post": scr_post.describe() if scr_post is not None else "none",
        "sync_word_len": int(len(marker)) if marker is not None else 0,
        "sync_period_bits": cartridge.sync_period or 0,
    }

    result = SynthResult(samples=x, fs=fs, sps=sps, truth=truth, stages=stages)

    # ---- the .wav view of the same parameter vector ---------------------------
    if cfg.render_wav or cartridge.ssb:
        audio_fs = 48000.0 if fs > 48000.0 else fs
        centre = cartridge.centre_hz or 1800.0
        src = x
        if audio_fs != fs:
            src = chan.resample_rate(x, audio_fs / fs)
        result.audio = to_ssb_audio(src, audio_fs, centre, cartridge.ssb or "usb")
        result.audio_fs = audio_fs
        truth["ssb"] = cartridge.ssb or "usb"
        truth["centre_hz"] = centre

    return result
