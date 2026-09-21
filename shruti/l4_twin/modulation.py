"""Modulation mappers for the FSK, QAM and PSK families.

All three named families, plus the differential and offset variants that show up
constantly in real HF/VHF traffic and that a demodulator must handle or fail
silently on.

Every linear modulation exposes the same two operations:

* ``map(bits) -> complex symbols``  - used by the twin to synthesise
* ``demap_llr(symbols, noise_var) -> LLRs`` - used by L5 to produce **soft** bits

The soft demapper is generic over any labelled constellation via max-log:

    LLR_i = [ min_{p : b_i(p)=1} |r-p|^2  -  min_{p : b_i(p)=0} |r-p|^2 ] / noise_var

Positive LLR means bit 0, matching ``shruti.core.bits``.

**Ambiguities are not resolved here, deliberately.**  Phase rotation by a
constellation symmetry, differential-vs-absolute encoding, bit order and
spectral inversion are all small-cardinality hypotheses, and SHRUTI resolves
them the same way it resolves everything else: by which one lets the code decode.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "Modulation",
    "PSK",
    "QAM",
    "FSK",
    "build",
    "gray",
    "inverse_gray",
]


def gray(v: np.ndarray | int):
    """Binary -> Gray code."""
    if isinstance(v, int):
        return v ^ (v >> 1)
    v = np.asarray(v, dtype=np.int64)
    return v ^ (v >> 1)


def inverse_gray(g: int) -> int:
    """Gray code -> binary."""
    v = g
    shift = 1
    while (g >> shift) > 0:
        v ^= g >> shift
        shift += 1
    return v


class Modulation:
    """Base class for a labelled complex constellation."""

    kind: str = "none"
    order: int = 2
    differential: bool = False

    @property
    def bits_per_symbol(self) -> int:
        return int(np.log2(self.order))

    @property
    def points(self) -> np.ndarray:
        """Constellation points, indexed by the integer the bits form."""
        raise NotImplementedError

    @property
    def is_linear(self) -> bool:
        """True if the modulation produces symbols for a pulse shaper."""
        return True

    # ------------------------------------------------------------------ bits

    def _bits_to_ints(self, bits: np.ndarray) -> np.ndarray:
        b = self.bits_per_symbol
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        n = (len(bits) // b) * b
        if n == 0:
            return np.zeros(0, dtype=np.int64)
        g = bits[:n].reshape(-1, b).astype(np.int64)
        weights = (1 << np.arange(b - 1, -1, -1)).astype(np.int64)
        return g @ weights

    def _label_table(self) -> np.ndarray:
        """``(order, bits_per_symbol)`` array of the bits each point carries."""
        b = self.bits_per_symbol
        idx = np.arange(self.order, dtype=np.int64)
        shifts = np.arange(b - 1, -1, -1)
        return ((idx[:, None] >> shifts[None, :]) & 1).astype(np.uint8)

    # -------------------------------------------------------------- mapping

    def map(self, bits: np.ndarray) -> np.ndarray:
        syms = self.points[self._bits_to_ints(bits)]
        if self.differential:
            syms = np.cumprod(syms / np.abs(syms))
        return syms.astype(np.complex128)

    def demap_llr(self, rx: np.ndarray, noise_var: float = 1.0) -> np.ndarray:
        """Max-log soft demapping.  Returns one LLR per bit."""
        rx = np.asarray(rx, dtype=np.complex128).reshape(-1)
        if self.differential:
            prev = np.concatenate([[1.0 + 0j], rx[:-1]])
            with np.errstate(invalid="ignore", divide="ignore"):
                rx = rx * np.conj(prev) / np.maximum(np.abs(prev), 1e-12)

        pts = self.points
        labels = self._label_table()
        noise_var = max(float(noise_var), 1e-12)

        d2 = np.abs(rx[:, None] - pts[None, :]) ** 2          # (N, order)
        b = self.bits_per_symbol
        out = np.empty((len(rx), b), dtype=np.float64)
        for i in range(b):
            ones = labels[:, i] == 1
            m1 = d2[:, ones].min(axis=1)
            m0 = d2[:, ~ones].min(axis=1)
            out[:, i] = (m1 - m0) / noise_var
        return out.reshape(-1)

    def describe(self) -> str:
        d = "differential " if self.differential else ""
        return f"{d}{self.order}-{self.kind.upper()}"


@dataclass
class PSK(Modulation):
    """Phase-shift keying.  BPSK, QPSK, 8-PSK, and the differential variants.

    ``pi4`` selects pi/4-DQPSK, which alternates between two QPSK
    constellations offset by 45 degrees - ubiquitous in land-mobile radio, and a
    common silent failure for demodulators that assume plain DQPSK.
    """

    order: int = 4
    differential: bool = False
    pi4: bool = False
    offset: bool = False          #: OQPSK - Q delayed by half a symbol (see chain)
    phase_offset: float = 0.0
    #: Constellation rotation.  ``None`` means "conventional": QPSK sits at
    #: +/-45 degrees, every other order starts on the real axis.  The pi/4-DQPSK
    #: demapper passes 0.0 explicitly, because its reference constellation must
    #: NOT carry QPSK's 45-degree offset - leaving that implicit is a silent
    #: half-symbol rotation and the demapper returns noise.
    base_offset: float | None = None
    kind: str = "psk"

    def _base(self) -> float:
        if self.base_offset is not None:
            return float(self.base_offset)
        return np.pi / 4 if (self.order == 4 and not self.differential and not self.pi4) else 0.0

    @property
    def points(self) -> np.ndarray:
        k = gray(np.arange(self.order))
        return np.exp(1j * (2 * np.pi * k / self.order + self._base() + self.phase_offset))

    def map(self, bits: np.ndarray) -> np.ndarray:
        if not self.pi4:
            return super().map(bits)
        # pi/4-DQPSK: differential, with an extra pi/4 rotation each symbol.
        idx = self._bits_to_ints(bits)
        dphi = (2 * np.pi * gray(idx) / self.order) + np.pi / self.order
        return np.exp(1j * np.cumsum(dphi)).astype(np.complex128)

    def demap_llr(self, rx: np.ndarray, noise_var: float = 1.0) -> np.ndarray:
        if not self.pi4:
            return super().demap_llr(rx, noise_var)
        rx = np.asarray(rx, dtype=np.complex128).reshape(-1)
        prev = np.concatenate([[1.0 + 0j], rx[:-1]])
        with np.errstate(invalid="ignore", divide="ignore"):
            diff = rx * np.conj(prev) / np.maximum(np.abs(prev), 1e-12)
        diff = diff * np.exp(-1j * np.pi / self.order)
        plain = PSK(order=self.order, differential=False, base_offset=0.0)
        return plain.demap_llr(diff, noise_var)

    def describe(self) -> str:
        if self.pi4:
            return "pi/4-DQPSK"
        if self.offset:
            return "OQPSK"
        d = "D" if self.differential else ""
        names = {2: "BPSK", 4: "QPSK", 8: "8-PSK", 16: "16-PSK"}
        return d + names.get(self.order, f"{self.order}-PSK")


@dataclass
class QAM(Modulation):
    """Quadrature amplitude modulation: 16, 32 (cross) and 64.

    Square orders use independent Gray-coded PAM on I and Q, which is the
    universal convention.  **32-QAM is a cross constellation and its bit mapping
    is not universally standardised** - the one here is deterministic and
    self-consistent, and a cartridge that must match a specific standard should
    carry that standard's mapping explicitly rather than assume this one.
    """

    order: int = 16
    differential: bool = False
    kind: str = "qam"
    _pts: np.ndarray = field(default=None, init=False, repr=False, compare=False)

    @property
    def points(self) -> np.ndarray:
        if self._pts is not None:
            return self._pts
        b = self.bits_per_symbol
        if b % 2 == 0:
            L = int(np.sqrt(self.order))
            half = b // 2
            g = gray(np.arange(L))
            levels = np.empty(L)
            levels[g] = 2 * np.arange(L) - (L - 1)
            idx = np.arange(self.order)
            i_bits, q_bits = idx >> half, idx & ((1 << half) - 1)
            pts = levels[gray(i_bits)] + 1j * levels[gray(q_bits)]
        else:
            pts = self._cross_constellation()
        pts = pts / np.sqrt(np.mean(np.abs(pts) ** 2))
        object.__setattr__(self, "_pts", pts)
        return pts

    def _cross_constellation(self) -> np.ndarray:
        """Cross QAM (32, 128): the square grid with its corners removed."""
        side = int(np.ceil(np.sqrt(self.order * 2)))
        if side % 2:
            side += 1
        lv = 2 * np.arange(side) - (side - 1)
        grid = np.array([complex(i, q) for q in lv[::-1] for i in lv])
        keep = np.argsort(np.abs(grid), kind="stable")[: self.order]
        return grid[np.sort(keep)]

    def describe(self) -> str:
        return f"{self.order}-QAM"


@dataclass
class FSK(Modulation):
    """Continuous-phase frequency-shift keying: 2-FSK and 4-FSK.

    Unlike PSK/QAM this is **not** a linear modulation - there is no
    constellation for a pulse shaper to filter, so the twin renders FSK samples
    directly and L5 demodulates it with a non-coherent filter bank.
    ``is_linear`` is how the chain decides which path to take.

    ``h`` is the modulation index: tone spacing = h / symbol_period.  h = 0.5 is
    MSK, h = 1.0 is orthogonal non-coherent FSK.
    """

    order: int = 2
    h: float = 1.0
    kind: str = "fsk"
    differential: bool = False

    @property
    def is_linear(self) -> bool:
        return False

    @property
    def points(self) -> np.ndarray:
        # Not a constellation; the "points" are normalised tone offsets.
        m = np.arange(self.order)
        return (2 * m - (self.order - 1)).astype(np.complex128)

    def tone_offsets(self, symbol_rate: float) -> np.ndarray:
        """Tone frequencies in Hz relative to the carrier."""
        m = np.arange(self.order)
        return (2 * m - (self.order - 1)) * 0.5 * self.h * symbol_rate

    def render(self, bits: np.ndarray, sps: int, symbol_rate: float, fs: float) -> np.ndarray:
        """Render CPFSK samples directly, with continuous phase."""
        idx = self._bits_to_ints(bits)
        idx = gray(idx)
        offs = self.tone_offsets(symbol_rate)[idx]
        inst = np.repeat(offs, sps)
        phase = 2 * np.pi * np.cumsum(inst) / fs
        return np.exp(1j * phase).astype(np.complex128)

    def describe(self) -> str:
        return f"{self.order}-FSK (h={self.h:g})"


def build(spec: dict) -> Modulation:
    """Construct a modulation from a cartridge fragment."""
    kind = str(spec.get("type", "psk")).lower()
    order = int(spec.get("order", 2))
    if kind == "psk":
        return PSK(
            order=order,
            differential=bool(spec.get("differential", False)),
            pi4=bool(spec.get("pi4", False)),
            offset=bool(spec.get("offset", False)),
        )
    if kind == "qam":
        return QAM(order=order)
    if kind == "fsk":
        return FSK(order=order, h=float(spec.get("h", 1.0)))
    raise ValueError(f"unknown modulation type {kind!r}")
