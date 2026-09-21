"""SHRUTI - blind RF exploitation, samples to bits.

`sruti` (श्रुति) - that which is heard.  `artha` (अर्थ) - its meaning.

SHRUTI analyses an unlabelled .IQ / .wav capture by working out how to *rebuild*
it, rebuilding it, and measuring the difference against the original samples.
The error-correcting code is treated as a measuring instrument rather than an
obstacle: if every upstream estimate is right the code decodes, and the decoded
message is the proof that the measurements were correct.

Layer map (see docs/ARCHITECTURE.md):

    L0  container + format inference         shruti.l0_container
    L1  receiver self-model                  shruti.l1_receiver
    L2  wideband detection + tracking        shruti.l2_detect
    L3  proposal short-list                  shruti.l3_proposals
    L4  twin: forward synthesis + inversion  shruti.l4_twin
    L4b iterative emitter peeling            shruti.l4b_peel
    L5  soft demodulation + descrambling     shruti.l5_demod
    L6  interleaver + FEC reconstruction     shruti.l6_fec
    L7  bitstream structure + correlation    shruti.l7_bits
    L8  report, SigMF, attestation, GUI      shruti.l8_report / shruti.web

Licence: Apache-2.0.  No GPL code is linked (see NOTICE).
"""

__version__ = "2.0.0"
__all__ = ["__version__"]
