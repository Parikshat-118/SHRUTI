"""LDPC codes with min-sum belief propagation.

A regular ``(wc, wr)`` LDPC code built from a seeded random construction with
4-cycle removal, plus a normalised min-sum BP decoder.

Honest labelling, because it matters for the claims we make elsewhere: this is a
**SHRUTI-defined** LDPC family, not a bit-exact reproduction of the CCSDS AR4JA
or 802.11n matrices.  The parity-check matrix is fully specified by
``(n, wc, wr, seed)`` and is reproducible, so a cartridge naming those four
numbers is unambiguous - but a cartridge claiming CCSDS AR4JA conformance would
need that standard's published matrices loaded via :meth:`LDPCCode.from_alist`.
That hook exists; the matrices are not vendored.

Why BP rather than a hard decoder: belief propagation is differentiable when
unrolled as a network, which is what keeps the closure loop of §4 buildable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.bits import hard_decision
from ..core.gf2 import BitMatrix, nullspace, rref

__all__ = ["LDPCCode", "LDPCDecodeResult"]


@dataclass
class LDPCDecodeResult:
    """Outcome of one BP decode."""

    message: np.ndarray
    codeword: np.ndarray
    iterations: int
    converged: bool          #: all parity checks satisfied
    unsatisfied: int         #: how many checks still fail

    @property
    def ok(self) -> bool:
        return self.converged


@dataclass
class LDPCCode:
    """Regular LDPC code over GF(2).

    Parameters
    ----------
    n:
        Codeword length in bits.
    wc, wr:
        Column weight (checks per variable) and row weight (variables per check).
        A ``(3, 6)`` code has rate 1/2; ``(3, 9)`` gives rate 2/3.
    seed:
        Fixes the construction, so ``(n, wc, wr, seed)`` names the code exactly.
    """

    n: int = 1008
    wc: int = 3
    wr: int = 6
    seed: int = 20260919
    _H: np.ndarray = field(init=False, repr=False, compare=False)
    _G: np.ndarray = field(init=False, repr=False, compare=False)
    _info_cols: np.ndarray = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (self.n * self.wc) % self.wr:
            raise ValueError(f"n*wc must be divisible by wr (got {self.n}*{self.wc}/{self.wr})")
        self._H = self._build_H()
        self._build_generator()
        self._build_schedule()

    # ------------------------------------------------------------ construction

    @property
    def m(self) -> int:
        """Number of parity checks."""
        return (self.n * self.wc) // self.wr

    @property
    def k(self) -> int:
        """Message length - the true dimension, after any rank deficiency."""
        return int(self._G.shape[0])

    @property
    def rate(self) -> float:
        return self.k / self.n

    def parity_checks(self) -> np.ndarray:
        """The parity-check matrix H, shape (m, n)."""
        return self._H

    def _build_H(self) -> np.ndarray:
        """Gallager construction: `wc` strips, each a column permutation of the first.

        Strip 0 puts `wr` consecutive ones in each row.  Every later strip is a
        column-permuted copy, so **each column gets exactly one 1 per strip**
        (weight `wc`) and each row exactly `wr`.  Getting this wrong produces
        weight-0 columns - bits that sit in no parity check at all and can never
        be corrected, which shows up as an error floor rather than a waterfall.
        """
        rng = np.random.default_rng(self.seed)
        m, n, wc, wr = self.m, self.n, self.wc, self.wr
        strip_rows = n // wr

        base = np.zeros((strip_rows, n), dtype=np.uint8)
        for i in range(strip_rows):
            base[i, i * wr : (i + 1) * wr] = 1

        H = np.zeros((m, n), dtype=np.uint8)
        H[:strip_rows] = base
        for s in range(1, wc):
            H[s * strip_rows : (s + 1) * strip_rows] = base[:, rng.permutation(n)]

        return self._remove_4cycles(H, rng)

    @staticmethod
    def _remove_4cycles(H: np.ndarray, rng, max_passes: int = 400) -> np.ndarray:
        """Break length-4 cycles with degree-preserving 2-swaps.

        Two variables sharing two checks make BP double-count evidence.  The swap
        moves a 1 from ``(r1,c1)`` to ``(r1,c3)`` and from ``(r3,c3)`` to
        ``(r3,c1)``, so both row and column weights are preserved exactly - a
        naive "move the 1 somewhere else" fix is what destroys regularity.
        """
        m, n = H.shape
        for _ in range(max_passes):
            ov = H.astype(np.int32) @ H.T.astype(np.int32)
            np.fill_diagonal(ov, 0)
            bad = np.argwhere(ov >= 2)
            if len(bad) == 0:
                break
            r1, r2 = bad[rng.integers(len(bad))]
            shared = np.flatnonzero(H[r1] & H[r2])
            c1 = int(shared[0])
            for _try in range(200):
                r3 = int(rng.integers(m))
                if r3 == r1 or r3 == r2 or H[r3, c1]:
                    continue
                cands = np.flatnonzero(H[r3] & (1 - H[r1]))
                if len(cands) == 0:
                    continue
                c3 = int(cands[rng.integers(len(cands))])
                H[r1, c1], H[r1, c3] = 0, 1
                H[r3, c3], H[r3, c1] = 0, 1
                break
        return H

    def _build_generator(self) -> None:
        """G spans the nullspace of H, so every row of G is a codeword."""
        self._G = nullspace(BitMatrix.from_bits(self._H))
        # The nullspace basis carries an identity at the free columns, so those
        # columns are where the message bits land - the code is systematic there.
        reduced, pivots = rref(BitMatrix.from_bits(self._H))
        pivot_set = set(pivots)
        self._info_cols = np.array(
            [c for c in range(self.n) if c not in pivot_set], dtype=np.int64
        )

    def _build_schedule(self) -> None:
        """Pre-index the Tanner graph so BP is fully vectorised."""
        H = self._H
        chk_deg = H.sum(axis=1)
        var_deg = H.sum(axis=0)
        self._regular = bool((chk_deg == chk_deg[0]).all() and (var_deg == var_deg[0]).all())

        chk_vars = [np.flatnonzero(H[r]) for r in range(self.m)]
        self._chk_vars = chk_vars
        maxdeg = int(chk_deg.max())
        self._chk_idx = np.full((self.m, maxdeg), -1, dtype=np.int64)
        for r, vs in enumerate(chk_vars):
            self._chk_idx[r, : len(vs)] = vs
        self._chk_mask = self._chk_idx >= 0
        self._chk_idx_safe = np.where(self._chk_mask, self._chk_idx, 0)

        # Edge ids in check-major order, grouped per variable.
        eid = np.full((self.m, maxdeg), -1, dtype=np.int64)
        eid[self._chk_mask] = np.arange(int(self._chk_mask.sum()))
        self._n_edges = int(self._chk_mask.sum())
        self._edge_var = np.zeros(self._n_edges, dtype=np.int64)
        self._edge_var[eid[self._chk_mask]] = self._chk_idx[self._chk_mask]

        maxvd = int(var_deg.max())
        self._var_eid = np.full((self.n, maxvd), -1, dtype=np.int64)
        fill = np.zeros(self.n, dtype=np.int64)
        for r in range(self.m):
            for j, v in enumerate(chk_vars[r]):
                self._var_eid[v, fill[v]] = eid[r, j]
                fill[v] += 1
        self._var_mask = self._var_eid >= 0
        self._var_eid_safe = np.where(self._var_mask, self._var_eid, 0)

    # --------------------------------------------------------------- encoding

    def encode(self, bits: np.ndarray) -> np.ndarray:
        """Encode exactly `k` message bits into an `n`-bit codeword."""
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        if len(bits) != self.k:
            raise ValueError(f"expected {self.k} message bits, got {len(bits)}")
        return (bits @ self._G) & 1

    def encode_stream(self, bits: np.ndarray) -> np.ndarray:
        """Encode a stream, zero-padding the final block."""
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        pad = (-len(bits)) % self.k
        if pad:
            bits = np.concatenate([bits, np.zeros(pad, np.uint8)])
        return np.concatenate([self.encode(b) for b in bits.reshape(-1, self.k)])

    def extract_message(self, codeword: np.ndarray) -> np.ndarray:
        """Recover the message bits from a codeword (systematic at info columns)."""
        return np.asarray(codeword, dtype=np.uint8)[self._info_cols]

    # --------------------------------------------------------------- decoding

    def decode(
        self, llr: np.ndarray, max_iter: int = 50, alpha: float = 0.75
    ) -> LDPCDecodeResult:
        """Normalised min-sum belief propagation.

        `alpha` compensates min-sum's known overestimate of check-node
        reliability; 0.75 is the usual value and costs nothing to apply.
        """
        llr = np.asarray(llr, dtype=np.float64).reshape(-1)
        if len(llr) != self.n:
            raise ValueError(f"expected {self.n} LLRs, got {len(llr)}")

        v2c = llr[self._edge_var].copy()
        c2v = np.zeros(self._n_edges, dtype=np.float64)
        post = llr.copy()
        it = 0

        for it in range(1, max_iter + 1):
            # --- check nodes: sign product and the two smallest magnitudes
            M = np.where(self._chk_mask, v2c[self._chk_idx_to_edge()], np.inf)
            absM = np.abs(M)
            sgn = np.where(self._chk_mask, np.sign(M), 1.0)
            sgn[sgn == 0] = 1.0
            total_sign = np.prod(sgn, axis=1, keepdims=True)

            order = np.argsort(absM, axis=1)
            min1 = np.take_along_axis(absM, order[:, :1], axis=1)
            min2 = np.take_along_axis(absM, order[:, 1:2], axis=1) if absM.shape[1] > 1 else min1
            is_min = np.zeros_like(absM, dtype=bool)
            np.put_along_axis(is_min, order[:, :1], True, axis=1)
            mag = np.where(is_min, min2, min1)

            out = alpha * (total_sign / sgn) * mag
            out = np.where(self._chk_mask, out, 0.0)
            c2v[self._chk_idx_to_edge()[self._chk_mask]] = out[self._chk_mask]

            # --- variable nodes
            inc = np.where(self._var_mask, c2v[self._var_eid_safe], 0.0)
            post = llr + inc.sum(axis=1)
            new_v2c = post[:, None] - inc
            v2c[self._var_eid_safe[self._var_mask]] = new_v2c[self._var_mask]

            hard = hard_decision(post)
            unsat = int(((self._H @ hard) & 1).sum())
            if unsat == 0:
                return LDPCDecodeResult(self.extract_message(hard), hard, it, True, 0)

        hard = hard_decision(post)
        unsat = int(((self._H @ hard) & 1).sum())
        return LDPCDecodeResult(self.extract_message(hard), hard, it, False, unsat)

    def _chk_idx_to_edge(self) -> np.ndarray:
        """Edge ids laid out check-major, matching ``self._chk_idx``."""
        if not hasattr(self, "_chk_eid"):
            eid = np.full(self._chk_idx.shape, 0, dtype=np.int64)
            eid[self._chk_mask] = np.arange(self._n_edges)
            self._chk_eid = eid
        return self._chk_eid

    # ------------------------------------------------------------------- misc

    @classmethod
    def from_alist(cls, path: str) -> "LDPCCode":  # pragma: no cover - I/O hook
        """Load a published H in MacKay `alist` format.

        The hook by which a standard's real matrices (CCSDS AR4JA, 802.11n) enter
        SHRUTI as *data* rather than code - the same boundary as a cartridge.
        """
        raise NotImplementedError(
            "alist loading is the documented extension point for published LDPC "
            "matrices; no standard matrices are vendored with SHRUTI"
        )

    def describe(self) -> str:
        return (
            f"LDPC ({self.wc},{self.wr})-regular n={self.n} k={self.k} "
            f"rate={self.rate:.3f} seed={self.seed}"
        )
