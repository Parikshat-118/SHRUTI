"""Convolutional codes with soft-decision Viterbi decoding.

The canonical short-constraint code, and the one CCSDS 131.0-B specifies for
telemetry downlinks, is **K = 7, rate 1/2, G = [171, 133] octal**, punctured to
2/3 ... 7/8.  That is the default here, and it is why this file is the first
thing built: it covers the most common short-constraint family and the CCSDS
telemetry standard at the same time.

Conventions, stated once because getting them wrong fails silently
-----------------------------------------------------------------
* Shift register ``r = (b_t, b_{t-1}, ..., b_{t-K+1})``, ``b_t`` in the MSB.
* Output *j* is ``parity(r & g_j)``.
* State ``s`` is the low ``K-1`` bits of ``r``; ``next = ((b << (K-1)) | s) >> 1``.
* LLR sign: **positive means bit 0** (see ``shruti.core.bits``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.bits import hard_decision

__all__ = ["ConvCode", "CCSDS_K7_R12", "PUNCTURE_PATTERNS", "standard_code"]


# CCSDS 131.0-B puncturing patterns, as (2, P) masks over the rate-1/2 output.
# Row 0 is the G1 output stream, row 1 is G2.  A 0 means "not transmitted".
# NOTE: verify against the Blue Book before claiming bit-exact CCSDS conformance;
# the round trip here is self-consistent regardless.
PUNCTURE_PATTERNS: dict[str, np.ndarray] = {
    "1/2": np.array([[1], [1]], dtype=np.uint8),
    "2/3": np.array([[1, 0], [1, 1]], dtype=np.uint8),
    "3/4": np.array([[1, 0, 1], [1, 1, 0]], dtype=np.uint8),
    "5/6": np.array([[1, 0, 1, 0, 1], [1, 1, 0, 1, 0]], dtype=np.uint8),
    "7/8": np.array([[1, 0, 0, 0, 1, 0, 1], [1, 1, 1, 1, 0, 1, 0]], dtype=np.uint8),
}


@dataclass
class ConvCode:
    """A rate-1/n convolutional code, optionally punctured.

    Parameters
    ----------
    K:
        Constraint length.  "Short-constrained" means roughly K <= 9;
        the search grid in blind reconstruction uses 3..9.
    polys:
        Generator polynomials as integers.  Octal literals are conventional:
        ``[0o171, 0o133]``.
    invert:
        Per-output inversion.  CCSDS inverts the second output to guarantee
        symbol-transition density; without it a long run of zeros produces no
        transitions and the receiver's timing recovery drifts.
    rate:
        Puncturing key from :data:`PUNCTURE_PATTERNS`.
    """

    K: int = 7
    polys: tuple[int, ...] = (0o171, 0o133)
    invert: tuple[bool, ...] = (False, False)
    rate: str = "1/2"
    _trellis: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if len(self.invert) != len(self.polys):
            self.invert = tuple([False] * len(self.polys))
        if self.rate not in PUNCTURE_PATTERNS:
            raise ValueError(f"unknown puncture rate {self.rate!r}")
        self._build_trellis()

    # ------------------------------------------------------------------ setup

    @property
    def n_out(self) -> int:
        return len(self.polys)

    @property
    def n_states(self) -> int:
        return 1 << (self.K - 1)

    @property
    def code_rate(self) -> float:
        pat = PUNCTURE_PATTERNS[self.rate]
        return float(pat.shape[1]) / float(pat.sum())

    def _build_trellis(self) -> None:
        K, ns, nout = self.K, self.n_states, self.n_out
        mask = ns - 1
        inv = np.array(self.invert, dtype=np.uint8)

        out = np.zeros((ns, 2, nout), dtype=np.uint8)
        nxt = np.zeros((ns, 2), dtype=np.int64)
        for s in range(ns):
            for b in (0, 1):
                r = (b << (K - 1)) | s
                for j, g in enumerate(self.polys):
                    out[s, b, j] = (bin(r & g).count("1") & 1) ^ inv[j]
                nxt[s, b] = ((b << (K - 1)) | s) >> 1

        # Reverse trellis: each next-state has exactly two predecessors, found by
        # replaying the bit that was shifted out.
        prev_s = np.zeros((ns, 2), dtype=np.int64)
        prev_b = np.zeros((ns, 2), dtype=np.int64)
        for nsx in range(ns):
            for i, lsb in enumerate((0, 1)):
                r = (nsx << 1) | lsb
                prev_s[nsx, i] = r & mask
                prev_b[nsx, i] = r >> (K - 1)

        self._trellis = {
            "out": out,
            "next": nxt,
            "prev_s": prev_s,
            "prev_b": prev_b,
            # +1/-1 form of the outputs, for the soft branch metric
            "sym": (1 - 2 * out.astype(np.float64)),
        }

    # --------------------------------------------------------------- encoding

    def encode(self, bits: np.ndarray, terminate: bool = True) -> np.ndarray:
        """Encode hard bits.  With ``terminate`` the register is flushed to zero."""
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        if terminate:
            bits = np.concatenate([bits, np.zeros(self.K - 1, np.uint8)])

        out_tbl = self._trellis["out"]
        nxt = self._trellis["next"]
        s = 0
        out = np.empty((len(bits), self.n_out), dtype=np.uint8)
        for i, b in enumerate(bits):
            out[i] = out_tbl[s, b]
            s = nxt[s, b]
        return self._puncture(out.reshape(-1))

    def _puncture(self, stream: np.ndarray) -> np.ndarray:
        pat = PUNCTURE_PATTERNS[self.rate]
        if pat.shape[1] == 1 and pat.all():
            return stream
        nout, P = pat.shape
        nsteps = len(stream) // nout
        m = stream[: nsteps * nout].reshape(nsteps, nout).T          # (nout, nsteps)
        keep = np.tile(pat, (1, (nsteps + P - 1) // P))[:, :nsteps].astype(bool)
        return m.T[keep.T]

    @staticmethod
    def _keep_count(pat: np.ndarray, nsteps: int) -> int:
        """How many bits survive puncturing over `nsteps` trellis steps."""
        P = pat.shape[1]
        full, rem = divmod(nsteps, P)
        return full * int(pat.sum()) + int(pat[:, :rem].sum())

    def _depuncture(self, llr: np.ndarray) -> np.ndarray:
        """Re-insert erasures (LLR = 0) where the encoder dropped bits.

        The final period is usually partial, so the step count is recovered by
        search rather than by division - getting this wrong silently truncates
        the tail and breaks trellis termination.
        """
        pat = PUNCTURE_PATTERNS[self.rate]
        if pat.shape[1] == 1 and pat.all():
            return llr

        nout, P = pat.shape
        target = len(llr)
        nsteps = (target // max(1, int(pat.sum()))) * P
        while self._keep_count(pat, nsteps + 1) <= target:
            nsteps += 1
        while nsteps > 0 and self._keep_count(pat, nsteps) > target:
            nsteps -= 1

        keep = np.tile(pat, (1, (nsteps + P - 1) // P))[:, :nsteps].astype(bool)
        full = np.zeros((nout, nsteps), dtype=np.float64)
        full.T[keep.T] = llr[: self._keep_count(pat, nsteps)]
        return full.T.reshape(-1)

    # --------------------------------------------------------------- decoding

    def decode(
        self, llr: np.ndarray, terminated: bool = True
    ) -> tuple[np.ndarray, float]:
        """Soft-decision Viterbi.

        Returns ``(decoded_bits, path_metric)``.  The metric is the accumulated
        log-likelihood of the surviving path; its *margin* over the runner-up is
        a usable confidence signal, and it is what the closure loop maximises
        with respect to the physical-layer parameters.
        """
        llr = np.asarray(llr, dtype=np.float64).reshape(-1)
        llr = self._depuncture(llr)

        nout, ns = self.n_out, self.n_states
        nsteps = len(llr) // nout
        if nsteps < self.K:
            return np.zeros(0, np.uint8), -np.inf
        obs = llr[: nsteps * nout].reshape(nsteps, nout)

        sym = self._trellis["sym"]            # (ns, 2, nout), +1 for bit 0
        prev_s = self._trellis["prev_s"]      # (ns, 2)
        prev_b = self._trellis["prev_b"]

        NEG = -1e18
        pm = np.full(ns, NEG, dtype=np.float64)
        pm[0] = 0.0
        choice = np.zeros((nsteps, ns), dtype=np.uint8)

        # Branch metrics depend only on (state, bit), so index them by the
        # reverse trellis once per step.
        for t in range(nsteps):
            bm = sym.reshape(ns * 2, nout) @ obs[t]        # (ns*2,)
            bm = bm.reshape(ns, 2)
            cand = pm[prev_s] + bm[prev_s, prev_b]          # (ns, 2)
            pick = np.argmax(cand, axis=1)
            pm = cand[np.arange(ns), pick]
            choice[t] = pick.astype(np.uint8)

        end_state = 0 if terminated else int(np.argmax(pm))
        metric = float(pm[end_state])

        # Traceback
        bits = np.zeros(nsteps, dtype=np.uint8)
        s = end_state
        for t in range(nsteps - 1, -1, -1):
            i = choice[t, s]
            bits[t] = prev_b[s, i]
            s = int(prev_s[s, i])

        if terminated:
            bits = bits[: max(0, nsteps - (self.K - 1))]
        return bits, metric

    # ------------------------------------------------------------- diagnostics

    def parity_checks(self, block_len: int) -> np.ndarray:
        """Parity-check matrix for a terminated block of `block_len` info bits.

        Built by encoding the identity: column *i* of the generator is the
        encoding of a one-hot message, so the dual space of that generator is
        the set of checks that hold on the coded stream.  This is what L6
        track A tests a candidate stream against.
        """
        from ..core.gf2 import BitMatrix, nullspace

        rows = []
        for i in range(block_len):
            msg = np.zeros(block_len, np.uint8)
            msg[i] = 1
            rows.append(self.encode(msg, terminate=True))
        gen = np.array(rows, dtype=np.uint8)
        return nullspace(BitMatrix.from_bits(gen))

    def describe(self) -> str:
        polys = ", ".join(f"0o{p:o}" for p in self.polys)
        return f"convolutional K={self.K} rate={self.rate} G=[{polys}]"


def standard_code(name: str) -> ConvCode:
    """Look up a named standard code."""
    table = {
        "ccsds-k7-r12": ConvCode(K=7, polys=(0o171, 0o133), invert=(False, True), rate="1/2"),
        "ccsds-k7-r23": ConvCode(K=7, polys=(0o171, 0o133), invert=(False, True), rate="2/3"),
        "ccsds-k7-r34": ConvCode(K=7, polys=(0o171, 0o133), invert=(False, True), rate="3/4"),
        "ccsds-k7-r78": ConvCode(K=7, polys=(0o171, 0o133), invert=(False, True), rate="7/8"),
        "nasa-k7-r12": ConvCode(K=7, polys=(0o171, 0o133), rate="1/2"),
        "k9-r12": ConvCode(K=9, polys=(0o753, 0o561), rate="1/2"),
        "k5-r12": ConvCode(K=5, polys=(0o23, 0o35), rate="1/2"),
        "k3-r12": ConvCode(K=3, polys=(0o7, 0o5), rate="1/2"),
    }
    if name not in table:
        raise KeyError(f"unknown standard code {name!r}; have {sorted(table)}")
    return table[name]


#: The canonical short-constraint code, as specified by CCSDS 131.0-B.
CCSDS_K7_R12 = standard_code("ccsds-k7-r12")


def ber(a: np.ndarray, b: np.ndarray) -> float:
    """Bit error rate between two equal-length hard bit arrays."""
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    return float(np.count_nonzero(np.asarray(a[:n], np.uint8) ^ np.asarray(b[:n], np.uint8))) / n


def decode_hard(code: ConvCode, bits: np.ndarray, magnitude: float = 4.0) -> np.ndarray:
    """Convenience: Viterbi on hard bits by saturating them to LLRs."""
    from ..core.bits import llr_from_hard

    out, _ = code.decode(llr_from_hard(bits, magnitude))
    return out
