"""L4 - the differentiable twin: a parameterised generative model of a radio link.

This is the project.  Everything else either feeds it or reads its output.

The twin renders a waveform from a parameter vector:

    bits -> FEC -> interleave -> scramble -> map -> pulse-shape -> channel -> samples

and the *same* model, run in reverse as an inverse problem, is how SHRUTI
analyses an unknown capture.  Two consequences that no classifier-based design
can reach:

1. **Verification by resynthesis.**  Re-encode what was recovered, re-render the
   waveform, and measure the difference against the original samples.  When that
   difference is noise, the analysis is not *confident* - it is demonstrated.
2. **The test oracle.**  Every parameter SHRUTI is asked to recover is an input
   to the synthesiser, so property-based tests draw a random configuration,
   render it, analyse it, and assert the recovered values fall inside their own
   stated error bars.  Millions of labelled cases, no annotation effort.

The twin also settles the question of *"the spectral relationship from
training data containing both .IQ and .wav formats"* by construction: the `.IQ`
view and the `.wav` SSB-audio view are **rendered from one parameter set**,
because an SSB receiver is just another block in the chain (see `ssb.py`).
"""

from __future__ import annotations

__all__ = ["modulation", "shaping", "channel", "chain"]
