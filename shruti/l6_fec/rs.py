"""Reed-Solomon block codes.

Systematic RS(n, k) over GF(256) with Berlekamp-Massey error location, Chien
search and Forney error evaluation.  The two codes CCSDS 131.0-B specifies are
provided by name:

* ``RS(255, 223)`` - corrects up to **16** symbol errors  (E = 16)
* ``RS(255, 239)`` - corrects up to **8** symbol errors   (E = 8)

Why RS matters beyond the decode itself: it is the **outer** half of the
concatenated arrangement, and the number of symbol errors it
corrected is a directly reportable quality measurement - *"RS(255,223)
de-interleaved at depth 5, 11 symbol errors corrected"* is a sentence an analyst
can act on, and it is evidence that everything upstream was estimated correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .gf256 import GF256, GF_CONVENTIONAL

__all__ = ["ReedSolomon", "RS_255_223", "RS_255_239", "RSDecodeResult"]


@dataclass
class RSDecodeResult:
    """Outcome of one RS block decode."""

    message: np.ndarray
    corrected: int          #: symbol errors repaired, -1 if the block failed
    ok: bool
    positions: tuple[int, ...] = ()

    @property
    def failed(self) -> bool:
        return not self.ok


@dataclass
class ReedSolomon:
    """Systematic RS(n, k) over GF(256).

    Parameters
    ----------
    n, k:
        Block length and message length in symbols.  ``n - k = 2t`` parity
        symbols correct up to ``t`` symbol errors.
    fcr:
        First consecutive root exponent.  0 or 1 conventionally; **112** for CCSDS.
    prim:
        Step between consecutive roots.  1 conventionally; **11** for CCSDS.
    gf:
        The GF(256) instance, which fixes the primitive polynomial.
    """

    n: int = 255
    k: int = 223
    fcr: int = 0
    prim: int = 1
    gf: GF256 = field(default_factory=lambda: GF_CONVENTIONAL)
    _gen: np.ndarray = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not 0 < self.k < self.n <= 255:
            raise ValueError(f"invalid RS parameters n={self.n} k={self.k}")
        self._gen = self._generator()

    @property
    def nsym(self) -> int:
        """Number of parity symbols, 2t."""
        return self.n - self.k

    @property
    def t(self) -> int:
        """Correction capability in symbols."""
        return self.nsym // 2

    def _root(self, i: int) -> int:
        return self.gf.pow(2, self.fcr + i * self.prim)

    def _generator(self) -> np.ndarray:
        g = np.array([1], dtype=np.uint8)
        for i in range(self.nsym):
            g = self.gf.poly_mul(g, np.array([1, self._root(i)], dtype=np.uint8))
        return g

    # --------------------------------------------------------------- encoding

    def encode_block(self, msg: np.ndarray) -> np.ndarray:
        """Encode exactly `k` symbols into `n`.  Systematic: message then parity."""
        msg = np.asarray(msg, dtype=np.uint8).reshape(-1)
        if len(msg) != self.k:
            raise ValueError(f"expected {self.k} symbols, got {len(msg)}")
        padded = np.concatenate([msg, np.zeros(self.nsym, np.uint8)])
        parity = self.gf.poly_mod(padded, self._gen)
        return np.concatenate([msg, parity])

    def encode(self, data: np.ndarray) -> np.ndarray:
        """Encode a byte stream, zero-padding the final block."""
        data = np.asarray(data, dtype=np.uint8).reshape(-1)
        pad = (-len(data)) % self.k
        if pad:
            data = np.concatenate([data, np.zeros(pad, np.uint8)])
        return np.concatenate([self.encode_block(b) for b in data.reshape(-1, self.k)])

    # --------------------------------------------------------------- decoding

    def _syndromes(self, r: np.ndarray) -> np.ndarray:
        return np.array(
            [self.gf.poly_eval(r, self._root(i)) for i in range(self.nsym)],
            dtype=np.uint8,
        )

    def _berlekamp_massey(self, synd: np.ndarray) -> np.ndarray:
        """Return the error-locator polynomial, highest order first."""
        gf = self.gf
        sigma = np.array([1], dtype=np.uint8)
        old = np.array([1], dtype=np.uint8)

        for i in range(self.nsym):
            delta = int(synd[i])
            for j in range(1, len(sigma)):
                delta ^= gf.mul(int(sigma[len(sigma) - 1 - j]), int(synd[i - j]))

            old = np.concatenate([old, np.zeros(1, np.uint8)])
            if delta != 0:
                if len(old) > len(sigma):
                    new = gf.poly_scale(old, delta)
                    old = gf.poly_scale(sigma, gf.inv(delta))
                    sigma = new
                sigma = gf.poly_add(sigma, gf.poly_scale(old, delta))

        sigma = np.trim_zeros(sigma, "f")
        return sigma if len(sigma) else np.array([1], dtype=np.uint8)

    def _chien(self, sigma: np.ndarray) -> list[int]:
        """Roots of the locator give the error positions."""
        gf = self.gf
        errs = []
        for i in range(self.n):
            if gf.poly_eval(sigma, gf.pow(2, (255 - i) % 255)) == 0:
                errs.append(self.n - 1 - i)
        return errs

    def _forney(self, synd: np.ndarray, sigma: np.ndarray, positions: list[int]) -> np.ndarray:
        """Error magnitudes at the located positions.

        ``e_j = X_j^(1-fcr) * omega(X_j^-1) / sigma'(X_j^-1)``.
        """
        gf = self.gf

        # Error evaluator: omega(x) = [S(x) . sigma(x)] mod x^nsym.
        omega = gf.poly_mul(synd[::-1], sigma)[-self.nsym:]

        # Formal derivative in characteristic 2: only odd-degree terms survive.
        # With `sigma` highest-order-first, sigma[j] is the coefficient of
        # x^(deg-j), so it contributes iff (deg - j) is odd.
        deg = len(sigma) - 1
        dsig = np.zeros(max(deg, 1), dtype=np.uint8)
        for j in range(deg):
            if (deg - j) % 2 == 1:
                dsig[j] = sigma[j]

        mags = np.zeros(len(positions), dtype=np.uint8)
        for idx, p in enumerate(positions):
            xi = gf.pow(2, (self.n - 1 - p) % 255)
            xi_inv = gf.inv(xi)
            den = gf.poly_eval(dsig, xi_inv)
            if den == 0:
                continue
            val = gf.div(gf.poly_eval(omega, xi_inv), den)
            mags[idx] = gf.mul(val, gf.pow(xi, 1 - self.fcr)) if self.fcr != 1 else val
        return mags

    def decode_block(self, received: np.ndarray) -> RSDecodeResult:
        """Decode one `n`-symbol block."""
        r = np.asarray(received, dtype=np.uint8).reshape(-1).copy()
        if len(r) != self.n:
            raise ValueError(f"expected {self.n} symbols, got {len(r)}")

        synd = self._syndromes(r)
        if not synd.any():
            return RSDecodeResult(r[: self.k], 0, True)

        sigma = self._berlekamp_massey(synd)
        nerr = len(sigma) - 1
        if nerr == 0 or nerr > self.t:
            return RSDecodeResult(r[: self.k], -1, False)

        positions = self._chien(sigma)
        if len(positions) != nerr:
            return RSDecodeResult(r[: self.k], -1, False)

        mags = self._forney(synd, sigma, positions)
        for p, m in zip(positions, mags):
            if 0 <= p < self.n:
                r[p] ^= m

        if self._syndromes(r).any():
            return RSDecodeResult(r[: self.k], -1, False)
        return RSDecodeResult(r[: self.k], len(positions), True, tuple(sorted(positions)))

    def decode(self, stream: np.ndarray) -> tuple[np.ndarray, int, int]:
        """Decode a stream of blocks.  Returns ``(message, corrected, failed)``."""
        stream = np.asarray(stream, dtype=np.uint8).reshape(-1)
        nblocks = len(stream) // self.n
        out, corrected, failed = [], 0, 0
        for b in stream[: nblocks * self.n].reshape(-1, self.n):
            res = self.decode_block(b)
            out.append(res.message)
            if res.ok:
                corrected += res.corrected
            else:
                failed += 1
        msg = np.concatenate(out) if out else np.zeros(0, np.uint8)
        return msg, corrected, failed

    def describe(self) -> str:
        return f"RS({self.n},{self.k}) over GF(256), t={self.t}"


#: CCSDS-parameterised block lengths, conventional basis (see gf256 docstring).
RS_255_223 = ReedSolomon(n=255, k=223)
RS_255_239 = ReedSolomon(n=255, k=239)
