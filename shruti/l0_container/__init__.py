"""L0 - container and format inference.  Everything starts with the container.

    *"The data saved as .IQ and .wav have different parameters and therefore they
    store the raw information in different format. These files have to be
    processed in different ways for signal analysis."*

SHRUTI infers everything and **asks for nothing**.  Every competing tool opens
with a dialogue requesting sample rate, data type and centre frequency; refusing
to is a visible, demonstrable differentiator in the first ten seconds.

Three things this layer gets right that are easy to get wrong:

1. **A .wav file is not automatically IQ.**  An HF `.wav` is usually the *real
   audio output of an SSB receiver* - one channel, 300-3400 Hz of modem, no
   complex baseband and no RF centre frequency at all.  Two-channel files may be
   true stereo audio *or* I-in-left/Q-in-right.  Hermitian symmetry and
   inter-channel correlation settle which.

2. **Absolute sample rate is not identifiable from a headerless file.**  Every
   measurable quantity is a ratio.  SHRUTI says so, then resolves it from
   sidecars, filename conventions, or in-band anchors - and reports which.

3. **Files larger than RAM are normal, not an error.**  Everything is memory
   mapped.
"""

from __future__ import annotations

from .sniff import (
    Capture,
    ContainerInfo,
    load,
    load_iq,
    load_wav,
    infer_dtype,
    DTYPES,
)
from .filename import parse_filename
from .sigmf_io import read_sigmf, write_sigmf

__all__ = [
    "Capture",
    "ContainerInfo",
    "load",
    "load_iq",
    "load_wav",
    "infer_dtype",
    "parse_filename",
    "read_sigmf",
    "write_sigmf",
    "DTYPES",
]
