"""Bit-packed linear algebra over GF(2).

This is the layer that *sounds* expensive and is not.  Everything here is XOR
and ``popcount``: a 10^6-bit stream packs into 125 kB, and rank computations run
in machine words rather than in Python.  A rank over a few thousand rows of a
few hundred columns is milliseconds.

Why it is the heart of L6:

    An interleaver is a permutation, a permutation is linear over GF(2), and a
    linear code composed with a permutation is still a linear code.  So the
    interleaver-and-FEC composite is ONE linear map, and its dual space - the
    parity checks that hold on the received stream - is recoverable by linear
    algebra on the bits.  You do not need to separate the two to *detect* them.

Representation
--------------
A GF(2) matrix is an ``(nrows, nwords)`` array of ``uint64``.  Column *j* of a
row lives in word ``j // 64`` at bit ``j % 64`` counted from the LSB.  The
column count is carried alongside because the packing rounds up to a word.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "BitMatrix",
    "pack",
    "unpack",
    "rank",
    "rref",
    "nullspace",
    "row_space",
    "syndrome",
    "is_codeword",
    "rank_profile",
]

_W = 64


def _nwords(ncols: int) -> int:
    return (ncols + _W - 1) // _W


def pack(bits: np.ndarray) -> np.ndarray:
    """Pack a 2-D 0/1 array into ``uint64`` words, LSB-first within each word."""
    bits = np.atleast_2d(np.asarray(bits, dtype=np.uint8))
    nrows, ncols = bits.shape
    nw = _nwords(ncols)
    padded = np.zeros((nrows, nw * _W), dtype=np.uint64)
    padded[:, :ncols] = bits
    shifts = np.arange(_W, dtype=np.uint64)
    blocks = padded.reshape(nrows, nw, _W)
    return (blocks << shifts[None, None, :]).sum(axis=2, dtype=np.uint64)


def unpack(packed: np.ndarray, ncols: int) -> np.ndarray:
    """Inverse of :func:`pack`."""
    packed = np.atleast_2d(np.asarray(packed, dtype=np.uint64))
    nrows, nw = packed.shape
    shifts = np.arange(_W, dtype=np.uint64)
    bits = ((packed[:, :, None] >> shifts[None, None, :]) & np.uint64(1)).astype(np.uint8)
    return bits.reshape(nrows, nw * _W)[:, :ncols]


@dataclass
class BitMatrix:
    """A GF(2) matrix with its true column count."""

    words: np.ndarray
    ncols: int

    @classmethod
    def from_bits(cls, bits: np.ndarray) -> "BitMatrix":
        bits = np.atleast_2d(np.asarray(bits, dtype=np.uint8))
        return cls(pack(bits), bits.shape[1])

    @property
    def nrows(self) -> int:
        return int(self.words.shape[0])

    def to_bits(self) -> np.ndarray:
        return unpack(self.words, self.ncols)

    def copy(self) -> "BitMatrix":
        return BitMatrix(self.words.copy(), self.ncols)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"BitMatrix({self.nrows}x{self.ncols})"


def _col_mask(col: int) -> tuple[int, np.uint64]:
    return col // _W, np.uint64(1) << np.uint64(col % _W)


def rref(m: BitMatrix, inplace: bool = False) -> tuple[BitMatrix, list[int]]:
    """Reduced row echelon form.  Returns the matrix and its pivot columns.

    Fully vectorised: eliminating a pivot column XORs the pivot row into every
    other row that has a 1 there, in one numpy operation.
    """
    work = m if inplace else m.copy()
    words = work.words
    nrows = work.nrows
    pivot_row = 0
    pivots: list[int] = []

    for col in range(work.ncols):
        if pivot_row >= nrows:
            break
        w, mask = _col_mask(col)
        has_one = (words[pivot_row:, w] & mask) != 0
        if not has_one.any():
            continue
        src = pivot_row + int(np.argmax(has_one))
        if src != pivot_row:
            words[[pivot_row, src]] = words[[src, pivot_row]]
        targets = (words[:, w] & mask) != 0
        targets[pivot_row] = False
        if targets.any():
            words[targets] ^= words[pivot_row]
        pivots.append(col)
        pivot_row += 1

    return work, pivots


def rank(m: BitMatrix | np.ndarray, ncols: int | None = None) -> int:
    """Rank over GF(2)."""
    if not isinstance(m, BitMatrix):
        m = BitMatrix.from_bits(m) if ncols is None else BitMatrix(np.asarray(m, np.uint64), ncols)
    _, pivots = rref(m)
    return len(pivots)


def nullspace(m: BitMatrix) -> np.ndarray:
    """Basis of ``{h : M h^T = 0}``, returned as a 0/1 array of shape (d, ncols).

    When the rows of ``M`` are received codewords, this basis **is the set of
    parity checks that hold on the stream** - the dual code.  Its dimension is
    ``ncols - rank``, so a rank deficiency is exactly the signature of an
    underlying linear code (and of any interleaver composed with it).
    """
    reduced, pivots = rref(m)
    bits = reduced.to_bits()
    ncols = m.ncols
    pivot_set = set(pivots)
    free = [c for c in range(ncols) if c not in pivot_set]

    basis = np.zeros((len(free), ncols), dtype=np.uint8)
    for i, fc in enumerate(free):
        basis[i, fc] = 1
        for r, pc in enumerate(pivots):
            if bits[r, fc]:
                basis[i, pc] = 1
    return basis


def row_space(m: BitMatrix) -> np.ndarray:
    """A basis for the row space, as a 0/1 array."""
    reduced, pivots = rref(m)
    return reduced.to_bits()[: len(pivots)]


def syndrome(codewords: np.ndarray, checks: np.ndarray) -> np.ndarray:
    """Evaluate parity checks on hard bits.

    ``codewords`` is (N, n), ``checks`` is (m, n).  Returns (N, m) of 0/1, where
    0 means the check was satisfied.  For a true codeword every entry is 0.
    """
    cw = np.asarray(codewords, dtype=np.uint8)
    h = np.asarray(checks, dtype=np.uint8)
    return (cw @ h.T) & 1


def is_codeword(codewords: np.ndarray, checks: np.ndarray) -> np.ndarray:
    return syndrome(codewords, checks).sum(axis=1) == 0


def rank_profile(bits: np.ndarray, n: int, max_rows: int = 4096) -> tuple[int, int]:
    """Reshape a stream into rows of length `n` and report ``(rows, rank)``.

    The core measurement of L6 track B.  If the stream is a sequence of
    codewords of an (n, k) linear code and the row length `n` is guessed
    correctly *and* the phase is aligned, the rank saturates at `k < n`.  A wrong
    `n` gives a full-rank matrix.  **Rank deficiency is the detection.**
    """
    bits = np.asarray(bits, dtype=np.uint8)
    nrows = min(len(bits) // n, max_rows)
    if nrows < 2:
        return 0, 0
    m = BitMatrix.from_bits(bits[: nrows * n].reshape(nrows, n))
    return nrows, rank(m)
