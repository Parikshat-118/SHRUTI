"""Per-column entropy profiling: the header/payload segmentation, automatically.

The central observation behind frame-structure recovery, and it needs no
machine learning:

    Fold the bitstream into a matrix at the frame length and take the entropy of
    each column.  Low-entropy columns are sync words, addresses, static fields
    and padding.  High-entropy columns are payload.  **That profile IS the
    segmentation**, and it plots as a single readable figure.

Field typing then falls out of the same matrix: columns that increment are
counters, columns constant within a transmission but varying between them are
addresses, and a trailing block at near-perfect 1.0 bit/bit entropy is encrypted
or compressed - which, stated with a measured number attached, is a genuine
intelligence product rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..core.bits import column_entropy, from_bits

__all__ = ["FieldType", "Field", "FieldMap", "profile_fields", "segment_header_payload"]


class FieldType(str, Enum):
    SYNC = "sync"
    CONSTANT = "constant"
    COUNTER = "counter"
    ADDRESS = "address"
    PAYLOAD = "payload"
    PADDING = "padding"
    ENCRYPTED = "encrypted_or_compressed"
    UNKNOWN = "unknown"


@dataclass
class Field:
    """One contiguous run of columns sharing a character."""

    start: int
    length: int
    kind: FieldType
    entropy: float
    note: str = ""

    @property
    def end(self) -> int:
        return self.start + self.length

    def describe(self) -> str:
        return (
            f"bits {self.start:5d}-{self.end-1:5d} ({self.length:4d}) "
            f"{self.kind.value:24s} H={self.entropy:.3f}  {self.note}"
        )


@dataclass
class FieldMap:
    """The recovered frame layout."""

    period_bits: int
    entropy: np.ndarray
    fields: list[Field] = field(default_factory=list)
    header_bits: int = 0
    payload_bits: int = 0
    payload_entropy: float = 0.0
    n_frames: int = 0
    all_constant: bool = False
    note: str = ""

    @property
    def looks_encrypted(self) -> bool:
        """A payload at ~1.0 bit/bit is encrypted or compressed, not merely coded."""
        return self.payload_entropy > 0.98

    def summary(self) -> str:
        if self.all_constant:
            return f"repetitive content, period {self.period_bits} bits - {self.note}"
        s = (
            f"frame {self.period_bits} bits = header {self.header_bits} + "
            f"payload {self.payload_bits}, payload entropy "
            f"{self.payload_entropy:.4f} bit/bit"
        )
        if self.looks_encrypted:
            s += "  -> consistent with ENCRYPTED or COMPRESSED payload"
        return s

    def table(self) -> str:
        return "\n".join(f.describe() for f in self.fields)


def profile_fields(
    bits: np.ndarray,
    period: int,
    low_entropy: float = 0.35,
    high_entropy: float = 0.90,
) -> FieldMap:
    """Classify every column of the folded frame."""
    b = np.asarray(bits, dtype=np.uint8).reshape(-1)
    nframes = len(b) // period
    ent = column_entropy(b, period)
    fm = FieldMap(period_bits=period, entropy=ent, n_frames=nframes)
    if nframes < 3:
        return fm

    m = b[: nframes * period].reshape(nframes, period)

    kinds: list[FieldType] = []
    for c in range(period):
        col = m[:, c]
        h = float(ent[c])
        if h < 0.05:
            kinds.append(FieldType.CONSTANT)
        elif h < low_entropy:
            kinds.append(FieldType.ADDRESS)
        elif h > high_entropy:
            kinds.append(FieldType.PAYLOAD)
        else:
            kinds.append(FieldType.UNKNOWN)

    # Smooth isolated misclassifications before merging.  Per-column entropy from
    # a few dozen frames is noisy, so single columns flip category at random and
    # fragment what is really one field into a dozen one-bit slivers.  A field
    # map nobody can read is not a segmentation.
    if period >= 8:
        smoothed = list(kinds)
        for c in range(1, period - 1):
            if kinds[c] != kinds[c - 1] and kinds[c - 1] == kinds[c + 1]:
                smoothed[c] = kinds[c - 1]
        kinds = smoothed

    # Merge runs of like columns into fields.
    runs: list[Field] = []
    start = 0
    for c in range(1, period + 1):
        if c == period or kinds[c] != kinds[start]:
            seg = ent[start:c]
            runs.append(
                Field(
                    start=start,
                    length=c - start,
                    kind=kinds[start],
                    entropy=float(np.mean(seg)) if len(seg) else 0.0,
                )
            )
            start = c

    # Refine: a long constant run at the head is the sync marker; a monotonically
    # incrementing multi-bit field is a counter.
    for i, f in enumerate(runs):
        if f.kind is FieldType.CONSTANT and f.start < period * 0.25 and f.length >= 8:
            f.kind = FieldType.SYNC
            f.note = "constant at frame head - sync marker"
        elif f.kind is FieldType.CONSTANT and f.start > period * 0.75:
            f.kind = FieldType.PADDING
            f.note = "constant at frame tail - padding"
        elif f.kind in (FieldType.ADDRESS, FieldType.UNKNOWN) and 4 <= f.length <= 32:
            vals = from_bits(m[:, f.start : f.end].reshape(-1), f.length)
            if len(vals) > 3:
                d = np.diff(vals.astype(np.int64))
                if np.all(d == d[0]) and d[0] != 0:
                    f.kind = FieldType.COUNTER
                    f.note = f"increments by {int(d[0])} per frame - sequence number"
                elif f.kind is FieldType.ADDRESS:
                    f.note = "low entropy, varies between transmissions - address or ID"
        if f.kind is FieldType.PAYLOAD and f.entropy > 0.98:
            f.kind = FieldType.ENCRYPTED
            f.note = f"{f.entropy:.4f} bit/bit - encrypted or compressed"

    fm.fields = runs
    payload_kinds = (FieldType.PAYLOAD, FieldType.ENCRYPTED)
    fm.payload_bits = sum(f.length for f in runs if f.kind in payload_kinds)
    fm.header_bits = period - fm.payload_bits
    pay = [f for f in runs if f.kind in payload_kinds]
    fm.payload_entropy = (
        float(np.average([f.entropy for f in pay], weights=[f.length for f in pay]))
        if pay else 0.0
    )

    # If *every* column is constant, the detected period is the repeat length of
    # the content itself, not a frame with a header.  Saying "header 216 bits,
    # payload 0" there would be a confident wrong answer; the honest reading is
    # that the transmission is repetitive - an idle pattern, a test loop, or a
    # beacon - which is itself a finding worth reporting.
    if fm.payload_bits == 0 and float(np.mean(ent)) < 0.05:
        fm.all_constant = True
        fm.note = (
            f"every bit position is constant across all {nframes} repetitions: the "
            f"{period}-bit period is the repeat length of the content itself, not a "
            "frame header. Consistent with an idle pattern, test loop or beacon"
        )
    return fm


def segment_header_payload(bits: np.ndarray, period: int) -> tuple[int, FieldMap]:
    """Return the header/payload boundary and the full field map.

    The boundary is taken as the end of the last low-entropy field before the
    first sustained high-entropy region - which is how a protocol is actually
    laid out, and why this works without knowing the protocol.
    """
    fm = profile_fields(bits, period)
    boundary = 0
    for f in fm.fields:
        if f.kind in (FieldType.PAYLOAD, FieldType.ENCRYPTED) and f.length >= 16:
            boundary = f.start
            break
    return boundary, fm
