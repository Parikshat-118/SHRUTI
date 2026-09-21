"""L4b - iterative emitter peeling.  Only a tool that can SYNTHESISE can do this.

    1. Fit and invert the strongest emitter.
    2. Subtract its reconstruction from the observed samples.
    3. Re-run detection on the residual.
    4. Repeat until the residual passes a whiteness test.

This is CLEAN from radio astronomy and successive interference cancellation from
communications, applied to blind analysis.  It recovers **weak emitters buried
under strong ones, and signals overlapping in both time and frequency** - the
case that arises whenever the input is a whole recording rather than
pre-channelised bursts.

**It is structurally unavailable to a classifier-based design.**  You cannot
subtract a label; you can only subtract a reconstruction, and producing a
reconstruction requires a generative model of the whole chain.

It also makes a compelling live visual: the spectrogram getting quieter one
emitter at a time until only noise is left.
"""

from __future__ import annotations

from .peel import PeelStage, PeelResult, peel

__all__ = ["PeelStage", "PeelResult", "peel"]
