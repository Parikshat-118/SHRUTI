"""Classical, explainable proposals - no training data, no network.

Two estimators do most of the work:

* **Symbol rate** from the cyclostationary line in the squared envelope.
* **Modulation family** from higher-order cumulants, which are the textbook
  discriminative features for blind modulation recognition and which - unlike a
  learned embedding - can be written down and argued about.

A deliberate design note on the order penalty: an M-PSK constellation *contains*
every lower-order PSK constellation as a subset, so 8-PSK will always fit QPSK
data with low error.  Choosing on fit alone therefore always picks the highest
order offered.  The tie is broken by Occam - prefer the simplest constellation
that explains the data - and then settled for certain by whether the code
decodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..l4_twin.modulation import FSK, PSK, QAM, Modulation
from ..l4_twin.shaping import filter_delay, matched_filter
from ..l5_demod.sync import (
    estimate_cfo_mth_power,
    estimate_snr_m2m4,
    estimate_symbol_rate,
    estimate_symbol_rate_fm,
    is_constant_modulus,
    timing_recover,
)

__all__ = ["Proposal", "propose", "shortlist_cartridges", "cumulants"]


@dataclass
class Proposal:
    """One physical-layer hypothesis, with the evidence that produced it."""

    modulation: Modulation
    symbol_rate_bd: float
    sps: int
    evm: float
    score: float
    snr_db: float = float("nan")
    cfo_hz: float = 0.0
    evidence: dict = field(default_factory=dict)

    def describe(self) -> str:
        return (
            f"{self.modulation.describe()} @ {self.symbol_rate_bd:.1f} Bd "
            f"(EVM {self.evm:.3f}, SNR {self.snr_db:.1f} dB)"
        )


def cumulants(syms: np.ndarray) -> dict[str, float]:
    """Normalised fourth-order cumulants, the classical AMC features.

    ``|C40|/C21^2`` separates the PSK orders and QAM cleanly and is invariant to
    carrier phase, which is what makes it usable before synchronisation is
    finished.
    """
    s = np.asarray(syms, dtype=np.complex128)
    s = s[np.isfinite(s)]
    if len(s) < 32:
        return {"c20": 0.0, "c21": 0.0, "c40": 0.0, "c42": 0.0}
    p = np.mean(np.abs(s) ** 2)
    if p <= 0:
        return {"c20": 0.0, "c21": 0.0, "c40": 0.0, "c42": 0.0}
    s = s / np.sqrt(p)

    m20 = np.mean(s ** 2)
    m21 = np.mean(np.abs(s) ** 2)
    m40 = np.mean(s ** 4)
    m42 = np.mean(np.abs(s) ** 4)

    c20 = m20
    c21 = m21
    c40 = m40 - 3 * m20 ** 2
    c42 = m42 - np.abs(m20) ** 2 - 2 * m21 ** 2
    return {
        "c20": float(np.abs(c20)),
        "c21": float(np.abs(c21)),
        "c40": float(np.abs(c40)),
        "c42": float(np.abs(c42)),
    }


#: Candidate constellations, simplest first.  Order matters: ties are broken
#: toward the simpler hypothesis.
_CANDIDATES: list[Modulation] = [
    PSK(2), PSK(4), PSK(8),
    QAM(16), QAM(32), QAM(64),
    PSK(4, differential=True), PSK(4, pi4=True),
]

#: FSK is a required modulation family and needs an entirely separate path - it is not
#: a linear modulation, so there is no constellation to measure EVM against and
#: no symbol-rate line in the envelope.  Omitting it does not make FSK score
#: badly; it makes FSK get classified as whatever QAM order fits the noise.
_FSK_CANDIDATES: list[Modulation] = [FSK(2, h=1.0), FSK(4, h=1.0), FSK(2, h=0.5)]


def propose(
    x: np.ndarray,
    fs: float,
    sps_target: int = 8,
    symbol_rate_hint: float | None = None,
    top: int = 4,
) -> list[Proposal]:
    """Rank physical-layer hypotheses for a complex baseband capture."""
    x = np.asarray(x, dtype=np.complex128)
    if len(x) < 512:
        return []

    # A constant envelope means the signal is FSK/MSK/CPM, and that changes both
    # which rate estimator is valid and which constellations are worth trying.
    const_mod = is_constant_modulus(x)

    if symbol_rate_hint:
        rate, sharp = float(symbol_rate_hint), float("nan")
    elif const_mod:
        rate, sharp = estimate_symbol_rate_fm(x, fs)
    else:
        rate, sharp = estimate_symbol_rate(x, fs)
    if not rate or rate <= 0:
        return []

    sps = max(2, int(round(fs / rate)))
    out: list[Proposal] = []

    if const_mod:
        out.extend(_propose_fsk(x, fs, rate, sps, sharp))

    for i, mod in enumerate(_CANDIDATES):
        try:
            order = mod.order if mod.kind == "psk" else 4
            cfo, _ = estimate_cfo_mth_power(x, fs, order=max(2, min(order, 8)))
            n = np.arange(len(x))
            y = x * np.exp(-1j * 2 * np.pi * cfo * n / fs)
            y = matched_filter(y, sps, 0.35)[2 * filter_delay(sps):]
            syms, _ = timing_recover(y, sps)
            p = np.sqrt(np.mean(np.abs(syms) ** 2)) or 1.0
            syms = syms / p

            power = mod.order if mod.kind == "psk" else 4
            ref = np.angle(np.mean(mod.points ** power))
            ph = np.angle(np.mean(syms ** power) * np.exp(-1j * ref)) / power
            syms = syms * np.exp(-1j * ph)

            pts = mod.points
            nearest = pts[np.argmin(np.abs(syms[:, None] - pts[None, :]), axis=1)]
            evm = float(np.sqrt(np.mean(np.abs(syms - nearest) ** 2)))
            snr = estimate_snr_m2m4(syms)

            # Occam: a higher-order constellation contains the lower ones, so it
            # always fits at least as well.  Penalise complexity explicitly.
            penalty = 0.012 * mod.bits_per_symbol
            out.append(
                Proposal(
                    modulation=mod,
                    symbol_rate_bd=rate,
                    sps=sps,
                    evm=evm,
                    score=-(evm + penalty),
                    snr_db=snr,
                    cfo_hz=cfo,
                    evidence={
                        "rate_sharpness": sharp,
                        "cumulants": cumulants(syms),
                        "order_penalty": penalty,
                    },
                )
            )
        except Exception:                                      # noqa: BLE001
            continue

    out.sort(key=lambda p: p.score, reverse=True)
    return out[:top]


def _propose_fsk(
    x: np.ndarray, fs: float, rate: float, sps: int, sharp: float
) -> list[Proposal]:
    """Score FSK hypotheses by how cleanly their tone bank separates the symbols.

    There is no constellation here, so EVM is meaningless.  The analogous quality
    measure is the **tone margin**: at the right order and deviation each symbol
    lands squarely in one filter, so the winning tone beats the runner-up by a
    wide and consistent margin.  A wrong hypothesis splits energy between
    filters and the margin collapses.
    """
    from ..l5_demod.demod import _demod_fsk, _fsk_carrier

    out: list[Proposal] = []
    for mod in _FSK_CANDIDATES:
        try:
            cfo = _fsk_carrier(x, mod, fs, rate)
            n = np.arange(len(x))
            y = x * np.exp(-1j * 2 * np.pi * cfo * n / fs)
            d = _demod_fsk(y, mod, sps, fs, cfo)
            margin = float(d.meta.get("tone_margin", 0.0))
            if not np.isfinite(margin):
                continue
            # Same Occam penalty as the linear path: a higher order always has
            # more filters to win with, so it must earn the extra complexity.
            penalty = 0.02 * mod.bits_per_symbol
            out.append(
                Proposal(
                    modulation=mod,
                    symbol_rate_bd=rate,
                    sps=sps,
                    evm=float(1.0 - margin),
                    score=float(margin - penalty),
                    snr_db=estimate_snr_m2m4(y),
                    cfo_hz=cfo,
                    evidence={
                        "rate_sharpness": sharp,
                        "tone_margin": margin,
                        "constant_modulus": True,
                        "rate_estimator": "frequency discriminator",
                    },
                )
            )
        except Exception:                                      # noqa: BLE001
            continue
    return out


def shortlist_cartridges(
    library, proposals: list[Proposal], fs: float, rate_tolerance: float = 0.25
) -> list:
    """Keep only cartridges consistent with the measured physical layer.

    Matching is on the *ratio* of symbol rate to sample rate rather than on
    absolute baud, because for a headerless file the absolute rate is not
    identifiable - only ratios are.  A cartridge declaring 2400 Bd is a
    hypothesis about scale, not a measurement.
    """
    if not proposals:
        return list(library)

    best = proposals[0]
    families = {type(p.modulation).__name__ for p in proposals}
    orders = {p.modulation.order for p in proposals}

    # **Symbol rate is the filter; modulation order is only a preference.**
    #
    # The rate estimate is reliable to a fraction of a percent.  The modulation
    # *order* is not: an M-PSK constellation contains every lower-order one, so
    # QPSK data routinely proposes as 8-PSK or QAM, and excluding on order threw
    # away the correct cartridge.  Worse, it cascaded - with every rate-matching
    # cartridge excluded the shortlist fell back to rate-MISmatched ones, and a
    # 1200 Bd cartridge against a 2 MBd capture implies sps = 13,333, which made
    # the FSK alignment sweep take minutes. One over-strict filter became a hang.
    #
    # Order and family now rank rather than exclude, and the decode settles it.
    scored: list[tuple[int, object]] = []
    for cart in library:
        try:
            mapper = cart.build_mapper()
        except Exception:                                      # noqa: BLE001
            continue

        rate = cart.symbol_rate
        if rate > 0 and best.symbol_rate_bd > 0:
            ratio = rate / best.symbol_rate_bd
            # Accept the declared rate, or a scale factor consistent with a
            # different assumed sample rate (the identifiability caveat above).
            if not any(abs(ratio / k - 1.0) < rate_tolerance
                       for k in (1.0, 0.5, 2.0, 0.25, 4.0)):
                continue

        rank = 0
        if type(mapper).__name__ in families or isinstance(mapper, FSK):
            rank += 2
        if mapper.order in orders or isinstance(mapper, FSK):
            rank += 1
        scored.append((rank, cart))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [c for _, c in scored] or list(library)
