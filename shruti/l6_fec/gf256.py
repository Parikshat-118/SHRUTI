"""Arithmetic over GF(256), the field Reed-Solomon lives in.

The field is parameterised by its primitive polynomial because the two standards
SHRUTI cares about do not agree:

* **Conventional / DVB / most literature** - ``0x11D`` (x^8 + x^4 + x^3 + x^2 + 1)
* **CCSDS 131.0-B** - ``0x187`` (x^8 + x^7 + x^2 + x + 1), with first consecutive
  root 112 and primitive element alpha^11

Honest limitation, stated here rather than buried: CCSDS additionally specifies a
**dual-basis** representation for the code symbols.  SHRUTI implements the
conventional (power/polynomial) basis only.  A CCSDS cartridge therefore carries
``basis: conventional`` and is bit-exact against itself and against any
conventional-basis implementation, but a true CCSDS ground-station capture would
need the dual-basis transform applied first.  That transform is an 8x8 binary
matrix and is a known gap, not a hidden one.
"""

from __future__ import annotations

import numpy as np

__all__ = ["GF256", "GF_CONVENTIONAL", "GF_CCSDS"]


class GF256:
    """Tabulated GF(2^8).  Multiplication is a table lookup on logarithms."""

    __slots__ = ("prim_poly", "exp", "log", "_mul_tbl")

    def __init__(self, prim_poly: int = 0x11D) -> None:
        self.prim_poly = prim_poly
        exp = np.zeros(512, dtype=np.uint8)
        log = np.zeros(256, dtype=np.uint8)

        x = 1
        for i in range(255):
            exp[i] = x
            log[x] = i
            x <<= 1
            if x & 0x100:
                x ^= prim_poly
        exp[255:510] = exp[0:255]
        exp[510] = exp[0]
        exp[511] = exp[1]

        self.exp = exp
        self.log = log
        self._mul_tbl: np.ndarray | None = None

    # ---------------------------------------------------------------- scalars

    def mul(self, a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return int(self.exp[(int(self.log[a]) + int(self.log[b])) % 255])

    def div(self, a: int, b: int) -> int:
        if b == 0:
            raise ZeroDivisionError("GF(256) division by zero")
        if a == 0:
            return 0
        return int(self.exp[(int(self.log[a]) - int(self.log[b])) % 255])

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError("GF(256) inverse of zero")
        return int(self.exp[(255 - int(self.log[a])) % 255])

    def pow(self, a: int, n: int) -> int:
        if a == 0:
            return 0
        return int(self.exp[(int(self.log[a]) * n) % 255])

    # ------------------------------------------------------------ polynomials

    def poly_mul(self, p: np.ndarray, q: np.ndarray) -> np.ndarray:
        """Multiply two polynomials, coefficients highest-order first."""
        out = np.zeros(len(p) + len(q) - 1, dtype=np.uint8)
        for i, pi in enumerate(p):
            if pi == 0:
                continue
            lpi = int(self.log[pi])
            for j, qj in enumerate(q):
                if qj:
                    out[i + j] ^= self.exp[(lpi + int(self.log[qj])) % 255]
        return out

    def poly_eval(self, p: np.ndarray, x: int) -> int:
        """Horner evaluation."""
        y = 0
        for c in p:
            y = self.mul(y, x) ^ int(c)
        return y

    def poly_scale(self, p: np.ndarray, s: int) -> np.ndarray:
        if s == 0:
            return np.zeros_like(p)
        ls = int(self.log[s])
        out = np.zeros_like(p)
        nz = p != 0
        out[nz] = self.exp[(self.log[p[nz]].astype(int) + ls) % 255]
        return out

    @staticmethod
    def poly_add(p: np.ndarray, q: np.ndarray) -> np.ndarray:
        n = max(len(p), len(q))
        out = np.zeros(n, dtype=np.uint8)
        out[n - len(p):] ^= p
        out[n - len(q):] ^= q
        return out

    def poly_mod(self, dividend: np.ndarray, divisor: np.ndarray) -> np.ndarray:
        """Remainder of polynomial division."""
        out = np.array(dividend, dtype=np.uint8, copy=True)
        dlen = len(divisor)
        lead_inv_log = int(self.log[divisor[0]])
        for i in range(len(dividend) - dlen + 1):
            coef = int(out[i])
            if coef == 0:
                continue
            f = (int(self.log[coef]) - lead_inv_log) % 255
            for j in range(1, dlen):
                if divisor[j]:
                    out[i + j] ^= self.exp[(int(self.log[divisor[j]]) + f) % 255]
        return out[-(dlen - 1):]


GF_CONVENTIONAL = GF256(0x11D)
GF_CCSDS = GF256(0x187)
