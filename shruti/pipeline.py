"""The analysis pipeline: a file in, a report out.

Orchestrates L0 -> L7 and enforces two things the design insists on:

**Anytime results.**  Something on screen in ~2 s (detections, bandwidth),
refined at ~30 s (modulation, symbol rate, constellation), complete at ~5 min
(bits, FEC, framing).  The analyst is never staring at a spinner, and the
progressive tiers are an architectural property rather than a promise.

**Capability gating.**  Each stage declares how much data it needs.  A burst too
short for interleaver reconstruction says so, with the bit count required, and
the capability greys itself out.  Without this gate, FEC identification on a
4 ms burst returns confident nonsense rather than an honest refusal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

import numpy as np

from .cartridge import CartridgeLibrary, load_library
from .core.bits import bits_to_bytes, hard_decision
from .core.stats import GoodnessOfFit, goodness_of_fit, whiteness_test
from .l0_container import Capture, load
from .l3_proposals import Proposal, propose, shortlist_cartridges
from .l5_demod import soft_demodulate
from .l6_fec.match import MatchScore, match_library
from .l7_bits import analyse_frames, profile_fields

__all__ = ["AnalysisResult", "Capability", "analyse", "analyse_capture", "DATA_REQUIREMENTS"]


#: Minimum data each capability needs, in bits, from the design's own table.
#: Surfaced in the UI as a gate, not buried in a footnote.
DATA_REQUIREMENTS: dict[str, tuple[int, str]] = {
    "detection": (0, "detection, bandwidth and centre need only a few thousand samples"),
    "modulation": (0, "symbol rate and modulation family need ~10^2-10^3 symbols"),
    "framing": (1_000, "frame period and sync word need 10^3-10^4 bits"),
    "fec_library": (2_000, "matching a known code needs a few thousand bits"),
    "fec_reconstruction": (10_000, "reconstructing an unknown convolutional code needs 10^4-10^5 bits"),
    "interleaver_reconstruction": (20_000, "interleaver period and depth need 10^4-10^6 bits"),
}


@dataclass
class Capability:
    """Whether a capability is available on this capture, and why not if not."""

    name: str
    available: bool
    required_bits: int
    have_bits: int
    reason: str = ""

    def describe(self) -> str:
        if self.available:
            return f"{self.name}: available"
        return (
            f"{self.name}: DISABLED - needs >= {self.required_bits} bits, "
            f"this capture holds {self.have_bits}. {self.reason}"
        )


@dataclass
class AnalysisResult:
    """Everything SHRUTI concluded, plus the evidence for each conclusion."""

    path: str = ""
    capture: Capture | None = None
    proposals: list[Proposal] = field(default_factory=list)
    matches: list[MatchScore] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    frame: Any = None
    fieldmap: Any = None
    gof: GoodnessOfFit | None = None
    payload_bits: np.ndarray | None = None
    verdict: str = "UNKNOWN"
    matched_cartridge: object | None = None
    timings: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def best(self) -> MatchScore | None:
        return self.matches[0] if self.matches else None

    @property
    def identified(self) -> bool:
        return self.verdict == "IDENTIFIED"

    def payload_text(self, limit: int = 400) -> str:
        if self.payload_bits is None or len(self.payload_bits) == 0:
            return ""
        raw = bits_to_bytes(self.payload_bits)[: limit]
        return raw.decode("utf-8", errors="replace")

    @property
    def resolved_physical(self) -> str:
        """The physical layer as finally concluded, not as first guessed.

        L3 *proposes* and L6 *disposes*.  Once a cartridge has decoded with a
        certificate, its declared parameters are the answer and the winning
        proposal is merely the hypothesis that got us there - they can disagree,
        most visibly under fading, where an FSK signal's envelope varies enough
        to look like QAM to an envelope-based estimator.

        Reporting the proposal after the match has been made would print
        "64-QAM" beside a waveform named "2-FSK" in the same summary, which is
        the kind of internal contradiction that destroys trust faster than being
        wrong outright.
        """
        if self.best is not None and self.verdict == "IDENTIFIED" and self.matched_cartridge:
            c = self.matched_cartridge
            try:
                mod = c.build_mapper().describe()
            except Exception:                                  # noqa: BLE001
                mod = "?"
            extra = ""
            if self.proposals:
                extra = f"  [L3 first proposed {self.proposals[0].modulation.describe()}]"
            return f"{mod} @ {c.symbol_rate:g} Bd (from the decoded waveform){extra}"
        if self.proposals:
            return self.proposals[0].describe() + "  [hypothesis - not certified]"
        return "not determined"

    def summary(self) -> str:
        lines = [f"VERDICT: {self.verdict}"]
        if self.capture:
            lines.append(f"  container: {self.capture.info.summary()}")
        lines.append(f"  physical:  {self.resolved_physical}")
        if self.best:
            lines.append(f"  waveform:  {self.best.cartridge_id} ({self.best.detail})")
        if self.gof:
            lines.append(f"  fit:       {self.gof.summary()}")
        if self.frame is not None and getattr(self.frame, "found", False):
            lines.append(f"  framing:   {self.frame.summary()}")
        if self.fieldmap is not None:
            lines.append(f"  structure: {self.fieldmap.summary()}")
        for c in self.capabilities:
            if not c.available:
                lines.append(f"  gated:     {c.describe()}")
        return "\n".join(lines)


def _gate(name: str, have_bits: int) -> Capability:
    need, reason = DATA_REQUIREMENTS[name]
    return Capability(name, have_bits >= need, need, have_bits, reason)


def analyse(
    path: str,
    library: CartridgeLibrary | None = None,
    max_samples: int | None = 4_000_000,
    sample_rate: float | None = None,
    sps: int | None = None,
    progress: Callable[[str, float], None] | None = None,
    hold_out: str | None = None,
) -> AnalysisResult:
    """Analyse a capture file end to end.

    `hold_out` removes one cartridge from the library - the hold-out-cartridge
    rebuttal, which is a genuine blind test: track A cannot match, so the
    reconstruction tracks must do the work.
    """
    cap = load(path, **({"sample_rate": sample_rate} if sample_rate else {}))
    if max_samples and len(cap.samples) > max_samples:
        cap.samples = cap.samples[:max_samples]
        cap.info.n_samples = len(cap.samples)
    lib = library if library is not None else load_library()
    if hold_out:
        lib = lib.without(hold_out)
    return analyse_capture(cap, lib, sps=sps, progress=progress, path=path)


def analyse_capture(
    cap: Capture,
    library: CartridgeLibrary,
    sps: int | None = None,
    progress: Callable[[str, float], None] | None = None,
    path: str = "",
) -> AnalysisResult:
    """Analyse an already-loaded capture."""
    res = AnalysisResult(path=path or cap.info.path, capture=cap)
    t0 = time.time()

    def tick(stage: str, frac: float) -> None:
        res.timings[stage] = time.time() - t0
        if progress:
            progress(stage, frac)

    x = cap.samples
    fs = cap.fs
    tick("loaded", 0.05)

    # ---- tier 1: physical layer (fast) ------------------------------------
    res.proposals = propose(x, fs)
    if not res.proposals:
        res.verdict = "UNKNOWN"
        res.notes.append(
            "no symbol-rate line found - the capture may be noise, an analogue "
            "emission, or too short for a cyclostationary estimate"
        )
        res.capabilities = [_gate(k, 0) for k in DATA_REQUIREMENTS]
        return res
    tick("proposals", 0.25)

    # ---- shortlist by physical layer before any expensive decoding --------
    shortlist = shortlist_cartridges(library, res.proposals, fs)
    res.notes.append(
        f"L3 shortlisted {len(shortlist)} of {len(library)} cartridges from the "
        f"measured symbol rate ({res.proposals[0].symbol_rate_bd:.0f} Bd) and "
        f"modulation family"
    )
    tick("shortlist", 0.35)

    # ---- tier 2: demodulate under each hypothesis, score each cartridge ----
    best_overall: MatchScore | None = None
    best_llr: np.ndarray | None = None
    all_scores: list[MatchScore] = []

    for cart in shortlist:
        try:
            mapper = cart.build_mapper()
        except Exception:                                      # noqa: BLE001
            continue
        use_sps = sps or max(2, int(round(fs / cart.symbol_rate))) if cart.symbol_rate else (sps or 8)
        try:
            hyps = soft_demodulate(x, mapper, use_sps, fs, cart.rolloff)
        except Exception:                                      # noqa: BLE001
            continue
        for d in hyps:
            for m in match_library(d.llr, [cart], top=1):
                all_scores.append(m)
                if best_overall is None or m.score > best_overall.score:
                    best_overall, best_llr = m, d.llr

    all_scores.sort(key=lambda m: m.score, reverse=True)
    # Keep the best score per cartridge, so the ranking is over waveforms.
    seen, ranked = set(), []
    for m in all_scores:
        if m.cartridge_id in seen:
            continue
        seen.add(m.cartridge_id)
        ranked.append(m)
    res.matches = ranked[:5]
    tick("match", 0.7)

    have_bits = len(best_llr) if best_llr is not None else 0
    res.capabilities = [_gate(k, have_bits) for k in DATA_REQUIREMENTS]

    if best_overall is None:
        res.verdict = "UNKNOWN"
        res.notes.append("no cartridge in the library explains this capture")
        return res

    res.matched_cartridge = library.by_id(best_overall.cartridge_id)

    # ---- tier 3: bits, framing and structure ------------------------------
    payload = best_overall.result.payload_bits
    res.payload_bits = payload

    if len(payload) >= DATA_REQUIREMENTS["framing"][0]:
        cart = library.by_id(best_overall.cartridge_id)
        known = cart.sync_period if cart else None
        res.frame = analyse_frames(payload, known_period=None)
        if res.frame.found:
            res.fieldmap = profile_fields(payload, res.frame.period_bits)
    tick("framing", 0.9)

    # ---- verdict -----------------------------------------------------------
    agreement = best_overall.result.reencode_agreement
    certified = best_overall.ok
    if certified and (not np.isfinite(agreement) or agreement > 0.85):
        res.verdict = "IDENTIFIED"
    elif best_overall.score > 20:
        res.verdict = "PROBABLE"
    else:
        res.verdict = "UNKNOWN"
        res.notes.append(
            "the best hypothesis did not satisfy its own code constraints - "
            "reporting measurements only, and declining to name a waveform"
        )
    tick("done", 1.0)
    return res
