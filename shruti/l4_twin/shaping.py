"""Pulse shaping and matched filtering.

Root-raised-cosine is the near-universal choice in the traffic this PS targets,
and its roll-off is one of the parameters SHRUTI recovers.  Worth noting for the
evaluation section: **roll-off is one of the quantities the standard public
benchmark barely varies**, which is part of why a generative approach is right
here - the twin varies it because it is a parameter, not a fixed setting.

Roll-off also sits in a known degeneracy with symbol rate and SNR, which is why
L4 reports the full covariance rather than independent error bars, and why the
identifiability ledger names the degenerate direction explicitly.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sps_signal

__all__ = ["rrc_taps", "rc_taps", "gaussian_taps", "upsample", "pulse_shape", "matched_filter"]


def rrc_taps(sps: int, rolloff: float, span: int = 10) -> np.ndarray:
    """Root-raised-cosine impulse response, unit energy.

    `span` is the one-sided length in symbols; the filter is ``2*span*sps+1``
    taps.  Ten symbols is the usual compromise - short enough to be cheap, long
    enough that truncation does not distort the spectrum measurably.
    """
    beta = float(np.clip(rolloff, 1e-6, 1.0))
    n = np.arange(-span * sps, span * sps + 1, dtype=np.float64)
    t = n / sps                                   # time in symbol periods
    h = np.zeros_like(t)

    # t = 0
    z = np.isclose(t, 0.0)
    h[z] = 1.0 + beta * (4.0 / np.pi - 1.0)

    # t = +/- 1/(4*beta), where the closed form is 0/0
    if beta > 0:
        tc = 1.0 / (4.0 * beta)
        s = np.isclose(np.abs(t), tc)
        if s.any():
            h[s] = (beta / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta))
            )
    else:
        s = np.zeros_like(z)

    g = ~(z | s)
    tg = t[g]
    num = np.sin(np.pi * tg * (1 - beta)) + 4 * beta * tg * np.cos(np.pi * tg * (1 + beta))
    den = np.pi * tg * (1 - (4 * beta * tg) ** 2)
    h[g] = num / den

    return h / np.sqrt(np.sum(h ** 2))


def rc_taps(sps: int, rolloff: float, span: int = 10) -> np.ndarray:
    """Raised-cosine (the full Nyquist pulse, not its root)."""
    beta = float(np.clip(rolloff, 1e-6, 1.0))
    n = np.arange(-span * sps, span * sps + 1, dtype=np.float64)
    t = n / sps
    with np.errstate(divide="ignore", invalid="ignore"):
        sinc = np.sinc(t)
        cosf = np.cos(np.pi * beta * t) / (1 - (2 * beta * t) ** 2)
    cosf[np.isclose(np.abs(2 * beta * t), 1.0)] = np.pi / 4
    h = sinc * cosf
    return h / np.sqrt(np.sum(h ** 2))


def gaussian_taps(sps: int, bt: float = 0.3, span: int = 4) -> np.ndarray:
    """Gaussian pulse, for GFSK/GMSK-style waveforms."""
    n = np.arange(-span * sps, span * sps + 1, dtype=np.float64) / sps
    alpha = np.sqrt(np.log(2) / 2) / bt
    h = np.exp(-(np.pi ** 2) * (n ** 2) / (alpha ** 2))
    return h / np.sum(h)


def upsample(symbols: np.ndarray, sps: int) -> np.ndarray:
    """Zero-stuff to `sps` samples per symbol."""
    symbols = np.asarray(symbols, dtype=np.complex128).reshape(-1)
    out = np.zeros(len(symbols) * sps, dtype=np.complex128)
    out[::sps] = symbols
    return out


def pulse_shape(
    symbols: np.ndarray,
    sps: int,
    rolloff: float = 0.35,
    span: int = 10,
    offset_q: bool = False,
) -> np.ndarray:
    """Upsample and RRC-filter.

    ``offset_q`` implements OQPSK by delaying the quadrature arm half a symbol,
    which removes the 180-degree constellation transitions that make plain QPSK
    hard on a nonlinear amplifier.
    """
    h = rrc_taps(sps, rolloff, span)
    if not offset_q:
        return sps_signal.lfilter(h, 1.0, upsample(symbols, sps))

    half = sps // 2
    i_up = upsample(np.real(symbols).astype(np.complex128), sps)
    q_up = upsample(np.imag(symbols).astype(np.complex128), sps)
    q_up = np.concatenate([np.zeros(half, np.complex128), q_up])[: len(i_up)]
    return sps_signal.lfilter(h, 1.0, i_up) + 1j * sps_signal.lfilter(h, 1.0, q_up)


def matched_filter(x: np.ndarray, sps: int, rolloff: float = 0.35, span: int = 10) -> np.ndarray:
    """Apply the receive-side RRC.  Cascaded with the transmit RRC this is a
    raised cosine, which is Nyquist - zero ISI at the correct sampling instants."""
    h = rrc_taps(sps, rolloff, span)
    return sps_signal.lfilter(h, 1.0, np.asarray(x, dtype=np.complex128))


def filter_delay(sps: int, span: int = 10) -> int:
    """Group delay of one RRC, in samples.  Two of them cascade to ``2*span*sps``."""
    return span * sps
