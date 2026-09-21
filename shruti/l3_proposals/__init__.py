"""L3 - proposal short-list: narrow the hypothesis space before the expensive part.

Brute-forcing every cartridge against every ambiguity hypothesis is O(library x
ambiguities) full decodes, which does not scale past a toy library and wastes
effort on cartridges whose symbol rate is off by an order of magnitude.

L3 measures the cheap physical-layer quantities first - symbol rate, occupied
bandwidth, SNR, modulation family - and uses them to shortlist.  Only survivors
reach L6.

**The neural network belongs here, and it is eleventh of twelve in the build
order.**  A classical estimator does this job well, it is explainable, and it
needs no training data.  The net is a speed optimisation, not a capability, and
saying so out loud is worth more than shipping it.
"""

from __future__ import annotations

from .classical import Proposal, propose, shortlist_cartridges

__all__ = ["Proposal", "propose", "shortlist_cartridges"]
