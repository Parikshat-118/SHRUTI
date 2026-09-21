"""L6 - interleaver and FEC reconstruction.

Contains both directions, deliberately:

* **Encoders / interleavers / scramblers** - used by the L4 twin to *synthesise*
  a candidate waveform.  These are the forward model.
* **Decoders and blind reconstruction** - used to *analyse* an unknown capture.

Having both in one package is what makes verification-by-resynthesis possible:
the same code object that decoded the stream re-encodes it, and the twin rebuilds
the waveform for comparison against the original samples.

Three reconstruction tracks (see `match.py`, `algebraic.py`, `syndrome.py`):

    A  library match      - test against known cartridge specs.  Fast, decisive.
    B  algebraic          - rank-deficiency and dual-code search on hard bits.
    C  soft-syndrome      - binomial test on soft bits.  Extends B down in SNR
                            and yields a p-value instead of a threshold.
"""

from __future__ import annotations

__all__ = ["conv", "rs", "ldpc", "interleave", "scramble"]
