"""Soft demodulation, and the ambiguity set the decoder resolves.

The output of this module is **log-likelihood ratios**, plus an explicit list of
the hypotheses that the physical layer cannot settle on its own.  That list is
short - a handful of rotations, a conjugation, a bit-order flip - and it is the
bridge to the central idea: each one is tried, and the code decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..l4_twin.modulation import FSK, Modulation
from ..l4_twin.shaping import filter_delay, matched_filter
from .sync import estimate_cfo_mth_power, estimate_snr_m2m4, timing_recover

__all__ = ["DemodResult", "demodulate", "soft_demodulate", "AMBIGUITIES", "ambiguity_set"]


#: The standing ambiguities of blind demodulation.  Every one is small-
#: cardinality, and every one is resolved by which hypothesis lets the code
#: decode - never by a human listening or a threshold.
AMBIGUITIES = (
    "phase_rotation",     # modulo a symmetry of the constellation
    "spectral_inversion", # LSB vs USB; conjugate of the baseband
    "differential",       # differential vs absolute encoding
    "bit_order",          # MSB-first vs LSB-first within a symbol
)


@dataclass
class DemodResult:
    """Soft bits plus everything needed to explain and undo the demodulation."""

    llr: np.ndarray
    symbols: np.ndarray
    modulation: str
    sps: int
    cfo_hz: float = 0.0
    timing_offset: float = 0.0
    phase_rad: float = 0.0
    snr_db: float = float("nan")
    evm: float = float("nan")
    rotation_index: int = 0
    conjugated: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def n_bits(self) -> int:
        return len(self.llr)

    @property
    def n_symbols(self) -> int:
        return len(self.symbols)

    def summary(self) -> str:
        return (
            f"{self.modulation}: {self.n_symbols} symbols -> {self.n_bits} soft bits, "
            f"CFO {self.cfo_hz:+.1f} Hz, EVM {self.evm:.3f}, SNR {self.snr_db:.1f} dB"
        )


def ambiguity_set(mapper: Modulation) -> list[tuple[int, bool]]:
    """Enumerate ``(rotation_index, conjugate)`` hypotheses for a constellation.

    Small by construction: an M-PSK constellation has M rotational symmetries and
    one conjugation, so the whole set is 2M - which a decoder can sweep in
    milliseconds.  This is why "try both and let the code decide" is a practical
    engineering answer rather than a slogan.
    """
    if isinstance(mapper, FSK):
        return [(0, False), (0, True)]
    m = mapper.order if mapper.kind == "psk" else 4
    return [(r, c) for c in (False, True) for r in range(m)]


def _estimate_phase(syms: np.ndarray, mapper: Modulation) -> float:
    """Residual carrier phase, modulo a constellation symmetry.

    For M-PSK the M-th power mean has the modulation stripped, so its argument
    is M times the phase.  Square QAM uses the 4th power, whose corners dominate.

    **The reference is taken from the constellation itself, not assumed to be
    zero.**  Conventional QPSK sits at +/-45 degrees, so its 4th power is real
    *negative*; assuming a zero reference rotates the recovered constellation by
    45 degrees and the demapper then compares against the wrong points - low EVM
    on the symbols, garbage on the bits, which is a genuinely confusing failure
    to debug from the outside.
    """
    power = mapper.order if mapper.kind == "psk" else 4
    power = max(2, min(power, 8))
    z = syms ** power
    z = z[np.isfinite(z)]
    if len(z) == 0:
        return 0.0
    ref = np.angle(np.mean(mapper.points ** power))
    return float(np.angle(np.mean(z) * np.exp(-1j * ref)) / power)


def demodulate(
    x: np.ndarray,
    mapper: Modulation,
    sps: int,
    fs: float,
    rolloff: float = 0.35,
    cfo_hz: float | None = None,
    timing_offset: float | None = None,
    phase_rad: float | None = None,
    rotation_index: int = 0,
    conjugate: bool = False,
    symbol_offset: int = 0,
    fsk_offset: int | None = None,
    apply_matched_filter: bool = True,
) -> DemodResult:
    """Demodulate to symbols under one ambiguity hypothesis.

    Parameters left as ``None`` are estimated blind.  Passing a known value is
    how the closure loop feeds a refined physical-layer estimate back in.
    """
    x = np.asarray(x, dtype=np.complex128)
    if conjugate:
        x = np.conj(x)

    # --- carrier.  FSK is not an M-PSK signal, so the M-th power method does
    #     not apply to it; its carrier is the centroid of the occupied band.
    if cfo_hz is None:
        if isinstance(mapper, FSK):
            cfo_hz = _fsk_carrier(x, mapper, fs, fs / max(sps, 1))
        else:
            order = mapper.order if mapper.kind == "psk" else 4
            cfo_hz, _ = estimate_cfo_mth_power(x, fs, order=max(2, min(order, 8)))
    n = np.arange(len(x))
    x = x * np.exp(-1j * 2 * np.pi * cfo_hz * n / fs)

    # --- FSK leaves the linear path entirely
    if isinstance(mapper, FSK):
        return _demod_fsk(x, mapper, sps, fs, cfo_hz, symbol_offset, fsk_offset)

    # --- matched filter and timing.
    #     The transmit RRC already contributed `span*sps` of group delay and the
    #     receive RRC adds the same again, so the cascade delay is TWICE
    #     filter_delay().  Skipping only one of them leaves a ten-symbol offset -
    #     the constellation looks perfect and every bit is misaligned.
    if apply_matched_filter:
        y = matched_filter(x, sps, rolloff)
        y = y[2 * filter_delay(sps):]
    else:
        y = x
    syms, tau = timing_recover(y, sps, timing_offset, symbol_offset)

    # --- normalise to unit average power so LLR scaling is meaningful
    p = np.sqrt(np.mean(np.abs(syms) ** 2)) or 1.0
    syms = syms / p

    # --- residual phase, then the rotation hypothesis
    ph = _estimate_phase(syms, mapper) if phase_rad is None else float(phase_rad)
    syms = syms * np.exp(-1j * ph)
    if rotation_index:
        rot = 2 * np.pi * rotation_index / (mapper.order if mapper.kind == "psk" else 4)
        syms = syms * np.exp(1j * rot)

    snr_db = estimate_snr_m2m4(syms)
    noise_var = 10 ** (-snr_db / 10.0) if np.isfinite(snr_db) else 0.1
    noise_var = float(np.clip(noise_var, 1e-4, 10.0))

    llr = mapper.demap_llr(syms, noise_var)

    pts = mapper.points
    nearest = pts[np.argmin(np.abs(syms[:, None] - pts[None, :]), axis=1)]
    evm = float(np.sqrt(np.mean(np.abs(syms - nearest) ** 2)))

    return DemodResult(
        llr=llr,
        symbols=syms,
        modulation=mapper.describe(),
        sps=sps,
        cfo_hz=float(cfo_hz),
        timing_offset=float(tau),
        phase_rad=float(ph),
        snr_db=float(snr_db),
        evm=evm,
        rotation_index=rotation_index,
        conjugated=conjugate,
        meta={"noise_var": noise_var, "symbol_offset": symbol_offset},
    )


def _fsk_carrier(x: np.ndarray, mapper: FSK, fs: float, symbol_rate: float) -> float:
    """Carrier of an FSK signal, by matching its own tone comb to the spectrum.

    A power-weighted centroid is the obvious estimator and it is wrong: over a
    finite record the tones carry unequal energy simply because the data is
    random, which drags the centroid off the true carrier by an arbitrary
    fraction of the tone spacing.

    Instead, use the structure already known from the hypothesis.  An `order`-FSK
    signal puts energy at `order` tones of known spacing, so slide that comb
    across the spectrum and take the offset where it collects the most power.
    This is a matched filter in the frequency domain: unbiased by data balance,
    and it degrades gracefully rather than wandering.
    """
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 256:
        return 0.0

    nfft = int(2 ** np.ceil(np.log2(min(len(x), 1 << 16))))
    p = np.abs(np.fft.fftshift(np.fft.fft(x[:nfft], nfft))) ** 2
    f = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs))
    bin_hz = f[1] - f[0]

    tones = mapper.tone_offsets(symbol_rate)
    span = float(np.max(np.abs(tones))) + symbol_rate
    search = np.arange(-span, span + bin_hz, bin_hz)

    best_f, best_score = 0.0, -np.inf
    for f0 in search:
        idx = np.clip(((f0 + tones) - f[0]) / bin_hz, 0, nfft - 1).astype(int)
        score = float(np.sum(p[idx]))
        if score > best_score:
            best_f, best_score = float(f0), score
    return best_f


def _spectral_centroid(x: np.ndarray, fs: float) -> float:
    """Power-weighted centre of the occupied band.  Kept for wideband triage.

    Not used as an FSK carrier estimator - see :func:`_fsk_carrier` for why.
    """
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 64:
        return 0.0
    nfft = int(2 ** np.ceil(np.log2(min(len(x), 1 << 16))))
    p = np.abs(np.fft.fftshift(np.fft.fft(x[:nfft], nfft))) ** 2
    f = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs))
    thresh = p.max() * 0.05
    keep = p >= thresh
    if not keep.any():
        return 0.0
    return float(np.sum(f[keep] * p[keep]) / np.sum(p[keep]))


def _demod_fsk(
    x: np.ndarray, mapper: FSK, sps: int, fs: float, cfo_hz: float,
    symbol_offset: int = 0, explicit_offset: int | None = None,
) -> DemodResult:
    """Non-coherent FSK via a matched filter bank, one filter per tone.

    `symbol_offset` shifts the symbol grid by whole symbols.  FSK needs this for
    the same reason the linear path does: the intra-symbol phase search below
    fixes alignment *within* a symbol but cannot tell which symbol is first, and
    a one-symbol error shifts every recovered bit.
    """
    symbol_rate = fs / sps
    tones = mapper.tone_offsets(symbol_rate)
    if len(x) < sps * 4:
        return DemodResult(np.zeros(0), np.zeros(0, np.complex128), mapper.describe(), sps)

    t = np.arange(sps) / fs
    bank = np.exp(-2j * np.pi * np.outer(tones, t))          # (order, sps)

    # Symbol timing.  FSK has no constellation for the linear timing estimator to
    # work on, so recover it by direct search: at the correct sampling phase each
    # symbol sits squarely in one tone filter, which MAXIMISES the margin between
    # the winning tone and the runner-up.  Without this, any fractional timing
    # offset smears energy across two filters and the demodulator returns noise -
    # a failure that never appears when testing with perfectly aligned synthetic
    # captures.
    # An explicit offset (>= 0) is used verbatim: the caller is enumerating
    # alignments as hypotheses and the CODE will decide between them, which is
    # far more reliable than any timing heuristic. The search below is only the
    # fallback for a direct, single-shot call.
    if explicit_offset is not None:
        candidates = [int(explicit_offset)]
    else:
        base = max(0, symbol_offset) * sps
        candidates = list(range(base, base + sps))

    best_off, best_margin, best_corr = 0, -np.inf, None
    for off in candidates:
        nsym = (len(x) - off) // sps
        if nsym < 4:
            continue
        blk = x[off : off + nsym * sps].reshape(nsym, sps)
        c = np.abs(blk @ bank.T)
        part = np.partition(c, -2, axis=1)
        margin = float(np.mean(part[:, -1] - part[:, -2]) / (np.mean(part[:, -1]) or 1.0))
        if margin > best_margin:
            best_off, best_margin, best_corr = off, margin, c

    if best_corr is None:
        return DemodResult(np.zeros(0), np.zeros(0, np.complex128), mapper.describe(), sps)
    corr = best_corr                                          # (nsym, order)
    nsym = corr.shape[0]

    # Energies -> per-bit LLRs through the same max-log rule as the linear path.
    e = corr ** 2
    e = e / (np.mean(e) or 1.0)
    b = mapper.bits_per_symbol
    labels = mapper._label_table()
    from ..l4_twin.modulation import gray
    order_map = gray(np.arange(mapper.order))
    e_ordered = np.zeros_like(e)
    e_ordered[:, order_map] = e

    out = np.empty((nsym, b))
    for i in range(b):
        ones = labels[:, i] == 1
        out[:, i] = e_ordered[:, ~ones].max(axis=1) - e_ordered[:, ones].max(axis=1)

    hard = np.argmax(corr, axis=1)
    return DemodResult(
        llr=out.reshape(-1),
        symbols=(hard - (mapper.order - 1) / 2).astype(np.complex128),
        modulation=mapper.describe(),
        sps=sps,
        cfo_hz=float(cfo_hz),
        snr_db=float(estimate_snr_m2m4(x)),
        evm=float("nan"),
        timing_offset=float(best_off),
        meta={"tone_margin": float(best_margin)},
    )


def soft_demodulate(
    x: np.ndarray,
    mapper: Modulation,
    sps: int,
    fs: float,
    rolloff: float = 0.35,
    **kwargs,
) -> list[DemodResult]:
    """Demodulate under *every* ambiguity hypothesis.

    Returns one :class:`DemodResult` per hypothesis, cheapest-first.  L6 tries
    each in turn and keeps whichever one satisfies the code's parity checks -
    which is the mechanism that resolves spectral inversion, phase rotation and
    differential encoding without a human in the loop.
    """
    out = []
    if isinstance(mapper, FSK):
        # FSK has no constellation to lock timing against, so the sampling
        # alignment is enumerated outright and the parity checks settle it - the
        # same mechanism that resolves phase rotation and spectral inversion.
        #
        # **Cap the sweep.**  `sps` is fs/symbol_rate, so a cartridge whose rate
        # is far from the truth produces an enormous one (16 MHz / 1200 Bd is
        # 13,333), and an O(sps) sweep of matrix multiplies then takes minutes -
        # an unbounded loop driven by a *hypothesis* rather than by the data.
        # Sub-sample alignment beyond ~16 positions per symbol buys nothing.
        n_off = min(sps, 16)
        for off in (int(round(i * sps / n_off)) for i in range(n_off)):
            for _, conj in ambiguity_set(mapper):
                out.append(
                    demodulate(x, mapper, sps, fs, rolloff,
                               conjugate=conj, fsk_offset=off, **kwargs)
                )
        return out

    for soff in (0, 1):
        for rot, conj in ambiguity_set(mapper):
            out.append(
                demodulate(
                    x, mapper, sps, fs, rolloff,
                    rotation_index=rot, conjugate=conj, symbol_offset=soff, **kwargs,
                )
            )
    return out
