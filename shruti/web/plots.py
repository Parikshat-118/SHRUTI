"""Plot data extraction, with the sample mapping that makes brushing possible.

Every view returns not just values but **where those values came from in the
original sample stream**.  That is the whole mechanism behind provenance
brushing (PS: *"improve feature visibility of signals with the help of GUI"*):

    Click a decoded byte and the exact symbols that carried it light up in the
    constellation, the exact samples light up in the waterfall, and the exact
    microseconds highlight on the time axis.  Drag a box on the spectrogram and
    see which bits came from it.

No commercial decoder offers this, and it is only possible because the whole
chain was modelled end to end - so provenance is available end to end.
"""

from __future__ import annotations

import numpy as np

__all__ = ["spectrum", "waterfall", "constellation", "time_series", "provenance_map"]


def spectrum(x: np.ndarray, fs: float, nfft: int = 4096) -> dict:
    """Averaged power spectrum in dB, with the frequency axis in Hz."""
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 16:
        return {"freq_hz": [], "power_db": [], "nfft": 0}

    nfft = int(min(nfft, 1 << int(np.floor(np.log2(max(len(x), 16))))))
    nseg = max(1, len(x) // nfft)
    win = np.hanning(nfft)
    acc = np.zeros(nfft)
    for i in range(min(nseg, 64)):
        seg = x[i * nfft : (i + 1) * nfft]
        if len(seg) < nfft:
            break
        acc += np.abs(np.fft.fftshift(np.fft.fft(seg * win))) ** 2
    acc /= max(1, min(nseg, 64))
    power_db = 10 * np.log10(np.maximum(acc, 1e-20))
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs))
    return {
        "freq_hz": freqs.round(3).tolist(),
        "power_db": power_db.round(2).tolist(),
        "nfft": nfft,
    }


def waterfall(
    x: np.ndarray, fs: float, nfft: int = 512, max_rows: int = 360
) -> dict:
    """Time-frequency surface.

    Returns the magnitude grid plus the sample index each row began at, so a
    brush on the waterfall maps back to an exact sample range.
    """
    x = np.asarray(x, dtype=np.complex128)
    nfft = int(min(nfft, max(16, 1 << int(np.floor(np.log2(max(len(x), 16)))))))
    hop = max(nfft // 2, 1)
    nrows = max(1, (len(x) - nfft) // hop + 1)
    step = max(1, nrows // max_rows)
    rows, starts = [], []
    win = np.hanning(nfft)

    for r in range(0, nrows, step):
        i = r * hop
        seg = x[i : i + nfft]
        if len(seg) < nfft:
            break
        s = np.abs(np.fft.fftshift(np.fft.fft(seg * win)))
        rows.append((20 * np.log10(np.maximum(s, 1e-12))).round(1).tolist())
        starts.append(int(i))

    freqs = np.fft.fftshift(np.fft.fftfreq(nfft, d=1.0 / fs))
    flat = np.array(rows) if rows else np.zeros((0, nfft))
    return {
        "rows": rows,
        "sample_start": starts,
        "freq_hz": freqs.round(3).tolist(),
        "nfft": nfft,
        "hop": hop,
        "vmin": float(np.percentile(flat, 5)) if flat.size else -120.0,
        "vmax": float(np.percentile(flat, 99.5)) if flat.size else 0.0,
        "duration_s": len(x) / fs if fs else 0.0,
    }


def constellation(symbols: np.ndarray, max_points: int = 6000) -> dict:
    """Constellation scatter.

    `index` carries the symbol number of every plotted point, so selecting a
    cluster selects real symbols rather than pixels.
    """
    s = np.asarray(symbols, dtype=np.complex128)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return {"i": [], "q": [], "index": [], "n_total": 0}
    step = max(1, len(s) // max_points)
    idx = np.arange(0, len(s), step)
    sel = s[idx]
    return {
        "i": np.real(sel).round(4).tolist(),
        "q": np.imag(sel).round(4).tolist(),
        "index": idx.tolist(),
        "n_total": int(len(s)),
        "decimation": int(step),
    }


def time_series(x: np.ndarray, fs: float, max_points: int = 3000) -> dict:
    """Envelope over time, for the triage view."""
    x = np.asarray(x)
    if len(x) == 0:
        return {"t_s": [], "magnitude_db": []}
    step = max(1, len(x) // max_points)
    n = (len(x) // step) * step
    mag = np.abs(x[:n]).reshape(-1, step).max(axis=1)
    t = np.arange(len(mag)) * step / fs if fs else np.arange(len(mag))
    return {
        "t_s": t.round(6).tolist(),
        "magnitude_db": (20 * np.log10(np.maximum(mag, 1e-12))).round(2).tolist(),
        "decimation": int(step),
    }


def provenance_map(
    n_bits: int, bits_per_symbol: int, sps: int, rrc_delay: int = 0
) -> dict:
    """The linear map from bit index to symbol index to sample range.

    Deliberately simple and explicit rather than implicit: the GUI needs to be
    able to answer "which samples produced this byte" in both directions without
    re-running anything.
    """
    return {
        "bits_per_symbol": int(max(1, bits_per_symbol)),
        "samples_per_symbol": int(max(1, sps)),
        "sample_offset": int(rrc_delay),
        "n_bits": int(n_bits),
        "n_symbols": int(n_bits // max(1, bits_per_symbol)),
    }
