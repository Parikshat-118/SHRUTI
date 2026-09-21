"""Bit-array utilities shared by L5 (soft demod), L6 (FEC) and L7 (bitstream).

Two representations are used throughout SHRUTI and it matters which is which:

* **hard bits**  - ``np.uint8`` array of 0/1.  What an encoder emits.
* **soft bits**  - ``np.float64`` array of log-likelihood ratios, LLR = log P(b=0)/P(b=1).
  Positive LLR means the bit is probably 0.  What L5 emits and what L6 wants:
  every blind-reconstruction track in L6 works dramatically better on soft
  information, and that single choice is where most teams lose their FEC stage.

The sign convention is stated once here because getting it backwards is the
classic silent bug: **LLR > 0 ⇒ bit 0**.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "to_bits",
    "from_bits",
    "bytes_to_bits",
    "bits_to_bytes",
    "hard_decision",
    "llr_from_hard",
    "xor_parity",
    "hamming_distance",
    "shannon_entropy",
    "column_entropy",
    "bit_autocorrelation",
    "text_to_bits",
    "bits_to_text",
]


def to_bits(values: np.ndarray, width: int, msb_first: bool = True) -> np.ndarray:
    """Expand integers to their `width`-bit representations, flattened."""
    values = np.asarray(values, dtype=np.uint64)
    shifts = np.arange(width - 1, -1, -1) if msb_first else np.arange(width)
    bits = (values[:, None] >> shifts[None, :].astype(np.uint64)) & np.uint64(1)
    return bits.astype(np.uint8).reshape(-1)


def from_bits(bits: np.ndarray, width: int, msb_first: bool = True) -> np.ndarray:
    """Inverse of :func:`to_bits`.  Trailing partial groups are discarded."""
    bits = np.asarray(bits, dtype=np.uint8)
    n = (len(bits) // width) * width
    grouped = bits[:n].reshape(-1, width).astype(np.uint64)
    shifts = np.arange(width - 1, -1, -1) if msb_first else np.arange(width)
    return (grouped << shifts[None, :].astype(np.uint64)).sum(axis=1)


def bytes_to_bits(data: bytes | np.ndarray, msb_first: bool = True) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8) if isinstance(data, bytes) else np.asarray(data, np.uint8)
    out = np.unpackbits(arr, bitorder="big" if msb_first else "little")
    return out.astype(np.uint8)


def bits_to_bytes(bits: np.ndarray, msb_first: bool = True) -> bytes:
    bits = np.asarray(bits, dtype=np.uint8)
    pad = (-len(bits)) % 8
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, np.uint8)])
    return np.packbits(bits, bitorder="big" if msb_first else "little").tobytes()


def hard_decision(llr: np.ndarray) -> np.ndarray:
    """LLR -> hard bits.  Positive LLR means bit 0 (see module docstring)."""
    return (np.asarray(llr) < 0).astype(np.uint8)


def llr_from_hard(bits: np.ndarray, magnitude: float = 8.0) -> np.ndarray:
    """Hard bits -> saturated LLRs, for feeding hard data to a soft algorithm."""
    bits = np.asarray(bits, dtype=np.uint8)
    return np.where(bits == 0, magnitude, -magnitude).astype(np.float64)


def xor_parity(bits: np.ndarray, axis: int | None = None) -> np.ndarray:
    """Parity (XOR reduction) over GF(2)."""
    return np.bitwise_xor.reduce(np.asarray(bits, dtype=np.uint8), axis=axis)


def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(np.asarray(a, np.uint8) ^ np.asarray(b, np.uint8)))


def shannon_entropy(bits: np.ndarray) -> float:
    """Entropy in bits per bit.  1.0 means indistinguishable from a fair coin."""
    bits = np.asarray(bits, dtype=np.uint8)
    if bits.size == 0:
        return 0.0
    p = float(np.count_nonzero(bits)) / bits.size
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p)))


def column_entropy(bits: np.ndarray, period: int) -> np.ndarray:
    """Fold a stream to `period` columns and return per-column entropy.

    This is the whole of L7 step 2 in one function.  Low-entropy columns are
    sync words, addresses, static fields and padding; high-entropy columns are
    payload.  **The entropy profile across one frame is the header/payload
    segmentation**, produced automatically.
    """
    bits = np.asarray(bits, dtype=np.uint8)
    nrows = len(bits) // period
    if nrows < 2:
        return np.full(period, np.nan)
    m = bits[: nrows * period].reshape(nrows, period)
    p = m.mean(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        h = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))
    return np.nan_to_num(h, nan=0.0)


def bit_autocorrelation(bits: np.ndarray, max_lag: int, min_lag: int = 1) -> np.ndarray:
    """Normalised agreement of the stream with itself at each lag.

    A periodic sync word produces a comb of peaks; the comb spacing is the frame
    period.  Returned values are in [-1, 1]; 0 means "no better than chance".
    """
    bits = np.asarray(bits, dtype=np.int8)
    sym = 1 - 2 * bits.astype(np.int16)  # 0 -> +1, 1 -> -1
    n = len(sym)
    max_lag = min(max_lag, n - 1)
    out = np.zeros(max_lag - min_lag + 1)
    for i, lag in enumerate(range(min_lag, max_lag + 1)):
        overlap = n - lag
        if overlap < 32:
            break
        out[i] = float(np.dot(sym[:overlap], sym[lag:])) / overlap
    return out


def text_to_bits(text: str) -> np.ndarray:
    """UTF-8 text -> bits.  Used by the blind self-test."""
    return bytes_to_bits(text.encode("utf-8"))


def bits_to_text(bits: np.ndarray, errors: str = "replace") -> str:
    return bits_to_bytes(bits).decode("utf-8", errors=errors)
