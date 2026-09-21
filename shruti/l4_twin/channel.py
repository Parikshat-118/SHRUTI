"""Channel and front-end impairments, including a real HF ionospheric channel.

**HF comes first**, and HF is not AWGN.  Without a proper ionospheric
model a faded HF capture produces a large residual and SHRUTI would wrongly
announce UNKNOWN - the honesty mechanism misfiring on the primary band of interest.
So the Watterson tapped-delay-line model of ITU-R F.1487 is here, with delay and
Doppler spread as **recovered parameters** rather than fixed settings.

Once recovered they are intelligence in their own right: a propagation-mode
hypothesis (groundwave vs single-hop vs multi-hop skywave) with uncertainty
attached, out of the same fit that produced the modulation.

This module also contains the *receiver* artefacts - DC offset, IQ imbalance,
LO leakage, front-end nonlinearity - because L1 must be able to recognise them,
and the cheapest way to be sure it can is to generate them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal as sps_signal

__all__ = [
    "awgn",
    "apply_cfo",
    "apply_timing_offset",
    "WattersonChannel",
    "ITU_CONDITIONS",
    "iq_imbalance",
    "dc_offset",
    "nonlinearity",
    "add_phase_noise",
]


#: ITU-R F.1487 reference conditions: (delay spread seconds, Doppler spread Hz).
ITU_CONDITIONS: dict[str, tuple[float, float]] = {
    "good": (0.5e-3, 0.1),
    "moderate": (1.0e-3, 0.5),
    "poor": (2.0e-3, 1.0),
    "flutter": (0.5e-3, 10.0),
    "disturbed": (3.0e-3, 2.0),
}


def awgn(x: np.ndarray, snr_db: float, rng: np.random.Generator | None = None) -> np.ndarray:
    """Add complex AWGN at the given SNR, measured over the whole array."""
    rng = rng or np.random.default_rng()
    x = np.asarray(x, dtype=np.complex128)
    sig_p = float(np.mean(np.abs(x) ** 2))
    if sig_p <= 0:
        return x
    n_p = sig_p / (10 ** (snr_db / 10.0))
    n = np.sqrt(n_p / 2) * (rng.normal(size=x.shape) + 1j * rng.normal(size=x.shape))
    return x + n


def noise_variance_for_snr(x: np.ndarray, snr_db: float) -> float:
    sig_p = float(np.mean(np.abs(np.asarray(x)) ** 2))
    return sig_p / (10 ** (snr_db / 10.0))


def apply_cfo(x: np.ndarray, cfo_hz: float, fs: float, phase0: float = 0.0) -> np.ndarray:
    """Carrier frequency offset, plus an initial phase.

    A residual CFO is the single most common reason a blind demodulator produces
    a rotating constellation and then nonsense bits.  SHRUTI estimates it, and
    the decode outcome certifies the estimate.
    """
    n = np.arange(len(x))
    return np.asarray(x, np.complex128) * np.exp(1j * (2 * np.pi * cfo_hz * n / fs + phase0))


def apply_timing_offset(x: np.ndarray, frac: float) -> np.ndarray:
    """Fractional-sample delay via band-limited (sinc) interpolation.

    `frac` is in samples and may be non-integer; this is how the twin models a
    receiver whose sampling instants do not align with the transmitter's.
    """
    x = np.asarray(x, dtype=np.complex128)
    if abs(frac) < 1e-12:
        return x
    n = np.arange(len(x))
    ntaps = 16
    k = np.arange(-ntaps // 2, ntaps // 2 + 1)
    h = np.sinc(k - frac) * np.hanning(len(k))
    h = h / np.sum(h)
    return sps_signal.lfilter(h, 1.0, x)[: len(x)]


def resample_rate(x: np.ndarray, ratio: float) -> np.ndarray:
    """Resample by an arbitrary ratio - models a sample-clock error in ppm."""
    x = np.asarray(x, dtype=np.complex128)
    n_out = int(round(len(x) * ratio))
    if n_out < 2:
        return x
    src = np.arange(len(x))
    dst = np.linspace(0, len(x) - 1, n_out)
    return np.interp(dst, src, x.real) + 1j * np.interp(dst, src, x.imag)


@dataclass
class WattersonChannel:
    """Watterson HF ionospheric model, per ITU-R F.1487.

    Two independently Rayleigh-fading paths separated by `delay_s`, each with a
    Gaussian Doppler spectrum of standard deviation `doppler_hz`.  This is the
    standard against which HF modems are tested, and its two parameters are what
    a propagation-mode hypothesis is built from.

    The fading process is generated at a low rate (Doppler spreads are fractions
    of a hertz while `fs` may be tens of kilohertz) and interpolated up, which is
    both correct and roughly four orders of magnitude cheaper than filtering
    white noise at the sample rate.
    """

    delay_s: float = 1.0e-3
    doppler_hz: float = 0.5
    n_paths: int = 2
    path_gains_db: tuple[float, ...] = (0.0, 0.0)

    @classmethod
    def from_condition(cls, name: str) -> "WattersonChannel":
        if name not in ITU_CONDITIONS:
            raise KeyError(f"unknown ITU condition {name!r}; have {sorted(ITU_CONDITIONS)}")
        d, f = ITU_CONDITIONS[name]
        return cls(delay_s=d, doppler_hz=f)

    def _fading(self, n: int, fs: float, rng: np.random.Generator) -> np.ndarray:
        """One complex Rayleigh tap gain with a Gaussian Doppler spectrum."""
        spread = max(self.doppler_hz, 1e-3)
        # Generate at ~20x the Doppler spread, then interpolate to fs.
        lo_fs = max(spread * 20.0, 4.0)
        n_lo = max(int(np.ceil(n * lo_fs / fs)) + 8, 16)
        w = rng.normal(size=n_lo) + 1j * rng.normal(size=n_lo)

        # Gaussian Doppler shaping in the frequency domain.
        f = np.fft.fftfreq(n_lo, d=1.0 / lo_fs)
        shape = np.exp(-(f ** 2) / (2 * spread ** 2))
        g = np.fft.ifft(np.fft.fft(w) * shape)
        p = np.mean(np.abs(g) ** 2)
        if p > 0:
            g = g / np.sqrt(p)

        t_lo = np.arange(n_lo) / lo_fs
        t_hi = np.arange(n) / fs
        return np.interp(t_hi, t_lo, g.real) + 1j * np.interp(t_hi, t_lo, g.imag)

    def apply(self, x: np.ndarray, fs: float, rng: np.random.Generator | None = None) -> np.ndarray:
        rng = rng or np.random.default_rng()
        x = np.asarray(x, dtype=np.complex128)
        n = len(x)
        delay_samples = int(round(self.delay_s * fs))

        gains = np.array(self.path_gains_db[: self.n_paths], dtype=float)
        if len(gains) < self.n_paths:
            gains = np.concatenate([gains, np.zeros(self.n_paths - len(gains))])
        lin = 10 ** (gains / 20.0)
        lin = lin / np.sqrt(np.sum(lin ** 2))

        out = np.zeros(n, dtype=np.complex128)
        for p in range(self.n_paths):
            tap = self._fading(n, fs, rng) * lin[p]
            d = p * delay_samples
            if d == 0:
                out += tap * x
            elif d < n:
                out[d:] += tap[d:] * x[: n - d]
        return out

    def describe(self) -> str:
        return (
            f"Watterson HF: {self.n_paths} paths, delay {self.delay_s*1e3:.2f} ms, "
            f"Doppler spread {self.doppler_hz:.2f} Hz"
        )

    def propagation_hypothesis(self) -> str:
        """A propagation-mode hypothesis - stated as a hypothesis, not a range."""
        if self.delay_s < 0.2e-3:
            return "groundwave or single-hop, low dispersion"
        if self.delay_s < 1.5e-3:
            return "single-hop skywave (1F or 1E), moderate dispersion"
        return "multi-hop skywave, high dispersion"


# --------------------------------------------------------------------------
# Receiver-side artefacts.  L1 must recognise these; generating them is the
# cheapest way to be certain it can.
# --------------------------------------------------------------------------


def iq_imbalance(x: np.ndarray, gain_db: float = 0.5, phase_deg: float = 2.0) -> np.ndarray:
    """Amplitude and quadrature imbalance, which creates a conjugate image.

    The image is the conjugate mirror of the wanted signal about DC, so it
    correlates with its own mirror - which is exactly the reference-free test L1
    uses to detect it *and* to estimate the imbalance for blind correction.
    """
    x = np.asarray(x, dtype=np.complex128)
    g = 10 ** (gain_db / 20.0)
    phi = np.deg2rad(phase_deg)
    i = np.real(x)
    q = np.imag(x) * g
    return (i + q * np.sin(phi)) + 1j * (q * np.cos(phi))


def dc_offset(x: np.ndarray, dc: complex = 0.05 + 0.02j) -> np.ndarray:
    """LO self-mixing: energy confined to bin 0 with no measurable bandwidth."""
    return np.asarray(x, dtype=np.complex128) + dc


def nonlinearity(x: np.ndarray, iip3: float = 12.0) -> np.ndarray:
    """Third-order front-end nonlinearity, producing harmonics and IMD.

    L1 detects this by the *superlinear* growth of energy at 2f and 3f with the
    power at f - a spur that grows faster than linearly is not an emitter.
    """
    x = np.asarray(x, dtype=np.complex128)
    a3 = 10 ** (-iip3 / 10.0)
    return x - a3 * x * np.abs(x) ** 2


def add_phase_noise(x: np.ndarray, level_dbc_hz: float = -90.0, fs: float = 1.0,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """Oscillator phase noise - a random walk in phase.

    This is one of the residual features that carries **device identity**: it is
    part of what the standard does not specify, which is precisely where a
    physical fingerprint lives.
    """
    rng = rng or np.random.default_rng()
    x = np.asarray(x, dtype=np.complex128)
    sigma = np.sqrt(2 * np.pi * (10 ** (level_dbc_hz / 10.0)) * fs)
    phi = np.cumsum(rng.normal(0.0, sigma, len(x)))
    return x * np.exp(1j * phi)
