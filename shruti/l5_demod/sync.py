"""Blind synchronisation: symbol rate, timing and carrier offset.

All three estimators here are **non-data-aided** - they work with no training
sequence, because a non-cooperative capture never has one.  Their accuracy is
the physical-layer floor that the decode-feedback loop later improves on, and
quantifying that improvement is the empirical proof of SHRUTI's central claim.

Typical open-loop accuracy: symbol rate to ~1e-4 relative, CFO to a few percent
of the symbol rate.  Staying symbol-aligned across a 1e5-symbol codeword needs
~1e-6, which is an order of magnitude better - and that is what the code
certifies when it decodes.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "estimate_cfo_mth_power",
    "estimate_symbol_rate",
    "oerder_meyr_timing",
    "timing_recover",
    "estimate_snr_m2m4",
]


def estimate_cfo_mth_power(
    x: np.ndarray, fs: float, order: int = 4, search_hz: float | None = None
) -> tuple[float, float]:
    """Carrier frequency offset by the M-th power method.

    Raising an M-PSK signal to the M-th power strips the modulation and leaves a
    tone at ``M * CFO``.  Returns ``(cfo_hz, sharpness)`` where sharpness is the
    peak-to-mean ratio of the spectrum - a usable confidence signal, and the
    thing that collapses when `order` does not match the constellation.

    **The estimate is inherently ambiguous modulo ``fs/M``**, because the M-th
    power discards exactly that much information.  SHRUTI does not paper over
    this: the residual ambiguity is one of the small-cardinality hypotheses the
    decoder resolves.
    """
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 64:
        return 0.0, 0.0

    # Do NOT remove the mean here.  Raising to the M-th power concentrates the
    # modulation-stripped carrier into a tone at M*CFO, and when the offset is
    # near zero that tone IS the DC component.  Subtracting the mean deletes the
    # signal and the estimator locks onto a noise peak - a failure that only
    # appears on well-tuned captures, and therefore never during testing with
    # artificially large offsets.
    y = x ** order
    nfft = int(2 ** np.ceil(np.log2(len(y))))
    spec = np.abs(np.fft.fftshift(np.fft.fft(y, nfft)))
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs))

    if search_hz is not None:
        band = np.abs(freqs) <= search_hz * order
        if band.any():
            spec = np.where(band, spec, 0.0)

    k = int(np.argmax(spec))
    peak = spec[k]
    mean = np.mean(spec[spec > 0]) if np.any(spec > 0) else 1.0
    sharpness = float(peak / mean) if mean > 0 else 0.0

    # Parabolic interpolation around the peak for sub-bin resolution.
    if 0 < k < len(spec) - 1:
        a, b, c = spec[k - 1], spec[k], spec[k + 1]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-30 else 0.0
    else:
        delta = 0.0
    bin_hz = freqs[1] - freqs[0]
    return float((freqs[k] + delta * bin_hz) / order), sharpness


def estimate_symbol_rate(
    x: np.ndarray, fs: float, rate_range: tuple[float, float] | None = None
) -> tuple[float, float]:
    """Symbol rate from the cyclostationary line in the squared envelope.

    A linearly modulated signal has a spectral line at the symbol rate in
    ``|x|^2``.  Returns ``(rate_hz, sharpness)``.

    This is the estimator whose precision the closure loop improves on - it is
    good to roughly 1e-4 relative on a short burst, and hits a self-noise floor
    set by the unknown payload at high SNR.
    """
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 256:
        return 0.0, 0.0

    env = np.abs(x) ** 2
    env = env - np.mean(env)
    nfft = int(2 ** np.ceil(np.log2(len(env))))
    spec = np.abs(np.fft.rfft(env, nfft))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)

    lo, hi = rate_range if rate_range else (fs / 5000.0, fs / 2.0)
    band = (freqs >= lo) & (freqs <= hi)
    if not band.any():
        return 0.0, 0.0

    idx = np.flatnonzero(band)
    sub = spec[idx]
    j = int(np.argmax(sub))
    k = idx[j]
    mean = float(np.mean(sub)) or 1.0
    sharpness = float(sub[j] / mean)

    if 0 < k < len(spec) - 1:
        a, b, c = spec[k - 1], spec[k], spec[k + 1]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-30 else 0.0
    else:
        delta = 0.0
    bin_hz = freqs[1] - freqs[0]
    return float(freqs[k] + delta * bin_hz), sharpness


def estimate_symbol_rate_fm(
    x: np.ndarray, fs: float, rate_range: tuple[float, float] | None = None
) -> tuple[float, float]:
    """Symbol rate of a **constant-modulus** signal, via the frequency discriminator.

    :func:`estimate_symbol_rate` looks for a cyclostationary line in ``|x|^2``,
    which works for linear modulations because their envelope varies with the
    data.  **FSK, MSK and CPM have a constant envelope, so ``|x|^2`` carries no
    symbol-rate line at all** and that estimator returns whatever the noise
    favours.

    The information is in the *frequency*, not the amplitude.  Differentiating
    the instantaneous phase gives a piecewise-constant frequency that steps at
    every symbol boundary, and the magnitude of *its* derivative is a train of
    impulses at exactly the symbol rate.
    """
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 512:
        return 0.0, 0.0

    inst_f = np.diff(np.unwrap(np.angle(x)))
    trans = np.abs(np.diff(inst_f))
    trans = trans - np.mean(trans)
    if not np.any(trans):
        return 0.0, 0.0

    nfft = int(2 ** np.ceil(np.log2(len(trans))))
    spec = np.abs(np.fft.rfft(trans, nfft))
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)

    lo, hi = rate_range if rate_range else (fs / 5000.0, fs / 2.5)
    band = (freqs >= lo) & (freqs <= hi)
    if not band.any():
        return 0.0, 0.0

    idx = np.flatnonzero(band)
    sub = spec[idx]
    j = int(np.argmax(sub))
    k = idx[j]
    mean = float(np.mean(sub)) or 1.0
    sharpness = float(sub[j] / mean)

    # Reduce to the FUNDAMENTAL.  A train of symbol-boundary impulses has lines
    # at every multiple of the symbol rate, and with random data a harmonic is
    # often the strongest of them - so the raw peak can be 2x or 3x the true
    # rate.  Walk down to the smallest submultiple that still shows most of the
    # energy, exactly as the frame-period detector does for the same reason.
    bin_hz = freqs[1] - freqs[0]
    base = float(spec[k])
    changed = True
    while changed:
        changed = False
        for div in (2, 3, 5):
            cand = k // div
            if cand > 0 and freqs[cand] >= lo and float(spec[cand]) > 0.4 * base:
                k = cand
                changed = True
                break

    if 0 < k < len(spec) - 1:
        a, b, c = spec[k - 1], spec[k], spec[k + 1]
        denom = a - 2 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-30 else 0.0
    else:
        delta = 0.0
    return float(freqs[k] + delta * bin_hz), sharpness


def is_constant_modulus(x: np.ndarray, tol: float = 0.12) -> bool:
    """Does the envelope barely vary?  If so, the FM estimator is the right one."""
    a = np.abs(np.asarray(x))
    m = float(np.mean(a))
    if m <= 0:
        return False
    return bool(float(np.std(a)) / m < tol)


def oerder_meyr_timing(x: np.ndarray, sps: int) -> float:
    """Blind symbol-timing offset by the Oerder-Meyr square-law estimator.

    The DFT coefficient of ``|x|^2`` at the symbol rate carries the timing phase
    directly.  Returns the offset in samples, in ``[0, sps)``.  Non-data-aided,
    needs no feedback loop, and works on any linear modulation.
    """
    x = np.asarray(x, dtype=np.complex128)
    n = (len(x) // sps) * sps
    if n < sps * 4:
        return 0.0
    e = np.abs(x[:n]) ** 2
    k = np.arange(n)
    c = np.sum(e * np.exp(-2j * np.pi * k / sps))
    tau = -np.angle(c) / (2 * np.pi) * sps
    return float(tau % sps)


def timing_recover(
    x: np.ndarray, sps: int, offset: float | None = None, symbol_offset: int = 0
) -> tuple[np.ndarray, float]:
    """Resample to one sample per symbol at the optimum instant.

    Uses Oerder-Meyr for the estimate and band-limited interpolation to land on
    a fractional offset.  Returns ``(symbols, offset_used)``.

    **The estimate is wrapped to ``(-sps/2, +sps/2]``.**  Oerder-Meyr returns a
    phase in ``[0, sps)``, so a true offset of -0.1 samples comes back as
    ``sps-0.1`` - and sampling there lands on the *next* symbol, silently
    dropping the first one.  The constellation still looks perfect, so this
    shows up only as bits that will not align with anything.

    `symbol_offset` shifts the whole grid by whole symbols.  That residual
    one-symbol ambiguity is real and is not resolvable from timing alone, so it
    joins the other small-cardinality hypotheses the decoder settles.
    """
    x = np.asarray(x, dtype=np.complex128)
    tau = oerder_meyr_timing(x, sps) if offset is None else float(offset)
    if tau > sps / 2.0:
        tau -= sps

    start = max(0, symbol_offset) * sps
    idx = np.arange(start, len(x) - sps, sps) + tau
    # Clamp, do not drop: a slightly negative first index means the first symbol
    # sits just before sample 0.  Discarding it re-creates exactly the
    # off-by-one-symbol error the wrap above exists to prevent.
    idx = np.maximum(idx, 0.0)

    lo = np.floor(idx).astype(int)
    frac = idx - lo
    lo = np.clip(lo, 0, len(x) - 2)
    syms = x[lo] * (1 - frac) + x[lo + 1] * frac
    return syms.astype(np.complex128), tau


def estimate_snr_m2m4(x: np.ndarray, kurtosis: float = 1.0) -> float:
    """Blind SNR from second and fourth moments (M2M4).

    `kurtosis` is the constellation's, 1.0 for constant-modulus (PSK/FSK).
    Returns SNR in dB.  Needed because the goodness-of-fit statistic must
    normalise the residual by a noise variance the fit itself estimated.
    """
    x = np.asarray(x, dtype=np.complex128)
    m2 = float(np.mean(np.abs(x) ** 2))
    m4 = float(np.mean(np.abs(x) ** 4))
    disc = 2 * m2 ** 2 - m4
    if disc <= 0 or m2 <= 0:
        return -np.inf
    s = np.sqrt(disc)
    n = m2 - s
    if n <= 0:
        return 40.0
    return float(10 * np.log10(s / n))
