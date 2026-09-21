"""Cross-capture bitstream correlation - traffic analysis, for free.

The phrase *"bit stream correlation"* supports a second reading worth
taking: correlate recovered bitstreams **between** captures.

* Matching streams across two sensors prove a **common transmission**.
* Matching headers across time prove **network membership or retransmission**.
* A bit-identical payload seen twice is a **replay**, not a live transmission.

This needs no new machinery and it is what an agency sitting on an archive
actually wants.  It also gets strictly better the more files exist, which makes
it a natural pitch to someone who already owns years of unanalysed captures.

Parameter agreement between two captures is *suggestive*.  **Bit agreement is
proof.**  That distinction is the whole value of reaching the bit layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["StreamMatch", "cross_correlate_streams", "best_alignment"]


@dataclass
class StreamMatch:
    """Evidence that two recovered bitstreams came from the same transmission."""

    offset: int
    overlap_bits: int
    agreement: float
    p_value: float
    verdict: str = ""

    @property
    def is_match(self) -> bool:
        return self.agreement > 0.9 and self.overlap_bits >= 256

    def summary(self) -> str:
        return (
            f"offset {self.offset:+d}, {self.overlap_bits} bits overlap, "
            f"{self.agreement*100:.1f}% agreement (p={self.p_value:.2e}) - {self.verdict}"
        )


def best_alignment(a: np.ndarray, b: np.ndarray, max_offset: int = 4096) -> tuple[int, float, int]:
    """Slide `b` against `a` and return ``(offset, agreement, overlap)``.

    Uses an FFT cross-correlation on the +/-1 mapped streams, which makes a
    full-range search over megabit streams a second rather than an afternoon.
    """
    x = 1.0 - 2.0 * np.asarray(a, dtype=np.float64)
    y = 1.0 - 2.0 * np.asarray(b, dtype=np.float64)
    if len(x) < 8 or len(y) < 8:
        return 0, 0.0, 0

    n = 1 << int(np.ceil(np.log2(len(x) + len(y))))
    corr = np.fft.irfft(np.fft.rfft(x, n) * np.conj(np.fft.rfft(y, n)), n)

    lags = np.arange(-len(y) + 1, len(x))
    full = np.concatenate([corr[-(len(y) - 1):], corr[: len(x)]])
    keep = np.abs(lags) <= max_offset
    if not keep.any():
        return 0, 0.0, 0

    sub_l, sub_c = lags[keep], full[keep]
    k = int(np.argmax(np.abs(sub_c)))
    off = int(sub_l[k])

    a0, b0 = (off, 0) if off >= 0 else (0, -off)
    overlap = min(len(x) - a0, len(y) - b0)
    if overlap <= 0:
        return off, 0.0, 0
    agree = float(np.mean(
        np.asarray(a[a0 : a0 + overlap], np.uint8)
        == np.asarray(b[b0 : b0 + overlap], np.uint8)
    ))
    return off, agree, overlap


def cross_correlate_streams(
    a: np.ndarray, b: np.ndarray, max_offset: int = 4096
) -> StreamMatch:
    """Test whether two bitstreams are the same transmission.

    The null hypothesis is that the two streams are independent, under which
    agreement is Binomial(n, 0.5).  Over thousands of bits, a real match produces
    a p-value small enough to state without hedging - which is what makes bit
    agreement *proof* rather than a suggestion.
    """
    from ..core.stats import binomial_bias_test

    off, agree, overlap = best_alignment(a, b, max_offset)
    if overlap < 64:
        return StreamMatch(off, overlap, agree, 1.0, "insufficient overlap to decide")

    p = binomial_bias_test(int(round(agree * overlap)), overlap, 0.5)
    if agree > 0.99:
        verdict = "bit-identical: same transmission, or a replay"
    elif agree > 0.9:
        verdict = "same transmission, recovered with errors"
    elif agree > 0.6:
        verdict = "partial agreement - possibly shared header, different payload"
    else:
        verdict = "no evidence of a common transmission"
    return StreamMatch(off, overlap, agree, p, verdict)
