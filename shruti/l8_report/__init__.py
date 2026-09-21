"""L8 - reporting, SigMF output and the attestation bundle.

The resynthesis thesis has a corollary that is worth more to a government than
to anyone else: **if an analysis is verified by rebuilding the waveform, then
the verification is portable.**  Ship the recipe and anyone can re-run it.

    shruti verify report.shruti-attest.zip
    -> re-synthesises the waveform from the recorded parameters
    -> recomputes the residual against the original capture
    -> PASS: residual reproduces; goodness-of-fit p = 0.31; 4 cartridges verified

Why that matters here specifically:

* **A finding becomes transferable.**  Agency B does not have to trust Agency
  A's analyst, or Agency A's build.  It re-runs the bundle.
* **It is a chain of custody for RF intelligence.**  Immutable input hash,
  pinned engine version, recorded seeds, deterministic output.  The question
  that follows any technical finding into a briefing - *"how do we know?"* -
  gets a command-line answer.
* **Regression testing becomes free.**  Every archived bundle is a test case, so
  historical conclusions are re-verified on every commit.  This is also, quietly,
  how the project stays correct after its authors have graduated.

> Every other tool gives you an answer.  This one gives you an answer and the
> receipt - and the receipt re-runs.
"""

from __future__ import annotations

from .attest import (
    AttestationBundle,
    VerifyResult,
    create_bundle,
    verify_bundle,
)

__all__ = ["AttestationBundle", "VerifyResult", "create_bundle", "verify_bundle"]
