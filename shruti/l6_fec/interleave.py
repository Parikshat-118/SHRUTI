"""Interleavers: block, convolutional, diagonal and pseudo-random.

All four families are implemented by name.  The unifying observation - and the reason this is one mechanism
rather than four engineering efforts:

    All four are PERMUTATIONS.  A permutation is linear over GF(2).  A linear
    code composed with a permutation is still a linear code.  So for *detection*
    the same rank-deficiency / dual-code machinery covers all four identically;
    what differs between them is only the PATTERN of syndrome failures, which is
    cheap to classify once the composite has been detected.

Blind signatures, which is what L6 classifies on:

===============  =================================================  ==============
Type             Signature                                          Recoverable?
===============  =================================================  ==============
Block            failures periodic at R*C; rank deficit at R*C      fully
Convolution      period N, delay step M, **no frame boundary** -    fully
                 the absence of a boundary is the discriminator
Diagonal         same period as block, different in-period pattern  fully
Pseudo Random    period detectable; permutation is NOT blindly      period + depth
                 recoverable in general                             only
===============  =================================================  ==============

That last row is the one place in this problem where the mathematics genuinely
refuses, and SHRUTI says so rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "Interleaver",
    "BlockInterleaver",
    "DiagonalInterleaver",
    "ConvolutionalInterleaver",
    "PseudoRandomInterleaver",
    "build",
]


class Interleaver:
    """Base class.  Subclasses supply a permutation or a streaming transform.

    ``symbol_bits`` is the size of the unit being permuted.  This is not a
    detail: **CCSDS RS interleaving of depth I permutes GF(256) symbols, not
    bits.**  Modelling it as a bit interleaver of the same geometry produces a
    permutation that does not preserve byte boundaries, so the RS decoder
    downstream sees misaligned codewords and fails - while the payload still
    appears, because RS is systematic.  That combination (text looks right,
    certificate says no) is exactly what the certificate is for.
    """

    kind: str = "none"
    symbol_bits: int = 1

    def _expand(self, sym_perm: np.ndarray) -> np.ndarray:
        """Lift a permutation of symbols to a permutation of bits."""
        if self.symbol_bits <= 1:
            return sym_perm
        return (
            sym_perm[:, None] * self.symbol_bits + np.arange(self.symbol_bits)
        ).reshape(-1)

    @property
    def period(self) -> int:
        """Length over which the permutation repeats."""
        raise NotImplementedError

    @property
    def depth(self) -> int:
        """Interleaving depth - how far apart adjacent input bits are spread."""
        raise NotImplementedError

    def permutation(self, n: int | None = None) -> np.ndarray:
        """Index array `p` such that ``out[i] = inp[p[i]]`` over one period."""
        raise NotImplementedError

    def interleave(self, bits: np.ndarray) -> np.ndarray:
        """Permute, **padding up to a whole number of periods**.

        Padding rather than passing a short final block through unpermuted is
        what makes the transform total, and therefore invertible by a receiver
        that does not know the original length.

        A pass-through tail looks symmetric and is not: any later stage that
        changes the stream length - frame padding, a flush tail, a demodulator
        returning a few bits fewer - shifts the receiver's idea of how many
        complete periods exist.  It then de-permutes a block that was never
        permuted, and the damage begins at an exact multiple of the period with
        everything before it perfectly clean.
        """
        p = self.permutation()
        bits = np.asarray(bits).reshape(-1)
        pad = (-len(bits)) % len(p)
        if pad:
            bits = np.concatenate([bits, np.zeros(pad, dtype=bits.dtype)])
        return bits.reshape(-1, len(p))[:, p].reshape(-1)

    def deinterleave(self, bits: np.ndarray) -> np.ndarray:
        """Undo the permutation over complete periods only.

        **The incomplete final period is discarded, not passed through.**  On the
        transmit side a partial block can be padded and sent verbatim, so passing
        it through looks symmetric - but a real demodulator returns a slightly
        different number of bits than were sent, so the receiver's idea of where
        the partial block starts is wrong.  Emitting those bits anyway hands the
        decoder downstream a region that is silently scrambled, which shows up as
        codeword failures scattered through an otherwise clean decode.

        Refusing to emit data known to be unreliable is the same discipline the
        rest of the tool applies at every other layer.
        """
        p = self.permutation()
        inv = np.argsort(p)
        bits = np.asarray(bits).reshape(-1)
        nper = len(bits) // len(p)
        if nper == 0:
            return bits[:0].copy()
        return bits[: nper * len(p)].reshape(nper, len(p))[:, inv].reshape(-1)

    def describe(self) -> str:
        return f"{self.kind} interleaver, period {self.period}, depth {self.depth}"


@dataclass
class BlockInterleaver(Interleaver):
    """Write rows, read columns, over an ``R x C`` frame.

    The classic.  CCSDS RS interleaving depth I in {1,2,3,4,5,8} is this, with
    I = 1 meaning no interleaving.
    """

    rows: int
    cols: int
    symbol_bits: int = 1
    kind: str = "block"

    @property
    def period(self) -> int:
        return self.rows * self.cols * self.symbol_bits

    @property
    def depth(self) -> int:
        return self.rows

    def permutation(self, n: int | None = None) -> np.ndarray:
        sym = np.arange(self.rows * self.cols).reshape(self.rows, self.cols).T.reshape(-1)
        return self._expand(sym)

    def describe(self) -> str:
        unit = "symbol" if self.symbol_bits > 1 else "bit"
        return (f"block interleaver {self.rows}x{self.cols} ({unit}-wise), "
                f"period {self.period} bits")


@dataclass
class DiagonalInterleaver(Interleaver):
    """A block interleaver read along diagonals of the ``R x C`` grid.

    One specific permutation of the same grid as :class:`BlockInterleaver`, so it
    has the *same period* and is distinguished only by the in-period pattern.
    The variant family is small and finite, so L6 enumerates it rather than
    treating it as an open problem.
    """

    rows: int
    cols: int
    symbol_bits: int = 1
    kind: str = "diagonal"

    @property
    def period(self) -> int:
        return self.rows * self.cols * self.symbol_bits

    @property
    def depth(self) -> int:
        return min(self.rows, self.cols)

    def permutation(self, n: int | None = None) -> np.ndarray:
        R, C = self.rows, self.cols
        r = np.arange(R)
        out = np.empty((C, R), dtype=np.int64)
        for d in range(C):
            out[d] = r * C + ((r + d) % C)
        return self._expand(out.reshape(-1))

    def describe(self) -> str:
        unit = "symbol" if self.symbol_bits > 1 else "bit"
        return (f"diagonal interleaver {self.rows}x{self.cols} ({unit}-wise), "
                f"period {self.period} bits")


@dataclass
class ConvolutionalInterleaver(Interleaver):
    """Ramsey / Forney convolutional interleaver: `branches` lines, delay step `delay`.

    Branch *i* delays by ``i * delay`` symbols.  Crucially there is **no frame
    boundary at all** - and that absence is exactly what tells it apart from a
    block interleaver of the same period - which is what makes the two
    distinguishable blind, rather than merely nameable.
    """

    branches: int
    delay: int
    kind: str = "convolutional"

    @property
    def period(self) -> int:
        return self.branches

    @property
    def depth(self) -> int:
        return self.branches * self.delay

    def permutation(self, n: int | None = None) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError(
            "a convolutional interleaver is a streaming transform with no frame "
            "boundary; use interleave()/deinterleave()"
        )

    def _run(self, bits: np.ndarray, delays: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        regs = [np.zeros(d, dtype=np.uint8) for d in delays]
        out = np.empty(len(bits), dtype=np.uint8)
        for i, b in enumerate(bits):
            br = i % self.branches
            if delays[br] == 0:
                out[i] = b
            else:
                out[i] = regs[br][0]
                regs[br] = np.concatenate([regs[br][1:], [b]])
        return out

    def interleave(self, bits: np.ndarray) -> np.ndarray:
        delays = np.arange(self.branches) * self.delay
        return self._run(bits, delays)

    def deinterleave(self, bits: np.ndarray) -> np.ndarray:
        # The matched de-interleaver mirrors the delays.
        delays = (self.branches - 1 - np.arange(self.branches)) * self.delay
        return self._run(bits, delays)

    @property
    def latency(self) -> int:
        """Total end-to-end delay, which is how much of the tail is unusable."""
        return self.branches * (self.branches - 1) * self.delay

    def describe(self) -> str:
        return (
            f"convolutional interleaver, {self.branches} branches, "
            f"delay step {self.delay} (no frame boundary)"
        )


@dataclass
class PseudoRandomInterleaver(Interleaver):
    """An arbitrary permutation of `size`, generated from `seed`.

    **Honest limit, and it is the one place the mathematics refuses:** an unknown
    pseudo-random permutation of large period is not blindly recoverable in the
    general case.  What *is* achievable is a great deal - detect that an
    interleaver is present, and estimate its period and depth from the
    periodicity of syndrome-failure positions.  A tool that reports
    *"interleaved, period 1152, permutation not blindly identifiable at this
    length"* is more valuable than one that guesses.
    """

    size: int
    seed: int = 0
    kind: str = "pseudo_random"

    @property
    def period(self) -> int:
        return self.size

    @property
    def depth(self) -> int:
        return self.size

    def permutation(self, n: int | None = None) -> np.ndarray:
        return np.random.default_rng(self.seed).permutation(self.size)

    def describe(self) -> str:
        return f"pseudo-random interleaver, period {self.size}, seed 0x{self.seed:X}"


def build(spec: dict) -> Interleaver | None:
    """Construct an interleaver from a cartridge fragment.

    ``{type: block, rows: 40, cols: 72}`` and friends.  Returns ``None`` for
    ``{type: none}`` so a cartridge can state "no interleaving" explicitly
    rather than by omission.
    """
    kind = str(spec.get("type", "none")).lower().replace("-", "_")
    if kind in ("none", "", "identity"):
        return None
    sym_bits = int(spec.get("symbol_bits", 8 if str(spec.get("unit", "bit")).lower()
                            in ("symbol", "byte") else 1))
    if kind == "block":
        return BlockInterleaver(int(spec["rows"]), int(spec["cols"]), sym_bits)
    if kind == "diagonal":
        return DiagonalInterleaver(int(spec["rows"]), int(spec["cols"]), sym_bits)
    if kind in ("convolutional", "convolution"):
        return ConvolutionalInterleaver(int(spec["branches"]), int(spec["delay"]))
    if kind in ("pseudo_random", "pseudorandom", "prbs", "random"):
        return PseudoRandomInterleaver(int(spec["size"]), int(spec.get("seed", 0)))
    raise ValueError(f"unknown interleaver type {kind!r}")
