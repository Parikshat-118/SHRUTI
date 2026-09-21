"""L7 - bitstream structure and correlation.

    *"Bit stream correlation"* ... *"carry out correlation of bit stream for
    identification of header and payload."*

The cheapest of the five requirements to satisfy well, and the one most teams
will never reach - because reaching it requires having succeeded at (ii), (iii)
and (iv) first.  There is no shortcut to it and no partial-credit version.

Four steps, all classical, all cheap once bits exist:

1. **Frame period detection** - autocorrelate the stream; a periodic sync word
   produces a comb of peaks whose spacing is the frame length.
2. **Reshape and profile** - fold at the frame length and take per-column
   entropy.  Low-entropy columns are sync words, addresses, static fields and
   padding; high-entropy columns are payload.  **The entropy profile across one
   frame IS the header/payload segmentation**, produced automatically.
3. **Field typing** - monotonic columns are counters; columns constant within a
   transmission but varying between them are addresses; a trailing block at
   ~1.0 bit/bit entropy is encrypted or compressed, and saying which with a
   measured number attached is a genuine intelligence product.
4. **Cross-capture correlation** - matching streams across two sensors prove a
   common transmission; matching headers across time prove network membership.
"""

from __future__ import annotations

from .frame import FrameAnalysis, find_sync_word, detect_frame_period, analyse_frames
from .fields import FieldMap, FieldType, profile_fields, segment_header_payload
from .correlate import cross_correlate_streams, StreamMatch

__all__ = [
    "FrameAnalysis",
    "find_sync_word",
    "detect_frame_period",
    "analyse_frames",
    "FieldMap",
    "FieldType",
    "profile_fields",
    "segment_header_payload",
    "cross_correlate_streams",
    "StreamMatch",
]
