"""L5 - soft demodulation and descrambling.

Demodulation is the hinge of the whole chain.  Two design choices here
decide whether the rest of the chain works:

1. **Soft output, not hard.**  L5 emits per-bit log-likelihood ratios.  Every
   blind reconstruction track in L6 works dramatically better on soft
   information, and rank-based methods on hard bits degrade fast with errors.
   This single choice is where most teams will lose their FEC stage.

2. **Ambiguities are enumerated, not guessed.**  Phase rotation by a
   constellation symmetry, differential vs absolute encoding, bit order, and
   spectral inversion are all one-bit or small-cardinality hypotheses.  SHRUTI
   resolves every one of them the same way: **by which one lets the code
   decode.**  Where a conventional tool needs a human to flip a switch and
   listen, this is a binomial test.
"""

from __future__ import annotations

from .sync import (
    estimate_cfo_mth_power,
    estimate_symbol_rate,
    oerder_meyr_timing,
    timing_recover,
)
from .demod import DemodResult, demodulate, soft_demodulate, AMBIGUITIES

__all__ = [
    "estimate_cfo_mth_power",
    "estimate_symbol_rate",
    "oerder_meyr_timing",
    "timing_recover",
    "demodulate",
    "soft_demodulate",
    "DemodResult",
    "AMBIGUITIES",
]
