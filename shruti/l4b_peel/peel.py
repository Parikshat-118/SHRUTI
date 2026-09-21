"""Subtract-and-rescan."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sps_signal

from ..core.stats import whiteness_test
from ..l2_detect import Detection, detect_emitters

__all__ = ["PeelStage", "PeelResult", "peel", "extract_band"]


@dataclass
class PeelStage:
    """One emitter removed, and what the residual looked like afterwards."""

    index: int
    detection: Detection
    residual_power_db: float
    removed_power_db: float
    whiteness_p: float

    def describe(self) -> str:
        return (
            f"stage {self.index}: removed {self.detection.describe()} "
            f"-> residual {self.residual_power_db:+6.1f} dB, "
            f"whiteness p={self.whiteness_p:.3f}"
        )


@dataclass
class PeelResult:
    stages: list[PeelStage] = field(default_factory=list)
    residual: np.ndarray | None = None
    newly_revealed: list[Detection] = field(default_factory=list)
    stopped_because: str = ""

    @property
    def n_emitters(self) -> int:
        return len(self.stages)

    def summary(self) -> str:
        lines = [f"peeled {self.n_emitters} emitter(s); stopped: {self.stopped_because}"]
        lines += [f"  {s.describe()}" for s in self.stages]
        if self.newly_revealed:
            lines.append(
                f"  {len(self.newly_revealed)} emitter(s) became visible only after "
                f"peeling - invisible in the original spectrogram:"
            )
            lines += [f"    {d.describe()}" for d in self.newly_revealed]
        return "\n".join(lines)


def extract_band(x: np.ndarray, fs: float, centre_hz: float, bandwidth_hz: float,
                 taps: int = 129) -> np.ndarray:
    """Isolate one emitter's band, as the reconstruction to subtract.

    A band-limited extraction rather than a full parametric resynthesis: it needs
    no successful fit, so peeling still works on emitters SHRUTI cannot yet
    identify.  Once a cartridge *does* fit, the twin's own render can be
    subtracted instead, which cancels far more deeply.
    """
    x = np.asarray(x, dtype=np.complex128)
    n = np.arange(len(x))
    shifted = x * np.exp(-2j * np.pi * centre_hz * n / fs)

    cutoff = max(bandwidth_hz / 2.0, fs / len(x) * 4)
    wn = float(np.clip(cutoff / (fs / 2), 1e-4, 0.99))
    h = sps_signal.firwin(taps, wn)
    lp = sps_signal.filtfilt(h, 1.0, shifted)

    return lp * np.exp(2j * np.pi * centre_hz * n / fs)


def peel(
    x: np.ndarray,
    fs: float,
    max_stages: int = 6,
    whiteness_threshold: float = 0.01,
    min_snr_db: float = 6.0,
) -> PeelResult:
    """Remove emitters strongest-first until the residual looks like noise.

    Stops on the **whiteness test**, not on a fixed count: the honest termination
    condition is "nothing structured is left", and that is measurable.
    """
    res = PeelResult()
    work = np.asarray(x, dtype=np.complex128).copy()
    p0 = float(np.mean(np.abs(work) ** 2)) or 1e-20

    initial = detect_emitters(work, fs)
    initial_centres = [d.centre_hz for d in initial]

    for i in range(max_stages):
        dets = detect_emitters(work, fs)
        strong = [d for d in dets if d.snr_db >= min_snr_db]
        if not strong:
            res.stopped_because = "no emitter above the SNR floor remains"
            break

        d = strong[0]
        recon = extract_band(work, fs, d.centre_hz, d.bandwidth_hz)
        removed = float(np.mean(np.abs(recon) ** 2))
        work = work - recon

        pr = float(np.mean(np.abs(work) ** 2))
        _, wp = whiteness_test(work[: min(len(work), 20000)])
        res.stages.append(PeelStage(
            index=i + 1,
            detection=d,
            residual_power_db=float(10 * np.log10(max(pr / p0, 1e-20))),
            removed_power_db=float(10 * np.log10(max(removed / p0, 1e-20))),
            whiteness_p=float(wp),
        ))

        if wp > whiteness_threshold:
            res.stopped_because = (
                f"residual is consistent with noise (whiteness p={wp:.3f}) - "
                "nothing structured is left to find"
            )
            break
    else:
        res.stopped_because = f"reached the stage limit ({max_stages})"

    res.residual = work

    # Anything detectable now that was not detectable before was buried.
    final = detect_emitters(work, fs)
    for d in final:
        if d.snr_db < min_snr_db:
            continue
        if not any(abs(d.centre_hz - c) < max(d.bandwidth_hz, fs / 1000) for c in initial_centres):
            res.newly_revealed.append(d)

    return res
