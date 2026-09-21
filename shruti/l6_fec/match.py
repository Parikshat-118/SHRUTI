"""L6 track A - library match: test a soft bitstream against known cartridges.

Track A is a lookup rather than a research problem.  It covers the overwhelming
majority of real traffic and its confidence is decisive: the code either decodes
or it does not.

**The research tracks never block this one.**  Tracks B and C reconstruct
*unknown* codes and are genuinely hard; track A recognises *known* ones and is
not.  Building A first is the single most important sequencing decision in the
project.

Everything here operates on **soft** bits.  Undoing an interleaver is a permute
of the LLR array; undoing an additive scrambler is a sign flip where the
generator sequence is 1.  Neither needs a hard decision, and postponing the hard
decision until after the decoder is what buys several dB.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..cartridge.schema import Cartridge
from ..core.bits import bits_to_bytes, bytes_to_bits, hard_decision, llr_from_hard
from .conv import ConvCode
from .interleave import ConvolutionalInterleaver, Interleaver
from .ldpc import LDPCCode
from .rs import ReedSolomon
from .scramble import AdditiveScrambler, SelfSyncScrambler

__all__ = ["ChainDecodeResult", "decode_with_cartridge", "match_library", "MatchScore",
           "COVERING_RADIUS"]

#: Agreement a rate-1/2 convolutional decoder reaches against an UNRELATED
#: stream. It always returns the nearest codeword, so this - not 0.5 - is the
#: null hypothesis for "the decoder produced something". Measured, not assumed:
#: see tests/test_roundtrip.py::test_reencode_agreement_discriminates.
COVERING_RADIUS = 0.87


@dataclass
class ChainDecodeResult:
    """Outcome of running one cartridge's bit layer in reverse."""

    payload_bits: np.ndarray
    ok: bool
    stages: dict[str, np.ndarray] = field(default_factory=dict)
    rs_corrected: int = 0
    rs_failed: int = 0
    rs_blocks: int = 0
    ldpc_converged: int = 0
    ldpc_blocks: int = 0
    viterbi_metric: float = float("nan")
    reencode_agreement: float = float("nan")
    notes: list[str] = field(default_factory=list)

    @property
    def n_payload_bits(self) -> int:
        return len(self.payload_bits)

    def as_text(self, errors: str = "replace") -> str:
        return bits_to_bytes(self.payload_bits).decode("utf-8", errors=errors)


def descramble_llr(scr, llr: np.ndarray) -> np.ndarray:
    """Undo a scrambler on soft bits.

    For an additive scrambler this is exact and costs nothing: XOR with 1 means
    "invert this bit", and inverting a bit negates its LLR.

    A self-synchronous scrambler mixes bits together, so an exact soft inverse
    would need the joint distribution.  SHRUTI takes the hard decision there and
    says so - and that error multiplication (one channel error becomes
    ``taps+1``) is precisely why self-synchronous scrambling is the harder case.
    """
    llr = np.asarray(llr, dtype=np.float64)
    if isinstance(scr, AdditiveScrambler):
        seq = scr.sequence(len(llr))
        return llr * (1.0 - 2.0 * seq)
    if isinstance(scr, SelfSyncScrambler):
        return llr_from_hard(scr.descramble(hard_decision(llr)), magnitude=float(np.mean(np.abs(llr)) or 4.0))
    raise TypeError(f"cannot descramble with {type(scr).__name__}")


def deinterleave_llr(il: Interleaver, llr: np.ndarray) -> np.ndarray:
    """Undo an interleaver on soft bits - a gather under the inverse permutation."""
    if isinstance(il, ConvolutionalInterleaver):
        # Streaming delay lines: run the matched de-interleaver on the LLR values
        # by treating them as the transported quantity.
        delays = (il.branches - 1 - np.arange(il.branches)) * il.delay
        regs = [np.zeros(d, dtype=np.float64) for d in delays]
        out = np.empty(len(llr), dtype=np.float64)
        for i, v in enumerate(llr):
            br = i % il.branches
            if delays[br] == 0:
                out[i] = v
            else:
                out[i] = regs[br][0]
                regs[br] = np.concatenate([regs[br][1:], [v]])
        # A convolutional interleaver/de-interleaver pair is transparent only
        # AFTER its end-to-end latency.  Failing to drop that prefix shifts the
        # whole stream and destroys block alignment for everything downstream -
        # which is why an LDPC block decoder then converges on nothing.
        return out[il.latency:] if il.latency < len(out) else out
    return il.deinterleave(np.asarray(llr, dtype=np.float64))


