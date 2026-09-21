"""Wideband emitter detection by OS-CFAR over the averaged spectrum."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.stats import os_cfar

__all__ = ["Detection", "detect_emitters", "occupancy"]


@dataclass
class Detection:
    """One emitter found in the capture."""

    centre_hz: float
    bandwidth_hz: float
    peak_db: float
    snr_db: float
    bin_start: int
    bin_end: int

    @property
    def low_hz(self) -> float:
        return self.centre_hz - self.bandwidth_hz / 2

    @property
    def high_hz(self) -> float:
        return self.centre_hz + self.bandwidth_hz / 2

    def describe(self) -> str:
        return (
            f"{self.centre_hz/1e3:+9.3f} kHz  BW {self.bandwidth_hz/1e3:7.3f} kHz  "
            f"peak {self.peak_db:6.1f} dB  SNR {self.snr_db:5.1f} dB"
        )


def _welch(x: np.ndarray, fs: float, nfft: int = 4096) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=np.complex128)
    nfft = int(min(nfft, 1 << int(np.floor(np.log2(max(len(x), 16))))))
    win = np.hanning(nfft)
    nseg = max(1, min(len(x) // nfft, 128))
    acc = np.zeros(nfft)
    for i in range(nseg):
        seg = x[i * nfft:(i + 1) * nfft]
        if len(seg) < nfft:
            break
        acc += np.abs(np.fft.fftshift(np.fft.fft(seg * win))) ** 2
    acc /= nseg
    return np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs)), acc


def detect_emitters(
    x: np.ndarray,
    fs: float,
    nfft: int = 4096,
    pfa: float = 1e-4,
    min_bins: int = 3,
) -> list[Detection]:
    """Find emitters and measure each one's centre and bandwidth.

    `pfa` is a *false-alarm probability*, not a dB threshold - which is the whole
    point of CFAR: the detector's behaviour is specified statistically and does
    not need retuning when the noise floor moves.
    """
    freqs, power = _welch(x, fs, nfft)
    if len(power) < 64:
        return []

    noise_floor = float(np.quantile(power[power > 0], 0.4)) or 1e-20

    det, _ = os_cfar(power, guard=4, train=24, rank=0.75, pfa=pfa)

    # CFAR estimates the noise from cells NEXT TO the cell under test, which is
    # exactly right in a crowded band and exactly wrong for a single emitter
    # that is wide compared with the training window: the window then sits
    # entirely inside the signal and measures the signal as its own noise floor,
    # so nothing is detected at all.
    #
    # Fall back to a global floor in that case.  The two detectors cover
    # complementary situations rather than competing - a wideband survey needs
    # CFAR, and a file containing one fat emitter needs this.
    occupied = float(det.mean())
    if occupied < 0.005 or occupied > 0.9:
        margin_db = 6.0
        det = power > noise_floor * (10 ** (margin_db / 10))
        if not det.any():
            return []
    bin_hz = float(freqs[1] - freqs[0])

    out: list[Detection] = []
    start = None
    for i, flag in enumerate(det):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start >= min_bins:
                out.append(_make(freqs, power, start, i, bin_hz, noise_floor))
            start = None
    if start is not None and len(det) - start >= min_bins:
        out.append(_make(freqs, power, start, len(det), bin_hz, noise_floor))

    out.sort(key=lambda d: d.peak_db, reverse=True)
    return out


def _make(freqs, power, a: int, b: int, bin_hz: float, floor: float) -> Detection:
    seg = power[a:b]
    # Power-weighted centre, and bandwidth from the span that holds 99% of the
    # segment's energy - more stable than a -3 dB width on a noisy spectrum.
    w = seg / seg.sum()
    centre = float(np.sum(freqs[a:b] * w))
    cum = np.cumsum(w)
    lo = int(np.searchsorted(cum, 0.005))
    hi = int(np.searchsorted(cum, 0.995))
    bw = max(1, hi - lo + 1) * bin_hz
    peak = float(10 * np.log10(max(seg.max(), 1e-20)))
    return Detection(
        centre_hz=centre,
        bandwidth_hz=bw,
        peak_db=peak,
        snr_db=float(10 * np.log10(max(seg.max() / floor, 1e-20))),
        bin_start=a,
        bin_end=b,
    )


def occupancy(x: np.ndarray, fs: float, nfft: int = 4096, pfa: float = 1e-4) -> float:
    """Fraction of the band that is occupied - the headline triage number."""
    dets = detect_emitters(x, fs, nfft, pfa)
    if not dets:
        return 0.0
    return float(min(1.0, sum(d.bandwidth_hz for d in dets) / fs))
