"""SSB rendering - how one parameter set produces both an .IQ and a .wav view.

One requirement is easy to read past:

    *"The spectral relationship from training data containing both .IQ and .wav
    formats can be utilised for identifying signal parameters."*

It reads oddly until you notice it is an invitation to cross-format modelling -
and that the twin answers it **by construction** rather than by hoping a network
discovers it from paired data:

    The .IQ file and the .wav file are two RENDERINGS of one underlying emitter:
    full complex baseband, and the real audio-band output of an SSB receiver
    applied to the same signal.  The SSB receiver is just another block in the
    chain, so the "spectral relationship" is not learned - it is a derivable
    transform, and the twin IS that transform.

Practical consequences, all cheap: one model covers both formats instead of two
pipelines; a signature library measured in one format transfers to the other;
and a .wav and an .IQ capture of the same emitter can be fitted jointly against
one shared parameter vector.

The sideband matters and cannot be read off the magnitude spectrum: **LSB
reception mirrors the spectrum relative to USB**, and for a symmetric PSK
spectrum the two are indistinguishable by eye.  Everything downstream breaks
silently on the wrong choice - which is why SHRUTI treats spectral inversion as
a one-bit hypothesis and lets the decoder settle it.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sps_signal

__all__ = ["to_ssb_audio", "from_ssb_audio", "spectral_invert", "analytic_signal"]


def to_ssb_audio(
    baseband: np.ndarray,
    fs: float,
    centre_hz: float = 1800.0,
    sideband: str = "usb",
    passband: tuple[float, float] = (300.0, 3400.0),
) -> np.ndarray:
    """Render complex baseband as the real audio output of an SSB receiver.

    This is what an HF `.wav` file actually contains: real-valued audio at
    8/11.025/22.05/48 kHz, carrying a modem inside roughly 300-3400 Hz, typically
    centred near 1500-1800 Hz.  There is **no complex baseband in the file**, and
    the RF centre frequency is gone unless a sidecar or the filename preserved it.
    """
    x = np.asarray(baseband, dtype=np.complex128)
    if sideband.lower() == "lsb":
        x = np.conj(x)

    n = np.arange(len(x))
    up = x * np.exp(1j * 2 * np.pi * centre_hz * n / fs)
    audio = np.real(up)

    lo, hi = passband
    nyq = fs / 2.0
    lo_n, hi_n = max(lo / nyq, 1e-4), min(hi / nyq, 0.999)
    if lo_n < hi_n:
        b, a = sps_signal.butter(4, [lo_n, hi_n], btype="band")
        audio = sps_signal.filtfilt(b, a, audio)

    peak = np.max(np.abs(audio)) or 1.0
    return (audio / peak * 0.85).astype(np.float64)


def analytic_signal(audio: np.ndarray) -> np.ndarray:
    """Form the analytic signal from real audio - the first step of the L0 audio path.

    Real audio has a Hermitian-symmetric spectrum, so negative frequencies carry
    no independent information.  The Hilbert transform discards them and gives a
    complex signal the rest of the chain can treat like baseband.
    """
    return sps_signal.hilbert(np.asarray(audio, dtype=np.float64))


def from_ssb_audio(
    audio: np.ndarray,
    fs: float,
    centre_hz: float,
    sideband: str = "usb",
) -> np.ndarray:
    """Recover complex baseband from SSB audio - the inverse of :func:`to_ssb_audio`.

    `sideband` is a **hypothesis**, not a known.  Try both and let the code
    decide: where a conventional tool needs a human to flip a switch and listen,
    SHRUTI resolves it with a binomial test on parity checks.
    """
    z = analytic_signal(audio)
    n = np.arange(len(z))
    bb = z * np.exp(-1j * 2 * np.pi * centre_hz * n / fs)
    return np.conj(bb) if sideband.lower() == "lsb" else bb


def spectral_invert(x: np.ndarray) -> np.ndarray:
    """Mirror the spectrum about DC.  A one-bit hypothesis the decoder resolves."""
    return np.conj(np.asarray(x, dtype=np.complex128))