def reencode_agreement(code, decoded: np.ndarray, received_llr: np.ndarray) -> float:
    """Fraction of received bits the re-encoded decoding reproduces.

    **This is the analysis-by-synthesis principle applied at the code layer, and
    it is the only sound way to score a code hypothesis.**  A Viterbi path metric
    cannot do the job: it scales with the magnitude of the input LLRs, so a
    confidently-wrong hypothesis outscores a tentatively-right one.  Re-encoding
    is scale-free and unambiguous.

    * right code  -> agreement = 1 - (channel BER), typically > 0.99
    * wrong code  -> agreement ~ :data:`COVERING_RADIUS` (about 0.87 for a
      rate-1/2 code), **not 0.5**

    That second figure is the one that matters and it is easy to get wrong.  The
    decoder does not return a random sequence when the code hypothesis is wrong;
    it returns the *nearest codeword*, which for a dense rate-1/2 code still
    reproduces around 87% of the received bits.  Treating 0.5 as the null makes
    a wrong hypothesis look like strong evidence, and both the certificate in
    :func:`_chain_succeeded` and the score in :func:`match_library` are centred
    on the covering radius for exactly that reason.
    """
    try:
        re_enc = code.encode(decoded, terminate=False) if isinstance(code, ConvCode) else None
    except Exception:                                          # noqa: BLE001
        return 0.5
    if re_enc is None:
        return 0.5
    recv = hard_decision(received_llr)
    n = min(len(re_enc), len(recv))
    if n < 64:
        return 0.5
    return float(np.count_nonzero(re_enc[:n] == recv[:n]) / n)


