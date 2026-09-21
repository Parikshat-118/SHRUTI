"""Container inference: what is this file, actually?

The decision tree, and every branch of it is a real case that appears in archives:

    .wav ---- 1 channel --> real audio.  Almost always an SSB receiver's output.
           |                Form the analytic signal; the modem is inside
           |                300-3400 Hz; RF centre frequency is GONE.
           |
           +-- 2 channels -> either true stereo audio, or I-in-left/Q-in-right.
                             Decided by inter-channel correlation and by whether
                             treating it as complex yields a non-Hermitian
                             spectrum (real signals have Hermitian spectra).

    raw ----> dtype and endianness inferred from file size, value distribution
              and DC balance.  Nothing is asked of the user.
"""

from __future__ import annotations

import pathlib
import struct
import wave
from dataclasses import dataclass, field

import numpy as np

from .filename import EXTENSION_DTYPES, FilenameInfo, parse_filename

__all__ = ["Capture", "ContainerInfo", "load", "load_wav", "load_iq", "infer_dtype", "DTYPES"]


#: Candidate raw sample formats, commonest first.
DTYPES: dict[str, np.dtype] = {
    "int8": np.dtype(np.int8),
    "uint8": np.dtype(np.uint8),
    "int16": np.dtype("<i2"),
    "int16be": np.dtype(">i2"),
    "int32": np.dtype("<i4"),
    "float32": np.dtype("<f4"),
    "float32be": np.dtype(">f4"),
    "float64": np.dtype("<f8"),
}


@dataclass
class ContainerInfo:
    """Everything L0 concluded, and why - so the GUI can show its reasoning."""

    path: str
    kind: str = "unknown"            #: iq | audio | iq_in_stereo | stereo_audio
    dtype: str = "unknown"
    channels: int = 1
    sample_rate: float | None = None
    centre_hz: float | None = None
    is_complex: bool = True
    n_samples: int = 0
    rate_basis: str = "unknown"      #: header | filename | sidecar | anchored | assumed
    centre_basis: str = "unknown"
    reasons: list[str] = field(default_factory=list)
    filename_info: FilenameInfo | None = None

    def add(self, reason: str) -> None:
        self.reasons.append(reason)

    def summary(self) -> str:
        sr = f"{self.sample_rate:g} Hz ({self.rate_basis})" if self.sample_rate else "unknown"
        cf = f"{self.centre_hz/1e6:.6f} MHz ({self.centre_basis})" if self.centre_hz else "unknown"
        return (
            f"{self.kind}, {self.dtype}, {self.channels}ch, "
            f"{self.n_samples} samples, rate {sr}, centre {cf}"
        )


@dataclass
class Capture:
    """A loaded capture: complex baseband plus what L0 worked out about it."""

    samples: np.ndarray
    info: ContainerInfo

    @property
    def fs(self) -> float:
        return float(self.info.sample_rate or 1.0)

    @property
    def duration_s(self) -> float:
        return len(self.samples) / self.fs if self.info.sample_rate else float("nan")

    def __len__(self) -> int:
        return len(self.samples)


# --------------------------------------------------------------------------- wav


def _read_wav_raw(path: pathlib.Path) -> tuple[np.ndarray, int, int, dict]:
    """Read a RIFF WAVE file with stdlib only, plus any extra chunks.

    stdlib `wave` rather than `soundfile`: it avoids an LGPL binary dependency
    (libsndfile), which keeps the whole runtime permissively licensed and the
    air-gapped install a single folder copy.
    """
    extras: dict = {}
    with open(path, "rb") as fh:
        raw = fh.read(12)
        if len(raw) >= 12 and raw[:4] == b"RIFF":
            fh.seek(12)
            while True:
                hdr = fh.read(8)
                if len(hdr) < 8:
                    break
                cid, size = struct.unpack("<4sI", hdr)
                data = fh.read(size) if cid not in (b"data",) else b""
                if cid == b"data":
                    fh.seek(size, 1)
                if size % 2:
                    fh.seek(1, 1)
                if cid == b"auxi" and len(data) >= 36:
                    extras["auxi"] = data
                elif cid == b"LIST":
                    extras["list"] = data

    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        fs = w.getframerate()
        frames = w.readframes(w.getnframes())

    if sw == 1:
        arr = np.frombuffer(frames, dtype=np.uint8).astype(np.float64) - 128.0
        arr /= 128.0
    elif sw == 2:
        arr = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32)
             | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        arr = v.astype(np.float64) / 8388608.0
    elif sw == 4:
        arr = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        raise ValueError(f"unsupported wav sample width {sw}")

    return arr.reshape(-1, nch) if nch > 1 else arr.reshape(-1, 1), fs, sw, extras


