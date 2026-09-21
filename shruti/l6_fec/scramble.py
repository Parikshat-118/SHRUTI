"""Scramblers - the layer that is rarely enumerated but is almost always present.

Nearly every real military and commercial waveform applies an additive or
self-synchronous scrambler between FEC encoding and modulation, to break up long
runs and guarantee transition density for the receiver's timing recovery.

**Why this matters more than it looks.**  Interleaving and FEC get enumerated;
scrambling usually does not.  Yet CCSDS 131.0-B puts a **pseudo-randomiser
between two of the stages that are** (after RS encoding, before the sync marker).
An implementation that handles interleaving and FEC without this will find its
FEC stage failing on every realistic capture for reasons it cannot diagnose,
because a descrambled stream and a scrambled one are statistically identical
until you test a parity check.

Two families:

* **Additive / synchronous** - XOR with an LFSR run freely from a known seed.
  Self-inverse, does not propagate errors, but needs frame alignment.
* **Self-synchronous / multiplicative** - feedback taken from the *transmitted*
  stream, so the receiver locks without alignment, at the cost of multiplying
  each channel error by the tap count.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "lfsr_sequence",
    "AdditiveScrambler",
    "SelfSyncScrambler",
    "CCSDS_RANDOMISER",
    "build",
]


def lfsr_sequence(poly: int, seed: int, length: int, width: int | None = None) -> np.ndarray:
    """Generate `length` bits from a Fibonacci LFSR.

    `poly` is the feedback polynomial as a bit mask over the register, excluding
    the implicit x^0 term.  `width` defaults to the polynomial's bit length.
    """
    if width is None:
        width = max(1, poly.bit_length())
    mask = (1 << width) - 1
    state = seed & mask
    if state == 0:
        state = mask  # an all-zero LFSR is stuck; standards seed with all ones

    out = np.empty(length, dtype=np.uint8)
    for i in range(length):
        bit = state & 1
        out[i] = bit
        fb = bin(state & poly).count("1") & 1
        state = (state >> 1) | (fb << (width - 1))
    return out


@dataclass
class AdditiveScrambler:
    """XOR with a free-running LFSR sequence.  Self-inverse.

    The CCSDS pseudo-randomiser is this, with ``h(x) = x^8 + x^7 + x^5 + x^3 + 1``
    and an all-ones seed, giving a period of 255.
    """

    poly: int = 0b10101001      # x^8 + x^7 + x^5 + x^3 + 1, low-order taps
    seed: int = 0xFF
    width: int = 8
    kind: str = "additive"

    @property
    def period(self) -> int:
        return (1 << self.width) - 1

    def sequence(self, length: int) -> np.ndarray:
        seq = lfsr_sequence(self.poly, self.seed, min(length, self.period), self.width)
        if length <= len(seq):
            return seq[:length]
        reps = (length + len(seq) - 1) // len(seq)
        return np.tile(seq, reps)[:length]

    def apply(self, bits: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        return bits ^ self.sequence(len(bits))

    #: Additive scrambling is an involution - the same operation undoes it.
    descramble = apply

    def describe(self) -> str:
        return f"additive scrambler, poly 0o{self.poly:o}, seed 0x{self.seed:X}, period {self.period}"


@dataclass
class SelfSyncScrambler:
    """Multiplicative scrambler: ``y[n] = x[n] XOR y[n-t1] XOR y[n-t2] ...``.

    Self-synchronising - the descrambler locks with no frame alignment, which is
    why it is common on continuous links.  The cost is **error multiplication**:
    one channel error becomes ``len(taps) + 1`` errors after descrambling, which
    is precisely why L5 must hand L6 *soft* bits rather than hard ones.
    """

    taps: tuple[int, ...] = (18, 23)
    kind: str = "self_sync"

    @property
    def period(self) -> int:
        return (1 << max(self.taps)) - 1

    def apply(self, bits: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        n = len(bits)
        hist = max(self.taps)
        y = np.zeros(n + hist, dtype=np.uint8)
        for i in range(n):
            fb = 0
            for t in self.taps:
                fb ^= y[i + hist - t]
            y[i + hist] = bits[i] ^ fb
        return y[hist:]

    def descramble(self, bits: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        n = len(bits)
        hist = max(self.taps)
        y = np.zeros(n + hist, dtype=np.uint8)
        y[hist:] = bits
        out = np.zeros(n, dtype=np.uint8)
        for i in range(n):
            fb = 0
            for t in self.taps:
                fb ^= y[i + hist - t]
            out[i] = bits[i] ^ fb
        return out

    def describe(self) -> str:
        return f"self-synchronous scrambler, taps {self.taps}"


#: CCSDS 131.0-B pseudo-randomiser, applied between RS encoding and the sync marker.
CCSDS_RANDOMISER = AdditiveScrambler(poly=0b10101001, seed=0xFF, width=8)


def build(spec: dict):
    """Construct a scrambler from a cartridge fragment."""
    kind = str(spec.get("type", "none")).lower().replace("-", "_")
    if kind in ("none", "", "identity"):
        return None
    if kind in ("additive", "synchronous", "randomiser", "randomizer"):
        return AdditiveScrambler(
            poly=int(spec.get("poly", 0b10101001)),
            seed=int(spec.get("seed", 0xFF)),
            width=int(spec.get("width", 8)),
        )
    if kind in ("self_sync", "selfsync", "multiplicative"):
        return SelfSyncScrambler(taps=tuple(int(t) for t in spec.get("taps", (18, 23))))
    raise ValueError(f"unknown scrambler type {kind!r}")
