"""L2 - wideband detection and emitter tracking.

Input bandwidth can run from a few kHz to GHz, so detection has to work on a whole
file rather than on a pre-channelised burst.  Two choices matter:

* **OS-CFAR, not a fixed threshold.**  An ordered statistic is robust when
  *other emitters* sit in the training cells, which in a wideband capture is the
  normal case rather than the exception.  A magic threshold would have to be
  retuned for every band, and would quietly fail on the crowded ones.
* **Segments, not peaks.**  An emitter occupies a band, so detections are merged
  into contiguous regions with a measured bandwidth and centre - which is what
  the analyst actually wants and what L3 needs to propose against.
"""

from __future__ import annotations

from .detect import Detection, detect_emitters, occupancy

__all__ = ["Detection", "detect_emitters", "occupancy"]