def _parse_auxi(data: bytes) -> dict:
    """The `auxi` chunk SDR recorders write: centre frequency and start time."""
    out: dict = {}
    try:
        if len(data) >= 36:
            cf = struct.unpack_from("<I", data, 32)[0]
            if 0 < cf < 30_000_000_000:
                out["centre_hz"] = float(cf)
    except Exception:                                          # noqa: BLE001
        pass
    return out


def _decide_two_channel(a: np.ndarray, b: np.ndarray) -> tuple[str, str]:
    """Is a 2-channel wav true stereo audio, or I/Q in left/right?

    Treat it as complex and ask whether the spectrum is Hermitian.  A *real*
    signal has a Hermitian spectrum (negative frequencies mirror the positive
    ones); genuine IQ does not.  This is cheap, needs no metadata, and is the
    difference between analysing a signal and analysing its mirror image.
    """
    n = min(len(a), 1 << 15)
    z = (a[:n] + 1j * b[:n]).astype(np.complex128)
    if np.allclose(b[:n], 0):
        return "audio", "right channel is silent - treating as mono audio"

    Z = np.fft.fft(z - z.mean())
    pos = np.abs(Z[1 : len(Z) // 2])
    neg = np.abs(Z[len(Z) // 2 + 1 :][::-1])
    m = min(len(pos), len(neg))
    if m < 16:
        return "iq_in_stereo", "too short to test Hermitian symmetry; assuming IQ"

    denom = np.linalg.norm(pos[:m]) * np.linalg.norm(neg[:m])
    herm = float(np.dot(pos[:m], neg[:m]) / denom) if denom > 0 else 0.0
    corr = float(np.corrcoef(a[:n], b[:n])[0, 1]) if n > 8 else 0.0

    if herm > 0.95:
        return "stereo_audio", (
            f"spectrum is Hermitian (r={herm:.3f}) - the two channels are a real "
            "signal, i.e. true stereo audio, not IQ"
        )
    return "iq_in_stereo", (
        f"spectrum is not Hermitian (r={herm:.3f}, inter-channel corr={corr:.3f}) "
        "- consistent with I in left, Q in right"
    )


def load_wav(path: str | pathlib.Path) -> Capture:
    """Load a `.wav`, deciding between mono SSB audio, stereo audio and IQ."""
    p = pathlib.Path(path)
    data, fs, sw, extras = _read_wav_raw(p)
    nch = data.shape[1]

    info = ContainerInfo(
        path=str(p),
        dtype={1: "uint8", 2: "int16", 3: "int24", 4: "int32"}.get(sw, f"{sw}B"),
        channels=nch,
        sample_rate=float(fs),
        rate_basis="header",
    )
    info.add(f"RIFF header gives {fs} Hz, {nch} channel(s), {sw*8}-bit")

    fn = parse_filename(p.name)
    info.filename_info = fn
    if fn.found_anything:
        info.add(f"filename convention: {fn.evidence()}")
    if "auxi" in extras:
        aux = _parse_auxi(extras["auxi"])
        if "centre_hz" in aux:
            info.centre_hz = aux["centre_hz"]
            info.centre_basis = "auxi chunk"
            info.add(f"auxi chunk gives centre {aux['centre_hz']/1e6:.6f} MHz")
    if info.centre_hz is None and fn.centre_hz:
        info.centre_hz = fn.centre_hz
        info.centre_basis = "filename"

    if nch == 1:
        info.kind = "audio"
        info.is_complex = False
        info.add(
            "single channel: real audio baseband. This is the SSB-receiver case - "
            "RF centre frequency is NOT recoverable from the samples"
        )
        from ..l4_twin.ssb import analytic_signal
        samples = analytic_signal(data[:, 0])
    else:
        kind, why = _decide_two_channel(data[:, 0], data[:, 1])
        info.kind = kind
        info.add(why)
        if kind == "iq_in_stereo":
            samples = (data[:, 0] + 1j * data[:, 1]).astype(np.complex128)
        else:
            info.is_complex = False
            from ..l4_twin.ssb import analytic_signal
            samples = analytic_signal(data[:, 0])

    info.n_samples = len(samples)
    return Capture(samples=samples, info=info)


# --------------------------------------------------------------------------- raw


def infer_dtype(path: pathlib.Path, hint: str | None = None) -> tuple[str, str]:
    """Guess the sample format of a headerless file.

    Scores each candidate on whether the decoded values look like a plausible
    baseband signal: roughly zero-mean, not clipped, not absurdly peaky.  Returns
    ``(dtype_name, reason)``.
    """
    size = path.stat().st_size
    if hint and hint in DTYPES:
        return hint, f"extension implies {hint}"

    head = np.fromfile(path, dtype=np.uint8, count=min(size, 1 << 20))
    best, best_score, why = "int16", -1e18, ""

    for name, dt in DTYPES.items():
        if size % (dt.itemsize * 2):
            continue
        n = len(head) // dt.itemsize
        if n < 64:
            continue
        # Reinterpreting arbitrary bytes as float can produce NaN/Inf bit
        # patterns; that is itself evidence the candidate dtype is wrong, so
        # treat it as a rejection rather than letting a warning escape.
        with np.errstate(invalid="ignore", over="ignore"):
            v = head[: n * dt.itemsize].view(dt).astype(np.float64)
        if name == "uint8":
            v = v - 128.0
        if not np.all(np.isfinite(v)) or np.allclose(v, 0):
            continue

        scale = np.percentile(np.abs(v), 99) or 1.0
        vn = v / scale
        dc = abs(float(np.mean(vn)))
        kurt = float(np.mean(vn ** 4) / max(np.mean(vn ** 2) ** 2, 1e-12))
        clipped = float(np.mean(np.abs(vn) > 0.999))

        score = -abs(kurt - 2.0) - 4.0 * dc - 8.0 * clipped
        if dt.itemsize in (2, 4):
            score += 0.5                       # int16/float32 are by far commonest
        if score > best_score:
            best, best_score = name, score
            why = (f"{name}: DC {dc:.3f}, kurtosis {kurt:.2f}, "
                   f"clipped {clipped*100:.1f}% - best fit of "
                   f"{len([d for d in DTYPES])} candidates")

    return best, why


def load_iq(
    path: str | pathlib.Path,
    dtype: str | None = None,
    sample_rate: float | None = None,
    header_skip: int = 0,
    max_samples: int | None = None,
) -> Capture:
    """Load interleaved IQ from a headerless file, inferring what is not given."""
    p = pathlib.Path(path)
    info = ContainerInfo(path=str(p), kind="iq", channels=2, is_complex=True)

    fn = parse_filename(p.name)
    info.filename_info = fn
    if fn.found_anything:
        info.add(f"filename convention: {fn.evidence()}")

    ext = p.suffix.lower()
    hint = dtype or fn.dtype or (EXTENSION_DTYPES.get(ext, (None, None))[0])
    name, why = infer_dtype(p, hint)
    info.dtype = name
    info.add(why or f"using {name}")

    dt = DTYPES[name]
    raw = np.memmap(p, dtype=dt, mode="r", offset=header_skip)
    n = (len(raw) // 2) * 2
    if max_samples:
        n = min(n, max_samples * 2)
    v = np.asarray(raw[:n], dtype=np.float64)
    if name == "uint8":
        v = v - 128.0
    scale = {1: 128.0, 2: 32768.0, 4: 2147483648.0}.get(dt.itemsize, 1.0)
    if dt.kind in "iu":
        v = v / scale
    samples = (v[0::2] + 1j * v[1::2]).astype(np.complex128)

    if sample_rate:
        info.sample_rate, info.rate_basis = float(sample_rate), "given"
    elif fn.sample_rate:
        info.sample_rate, info.rate_basis = fn.sample_rate, "filename"
    else:
        info.sample_rate, info.rate_basis = 1.0, "NOT IDENTIFIABLE"
        info.add(
            "absolute sample rate is NOT identifiable from a headerless file - "
            "every measurable quantity is a ratio. Normalised to 1.0; supply a "
            "rate, a sidecar, or let in-band anchoring solve it"
        )

    if fn.centre_hz:
        info.centre_hz, info.centre_basis = fn.centre_hz, "filename"

    info.n_samples = len(samples)
    return Capture(samples=samples, info=info)


def load(path: str | pathlib.Path, **kwargs) -> Capture:
    """Load any supported capture, choosing the reader by content and extension."""
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    suffix = p.suffix.lower()
    if suffix == ".wav":
        return load_wav(p)
    if suffix in (".sigmf-data", ".sigmf-meta") or p.with_suffix(".sigmf-meta").exists():
        from .sigmf_io import read_sigmf
        return read_sigmf(p, **kwargs)

    with open(p, "rb") as fh:
        if fh.read(4) == b"RIFF":
            return load_wav(p)

    return load_iq(p, **kwargs)
