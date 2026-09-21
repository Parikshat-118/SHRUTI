"""L1 - receiver self-model: telling the sensor's own artefacts from real emitters.

The obvious way to model a receiver's signature is to record with the input
terminated and fit the result.  **For files that arrive from different sensors
and different locations - i.e. every real file - you will never have one.**

So all five tests here are **reference-free**.  They need no calibration
capture, no hardware access, and no cooperation from whoever made the recording.

======================  ===============================================
Test                    Catches
======================  ===============================================
DC / LO self-mix        DC spike, local-oscillator leakage
Conjugate correlation   I/Q imbalance images - and *estimates* the
                        imbalance, so it can be corrected blindly
Spacing GCD             spur combs, ADC harmonics
Superlinear scaling     front-end nonlinearity products
Cross-file consistency  all of the above, retroactively, over an archive
======================  ===============================================

The last one needs no extra hardware and gets **stronger the more files you
process**, which makes it a natural fit for an agency already sitting on years
of captures: a feature at the same *baseband* offset across many files,
regardless of where the receiver was tuned, is the receiver.  An emitter would
have moved with the tuning.
"""

from __future__ import annotations

from .artefacts import (
    ArtefactReport,
    ArtefactFinding,
    analyse_artefacts,
    conjugate_correlation,
    correct_iq_imbalance,
    cross_file_consistency,
)

__all__ = [
    "ArtefactReport",
    "ArtefactFinding",
    "analyse_artefacts",
    "conjugate_correlation",
    "correct_iq_imbalance",
    "cross_file_consistency",
]
