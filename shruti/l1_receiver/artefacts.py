"""Reference-free artefact detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from functools import reduce

import numpy as np

__all__ = [
    "ArtefactFinding",
    "ArtefactReport",
    "analyse_artefacts",
    "conjugate_correlation",
    "correct_iq_imbalance",
    "spacing_gcd",
    "superlinear_scaling",
    "cross_file_consistency",
]


@dataclass
class ArtefactFinding:
    """One thing in the capture that is the receiver, not an emitter."""

    kind: str
    freq_hz: float | None
    confidence: float
    evidence: str

    def describe(self) -> str:
        where = f" at {self.freq_hz:+.1f} Hz" if self.freq_hz is not None else ""
        return f"ARTEFACT - {self.kind}{where} (p={self.confidence:.2f}): {self.evidence}"


@dataclass
class ArtefactReport:
    findings: list[ArtefactFinding] = field(default_factory=list)
    iq_gain_db: float = 0.0
    iq_phase_deg: float = 0.0
    dc_offset: complex = 0j

    @property
    def clean(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        if self.clean:
            return "no receiver artefacts detected"
        return "; ".join(f.kind for f in self.findings)


def _spectrum(x: np.ndarray, fs: float, nfft: int = 8192):
    n = int(min(nfft, 1 << int(np.floor(np.log2(max(len(x), 16))))))
    seg = x[:n] * np.hanning(n)
    p = np.abs(np.fft.fftshift(np.fft.fft(seg))) ** 2
    f = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / fs))
    return f, p


def detect_dc(x: np.ndarray, fs: float) -> ArtefactFinding | None:
    """LO self-mix: energy confined to bin 0 with no measurable bandwidth.

    A real emitter has bandwidth.  A DC spike does not - that is exactly what
    distinguishes it, and it needs no reference capture to see.
    """
    dc = complex(np.mean(x))
    p_dc = abs(dc) ** 2
    p_tot = float(np.mean(np.abs(x - dc) ** 2))
    if p_tot <= 0:
        return None
    ratio = p_dc / p_tot
    if ratio > 0.01:
        return ArtefactFinding(
            "DC offset / LO self-mix", 0.0, float(min(1.0, ratio * 10)),
            f"mean magnitude is {10*np.log10(ratio):.1f} dB relative to the "
            f"rest of the capture, with no measurable bandwidth",
        )
    return None


def conjugate_correlation(x: np.ndarray, fs: float) -> tuple[float, complex]:
    """Correlate the spectrum with its own conjugate mirror about DC.

    An I/Q-imbalance image is the **conjugate** of its twin, so the correlation
    is high - and the same statistic *estimates the imbalance*, which means the
    test that detects the problem also supplies the correction.  Returns
    ``(correlation, complex imbalance coefficient)``.
    """
    x = np.asarray(x, dtype=np.complex128)
    x = x - np.mean(x)
    n = len(x)
    if n < 256:
        return 0.0, 0j
    # E[x^2] is zero for a proper (circular) signal and non-zero when an image
    # is present; normalised, it is the imbalance coefficient directly.
    r_xx = float(np.mean(np.abs(x) ** 2))
    c_xx = complex(np.mean(x * x))
    if r_xx <= 0:
        return 0.0, 0j
    coeff = c_xx / r_xx
    return float(min(1.0, abs(coeff))), coeff


def correct_iq_imbalance(x: np.ndarray) -> np.ndarray:
    """Blindly remove an I/Q image using the same statistic that detected it."""
    x = np.asarray(x, dtype=np.complex128)
    x = x - np.mean(x)
    _, coeff = conjugate_correlation(x, 1.0)
    if abs(coeff) < 1e-6:
        return x
    w = coeff / (1.0 + abs(coeff) ** 2)
    return x - w * np.conj(x)


def spacing_gcd(freqs: list[float], tol_hz: float = 1.0) -> tuple[float, float]:
    """GCD of the spacings between detected tones.

    **A clock comb has one; independent emitters do not.**  Returns
    ``(gcd_hz, fraction of spacings explained)`` - the fraction is the
    confidence, because a coincidental GCD explains only some of the spacings.
    """
    if len(freqs) < 3:
        return 0.0, 0.0
    fs_sorted = sorted(freqs)
    spacings = np.diff(fs_sorted)
    spacings = spacings[spacings > tol_hz]
    if len(spacings) < 2:
        return 0.0, 0.0

    quant = np.round(spacings / tol_hz).astype(np.int64)
    g = reduce(gcd, quant.tolist())
    g_hz = g * tol_hz
    if g_hz <= tol_hz:
        return 0.0, 0.0
    explained = float(np.mean(np.abs(spacings / g_hz - np.round(spacings / g_hz)) < 0.05))
    return g_hz, explained


def superlinear_scaling(
    frames: list[np.ndarray], fs: float, f0: float
) -> tuple[float, str]:
    """Does energy at 2f0 grow faster than linearly with the power at f0?

    A spur that grows faster than linearly with drive level is an intermodulation
    product of the receiver's own front end, not a transmitter.  Returns
    ``(slope, evidence)``; a slope near 1 is linear (a real emitter), near 2 or 3
    is a nonlinearity.
    """
    if len(frames) < 3:
        return 0.0, "need at least three frames to measure scaling"

    p1, p2 = [], []
    for fr in frames:
        f, p = _spectrum(fr, fs)
        i1 = int(np.argmin(np.abs(f - f0)))
        i2 = int(np.argmin(np.abs(f - 2 * f0)))
        p1.append(p[i1])
        p2.append(p[i2])

    a = np.log10(np.maximum(np.array(p1), 1e-20))
    b = np.log10(np.maximum(np.array(p2), 1e-20))
    if np.std(a) < 1e-9:
        return 0.0, "drive level did not vary enough to measure scaling"
    slope = float(np.polyfit(a, b, 1)[0])
    verdict = "linear (consistent with a real emitter)" if slope < 1.4 else (
        f"superlinear (slope {slope:.2f}) - consistent with front-end intermodulation"
    )
    return slope, verdict


def cross_file_consistency(
    per_file_offsets: dict[str, list[float]], tol_hz: float = 50.0
) -> list[tuple[float, int, float]]:
    """Features recurring at the same BASEBAND offset across many files.

    The strongest artefact test available, and it needs no extra hardware:

        A feature at the same baseband offset across many files, *regardless of
        what frequency the receiver was tuned to*, is the receiver.  An emitter
        would have moved with the tuning.

    Gets strictly better the more files exist.  Returns
    ``(offset_hz, file_count, fraction_of_files)``, most persistent first.
    """
    if not per_file_offsets:
        return []
    all_offs = [(f, o) for f, offs in per_file_offsets.items() for o in offs]
    if not all_offs:
        return []

    used = set()
    clusters: list[tuple[float, int, float]] = []
    n_files = len(per_file_offsets)

    for i, (_, o) in enumerate(all_offs):
        if i in used:
            continue
        members = [j for j, (_, p) in enumerate(all_offs)
                   if j not in used and abs(p - o) <= tol_hz]
        used.update(members)
        files = {all_offs[j][0] for j in members}
        if len(files) >= max(2, n_files // 3):
            centre = float(np.mean([all_offs[j][1] for j in members]))
            clusters.append((centre, len(files), len(files) / n_files))

    clusters.sort(key=lambda c: c[1], reverse=True)
    return clusters


def analyse_artefacts(x: np.ndarray, fs: float, tone_freqs: list[float] | None = None) -> ArtefactReport:
    """Run every reference-free test on one capture."""
    rep = ArtefactReport()
    x = np.asarray(x, dtype=np.complex128)
    rep.dc_offset = complex(np.mean(x))

    dc = detect_dc(x, fs)
    if dc:
        rep.findings.append(dc)

    corr, coeff = conjugate_correlation(x, fs)
    if corr > 0.05:
        rep.iq_gain_db = float(20 * np.log10(1 + abs(coeff)))
        rep.iq_phase_deg = float(np.degrees(np.angle(coeff)) / 2)
        rep.findings.append(ArtefactFinding(
            "I/Q imbalance image", None, float(min(1.0, corr * 4)),
            f"spectrum correlates with its own conjugate mirror (r={corr:.3f}); "
            f"estimated imbalance {rep.iq_gain_db:.2f} dB / {rep.iq_phase_deg:.2f} deg "
            f"- correctable blindly",
        ))

    if tone_freqs and len(tone_freqs) >= 3:
        g, explained = spacing_gcd(tone_freqs)
        if g > 0 and explained > 0.8:
            rep.findings.append(ArtefactFinding(
                "spur comb / clock harmonics", g, float(explained),
                f"detected tone spacings share a GCD of {g:.1f} Hz explaining "
                f"{explained*100:.0f}% of them - independent emitters do not do this",
            ))

    return rep