def find_sync_offset(
    bits: np.ndarray, marker: np.ndarray, period: int, max_search: int | None = None
) -> int:
    """Locate the first sync marker in a stream, by agreement across all frames.

    Scores each candidate offset by how well the marker matches at *every*
    multiple of the frame period, not just once.  A single 32-bit match happens
    by chance every few billion bits; a match repeated at the right period does
    not, so this is decisive even on a noisy stream.
    """
    b = np.asarray(bits, dtype=np.uint8).reshape(-1)
    m = np.asarray(marker, dtype=np.uint8).reshape(-1)
    if len(b) < period + len(m):
        return 0

    limit = max_search if max_search is not None else min(period, len(b) - len(m))
    nframes = min(8, max(1, len(b) // period))
    best_off, best_score = 0, -1.0

    for off in range(limit):
        hits, total = 0, 0
        for f in range(nframes):
            s = off + f * period
            if s + len(m) > len(b):
                break
            hits += int(np.count_nonzero(b[s : s + len(m)] == m))
            total += len(m)
        if total == 0:
            continue
        score = hits / total
        if score > best_score:
            best_off, best_score = off, score
            if score == 1.0:
                break

    # Below about 80% agreement across frames there is no credible marker, and
    # guessing an offset is worse than starting at zero.
    return best_off if best_score >= 0.8 else 0


def _decode_inner(code, llr: np.ndarray, res: ChainDecodeResult) -> np.ndarray:
    """Soft-decode the inner code, returning the LLRs (or hard bits) it protects."""
    if isinstance(code, ConvCode):
        # `terminated=False` is not a detail.  A *captured* stream ends wherever
        # the recording stopped, not in the all-zero state, so forcing the
        # traceback to start at state 0 corrupts the tail - and Viterbi traceback
        # errors propagate backwards a long way.  That alone turned a clean
        # decode into ~8% residual BER, which then makes every code hypothesis
        # look equally mediocre and destroys blind identification.
        bits, metric = code.decode(llr, terminated=False)
        res.viterbi_metric = metric
        res.reencode_agreement = reencode_agreement(code, bits, llr)
        return llr_from_hard(bits, magnitude=6.0)
    if isinstance(code, LDPCCode):
        nblocks = len(llr) // code.n
        outs, conv = [], 0
        for b in range(nblocks):
            r = code.decode(llr[b * code.n : (b + 1) * code.n], max_iter=40)
            outs.append(r.message)
            conv += int(r.converged)
        res.ldpc_blocks = nblocks
        res.ldpc_converged = conv
        joined = np.concatenate(outs) if outs else np.zeros(0, np.uint8)
        return llr_from_hard(joined, magnitude=6.0)
    raise TypeError(f"cannot inner-decode with {type(code).__name__}")


def decode_with_cartridge(cart: Cartridge, llr: np.ndarray) -> ChainDecodeResult:
    """Run a cartridge's bit layer in reverse on soft bits.

    The exact inverse of :func:`shruti.l4_twin.chain.synthesise`'s bit stages,
    in reverse order.  If the cartridge is the right one, the payload comes out;
    if it is not, the codes fail their parity checks and ``ok`` is False - which
    is the whole basis of scoring in :func:`match_library`.
    """
    from ..l4_twin.chain import strip_sync

    res = ChainDecodeResult(payload_bits=np.zeros(0, np.uint8), ok=False)
    x = np.asarray(llr, dtype=np.float64)

    scr_post = cart.build_scrambler_post()
    if scr_post is not None:
        x = descramble_llr(scr_post, x)
        res.stages["descrambled_post"] = x.copy()

    il = cart.build_interleaver()
    if il is not None:
        x = deinterleave_llr(il, x)
        res.stages["deinterleaved"] = x.copy()

    inner = cart.build_fec()
    if inner is not None:
        x = _decode_inner(inner, x, res)
        res.stages["inner_decoded"] = x.copy()

    marker = cart.sync_word()
    if marker is not None:
        period = cart.sync_period or (len(marker) * 32)
        hard = hard_decision(x)
        # Find the marker rather than assuming the capture starts on a frame
        # boundary.  **A real recording begins whenever the operator pressed
        # record**, not at the start of a transfer frame, so assuming offset 0
        # strips 32 bits out of the middle of a frame and desynchronises the
        # descrambler and every codeword after it.  On synthetic captures that
        # happen to start aligned this is invisible, which is exactly what makes
        # it dangerous.
        off = find_sync_offset(hard, marker, period)
        if off > 0:
            res.notes.append(f"sync marker found at bit offset {off}, not 0")
        stripped = strip_sync(hard[off:], len(marker), period)
        x = llr_from_hard(stripped, magnitude=6.0)
        res.stages["sync_stripped"] = x.copy()

    scr = cart.build_scrambler()
    if scr is not None:
        x = descramble_llr(scr, x)
        res.stages["descrambled"] = x.copy()

    il_outer = cart.build_interleaver_outer()
    if il_outer is not None:
        x = deinterleave_llr(il_outer, x)
        res.stages["deinterleaved_outer"] = x.copy()

    outer = cart.build_fec_outer()
    if outer is not None:
        if not isinstance(outer, ReedSolomon):
            x = _decode_inner(outer, x, res)
        else:
            data = np.frombuffer(bits_to_bytes(hard_decision(x)), dtype=np.uint8)
            msg, corrected, failed = outer.decode(data)
            res.rs_corrected = corrected
            res.rs_failed = failed
            res.rs_blocks = len(data) // outer.n
            if failed:
                res.notes.append(f"{failed}/{res.rs_blocks} RS blocks failed")
            x = llr_from_hard(bytes_to_bits(msg.tobytes()), magnitude=6.0)
        res.stages["outer_decoded"] = x.copy()

    res.payload_bits = hard_decision(x)
    res.ok = _chain_succeeded(res, cart)
    return res


def _chain_succeeded(res: ChainDecodeResult, cart: Cartridge) -> bool:
    """Did the codes in the chain actually satisfy their constraints?

    This is the certificate that underwrites every claim SHRUTI makes: a code
    that decodes is a code whose thousands of parity checks all held at once,
    which can only happen if every upstream estimate was right.

    **The final block is excused, and only the final block.**  A capture is cut
    wherever the recording stopped, so its last codeword is almost always
    truncated - failing the whole certificate on that would mark every real
    capture as undecoded.  Any *interior* block failing is a genuine failure and
    is not excused.
    """
    if res.n_payload_bits == 0:
        return False
    if res.rs_blocks:
        interior_failures = max(0, res.rs_failed - 1)
        if interior_failures > 0:
            return False
    elif res.rs_failed > 0:
        return False
    if res.ldpc_blocks:
        if res.ldpc_converged < res.ldpc_blocks - 1:
            return False

    # A convolutional decoder ALWAYS returns something: it finds the nearest
    # codeword, even to noise.  For a rate-1/2 code the nearest codeword to an
    # unrelated stream still agrees on roughly 87% of bits - the covering
    # radius - so "it decoded" is not evidence of anything on its own.
    #
    # Demand agreement well clear of that floor.  Without this the wrong
    # cartridge can earn a certificate and the tool reports IDENTIFIED with a
    # confidently wrong answer, which is the one failure this design exists to
    # prevent.
    if np.isfinite(res.reencode_agreement) and res.reencode_agreement < 0.95:  # noqa: PLR2004
        res.notes.append(
            f"re-encode agreement {res.reencode_agreement:.3f} is too close to the "
            f"covering radius of the code (~0.87) to certify - the decoder found "
            f"a nearest codeword, not evidence that this is the right code"
        )
        return False

    return True


@dataclass
class MatchScore:
    """How well one cartridge explains a bitstream."""

    cartridge_id: str
    score: float
    ok: bool
    result: ChainDecodeResult
    detail: str = ""

    def __repr__(self) -> str:  # pragma: no cover
        return f"MatchScore({self.cartridge_id}, score={self.score:.3f}, ok={self.ok})"


def match_library(
    llr: np.ndarray, library, top: int = 5, text_hint: bool = True
) -> list[MatchScore]:
    """Score every cartridge in `library` against a soft bitstream.

    Returns the best `top`, most convincing first.  Scoring combines the hard
    evidence (did the codes decode) with a soft plausibility signal, because on
    a short capture several cartridges can decode and the tie needs breaking.
    """
    scores: list[MatchScore] = []
    for cart in library:
        try:
            res = decode_with_cartridge(cart, llr)
        except Exception as exc:                              # noqa: BLE001
            scores.append(MatchScore(cart.id, -1e9, False, ChainDecodeResult(
                np.zeros(0, np.uint8), False, notes=[str(exc)]), f"error: {exc}"))
            continue

        s = 0.0
        detail = []

        # --- primary evidence: did the code's own constraints actually hold? ---
        # Each branch requires real blocks to have been processed.  Awarding
        # points for "zero failures" when zero blocks existed is free credit for
        # any cartridge whose code never ran, and it is why a long CCSDS
        # cartridge previously outscored the correct short one every time.
        if res.rs_blocks > 0:
            clean = (res.rs_blocks - res.rs_failed) / res.rs_blocks
            s += 60.0 * clean - 20.0 * (1.0 - clean)
            detail.append(f"RS {res.rs_blocks - res.rs_failed}/{res.rs_blocks} blocks clean")
        if res.ldpc_blocks > 0:
            frac = res.ldpc_converged / res.ldpc_blocks
            s += 60.0 * frac - 20.0 * (1.0 - frac)
            detail.append(f"LDPC {res.ldpc_converged}/{res.ldpc_blocks} converged")
        if np.isfinite(res.reencode_agreement):
            # **Chance for a DECODER OUTPUT is the covering radius, not 0.5.**
            #
            # A convolutional decoder returns the nearest codeword even to noise,
            # and for a rate-1/2 code that still reproduces ~87% of the received
            # bits. Scoring against a coin flip therefore handed a *wrong* coded
            # cartridge ~+44 points of pure noise, which beat a *correct* uncoded
            # cartridge that has no code evidence to offer at all.
            #
            # Centred on the covering radius, an agreement of 0.87 scores zero -
            # it is evidence of nothing - and only genuine agreement scores.
            s += 200.0 * (res.reencode_agreement - COVERING_RADIUS)
            detail.append(f"re-encode agreement {res.reencode_agreement:.3f}")

        if not detail:
            # An uncoded cartridge offers no code evidence at all, so it must not
            # be able to beat one that does.  It stays in the ranking on the
            # weaker signals only.
            detail.append("uncoded - no code evidence available")

        if text_hint and res.n_payload_bits > 64:
            s += 20.0 * _printable_fraction(res.payload_bits)

        scores.append(MatchScore(cart.id, s, res.ok, res, "; ".join(detail)))

    scores.sort(key=lambda m: m.score, reverse=True)
    return scores[:top]


def _printable_fraction(bits: np.ndarray) -> float:
    """Fraction of bytes that are printable ASCII.

    A weak, honest tie-breaker only.  It must never be the primary evidence -
    a payload that is encrypted or compressed is *supposed* to look like noise,
    and treating high entropy as failure would invert the correct conclusion.
    """
    data = bits_to_bytes(bits)
    if not data:
        return 0.0
    arr = np.frombuffer(data, dtype=np.uint8)
    printable = ((arr >= 32) & (arr < 127)) | np.isin(arr, [9, 10, 13])
    return float(np.count_nonzero(printable) / len(arr))
