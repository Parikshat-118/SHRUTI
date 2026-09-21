"""Frame period and sync-word recovery from a raw bitstream."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.bits import bit_autocorrelation, bits_to_bytes

__all__ = ["FrameAnalysis", "detect_frame_period", "find_sync_word", "analyse_frames"]


@dataclass
class FrameAnalysis:
    """Recovered framing structure."""

    period_bits: int = 0
    confidence: float = 0.0
    sync_word: np.ndarray | None = None
    sync_offset: int = 0
    n_frames: int = 0
    peak_lags: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.period_bits > 0 and self.confidence > 0.15

    def sync_hex(self) -> str:
        if self.sync_word is None:
            return ""
        return bits_to_bytes(self.sync_word).hex().upper()

    def summary(self) -> str:
        if not self.found:
            return "no periodic framing detected"
        s = f"frame period {self.period_bits} bits, {self.n_frames} frames"
        if self.sync_word is not None:
            s += f", sync 0x{self.sync_hex()} ({len(self.sync_word)} bits) at offset {self.sync_offset}"
        return s


def detect_frame_period(
    bits: np.ndarray, min_period: int = 16, max_period: int | None = None
) -> FrameAnalysis:
    """Find the frame period from the comb of autocorrelation peaks.

    A periodic sync word repeats at the frame period, so the bitstream correlates
    with itself at that lag *and at every multiple of it*.  Insisting on the comb
    rather than a single peak is what rejects accidental correlations - a real
    frame structure produces harmonics, a coincidence does not.
    """
    b = np.asarray(bits, dtype=np.uint8).reshape(-1)
    res = FrameAnalysis()
    n = len(b)
    if n < 4 * min_period:
        res.notes.append(f"stream too short ({n} bits) for framing analysis")
        return res

    max_period = max_period or min(n // 4, 20000)
    if max_period <= min_period:
        res.notes.append("no usable lag range")
        return res

    ac = bit_autocorrelation(b, max_lag=max_period, min_lag=min_period)
    if ac.size == 0 or not np.isfinite(ac).any():
        return res

    lags = np.arange(min_period, min_period + len(ac))
    sigma = float(np.std(ac)) or 1e-9
    order = np.argsort(ac)[::-1]

    best_lag, best_score, best_peaks = 0, 0.0, []
    for cand_idx in order[:40]:
        lag = int(lags[cand_idx])
        if lag <= 0:
            continue
        # Score the harmonic comb: a true period repeats at 2x, 3x, ...
        harmonics, vals = [], []
        for k in range(1, 6):
            h = lag * k
            j = h - min_period
            if 0 <= j < len(ac):
                harmonics.append(h)
                vals.append(float(ac[j]))
        if len(vals) < 2:
            continue
        score = float(np.mean(vals)) / sigma * np.sqrt(len(vals))
        if score > best_score:
            best_lag, best_score, best_peaks = lag, score, harmonics

    if best_lag == 0:
        res.notes.append("no periodic structure found in the autocorrelation")
        return res

    # Reduce to the FUNDAMENTAL period.  A frame of length P correlates just as
    # strongly at 2P, 3P, ... so the comb score alone cannot distinguish the
    # fundamental from its harmonics - and reporting 2P silently halves the
    # number of frames and mangles every field boundary downstream.  Walk down
    # to the smallest divisor that still shows most of the correlation.
    def ac_at(lag: int) -> float:
        j = lag - min_period
        return float(ac[j]) if 0 <= j < len(ac) else -1.0

    base = ac_at(best_lag)
    changed = True
    while changed:
        changed = False
        for div in (2, 3, 5, 7):
            cand = best_lag // div
            if cand >= min_period and best_lag % div == 0 and ac_at(cand) > 0.7 * base:
                best_lag = cand
                changed = True
                res.notes.append(f"reduced to fundamental period {cand} (was a x{div} harmonic)")
                break

    res.period_bits = best_lag
    res.confidence = float(np.clip(best_score / 12.0, 0.0, 1.0))
    res.peak_lags = best_peaks
    res.n_frames = n // best_lag
    res.notes.append(
        f"autocorrelation comb at lags {best_peaks} (score {best_score:.1f} sigma)"
    )
    return res


def find_sync_word(
    bits: np.ndarray, period: int, max_len: int = 64, min_len: int = 8
) -> tuple[np.ndarray | None, int, float]:
    """Find the constant bit pattern repeating at `period`.

    Folds the stream at the frame period and looks for the longest run of
    columns that barely vary.  Those columns *are* the sync word - no template
    and no prior knowledge of the standard required.
    """
    b = np.asarray(bits, dtype=np.uint8).reshape(-1)
    nframes = len(b) // period
    if nframes < 3 or period < min_len:
        return None, 0, 0.0

    m = b[: nframes * period].reshape(nframes, period)
    p = m.mean(axis=0)
    constancy = np.abs(p - 0.5) * 2.0            # 1.0 = perfectly constant column

    best_start, best_len, best_score = 0, 0, 0.0
    run_start, run_len = 0, 0
    for i in range(period):
        if constancy[i] > 0.8:
            if run_len == 0:
                run_start = i
            run_len += 1
            if run_len >= min_len:
                score = float(np.mean(constancy[run_start : run_start + run_len]))
                if run_len > best_len or (run_len == best_len and score > best_score):
                    best_start, best_len, best_score = run_start, min(run_len, max_len), score
        else:
            run_len = 0

    if best_len < min_len:
        return None, 0, 0.0

    word = (p[best_start : best_start + best_len] > 0.5).astype(np.uint8)
    return word, best_start, best_score


def analyse_frames(bits: np.ndarray, known_period: int | None = None) -> FrameAnalysis:
    """Full framing analysis: period, then sync word within it."""
    if known_period:
        res = FrameAnalysis(period_bits=int(known_period), confidence=1.0)
        res.n_frames = len(bits) // int(known_period)
        res.notes.append(f"frame period {known_period} supplied by cartridge")
    else:
        res = detect_frame_period(bits)

    if res.period_bits:
        word, off, score = find_sync_word(bits, res.period_bits)
        if word is not None:
            res.sync_word = word
            res.sync_offset = off
            res.notes.append(
                f"constant field of {len(word)} bits at offset {off} "
                f"(constancy {score:.2f}) - this is the sync marker"
            )
    return res
