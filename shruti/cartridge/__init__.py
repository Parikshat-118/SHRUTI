"""Waveform cartridges - a waveform is **data**, not code.

A cartridge is a ~40-line YAML file describing a transmitter chain and the prior
ranges of its parameters.  One file, and every layer picks it up at once with no
code written:

======================  ====================================================
Layer                   What it gets from the cartridge, for free
======================  ====================================================
Twin (L4)               a forward model it can synthesise and differentiate
Proposals (L3)          labelled training data, on demand, .IQ *and* .wav
Standards lattice       a point in the lattice, with tolerances
Library match (L6/A)    a parity-check matrix and interleaver spec to test
Signature report        "consistent with MIL-STD-188-110A" not "8-PSK"
Capability envelope     bits required and SNR floor, measured not guessed
======================  ====================================================

Three consequences, and they are what makes the library worth having:

1. **Extending the tool stops being a software task.**  An analyst who has read
   a modem's specification can add it - no Python, no rebuild, no release cycle.
2. **It draws the open/classified line where a government needs it.**  The engine
   is Apache-2.0; the cartridge library is data and can be tiered - public for
   civil standards, restricted for sensitive material, classified and never
   shipped.  An agency can extend the tool with material it can never show you,
   without forking the code.
3. **Maintenance cost collapses.**  The long tail of a decoder suite is waveform
   coverage, not engineering.  Moving coverage into data means the project
   survives its authors.

Prior art, named honestly: declarative *format* description is well established
(Kaitai Struct; Tektronix's protocol-description patents).  What is different
here is the **direction** - those describe a known format so a parser can read
it; a cartridge describes a candidate waveform so a *generator* can synthesise
it, and the synthesis is then inverted against an unknown capture.
"""

from __future__ import annotations

from .schema import Cartridge, CartridgeError, parse_int
from .loader import load_cartridge, load_library, CartridgeLibrary

__all__ = [
    "Cartridge",
    "CartridgeError",
    "CartridgeLibrary",
    "load_cartridge",
    "load_library",
    "parse_int",
]
