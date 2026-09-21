"""Cartridge schema, validation and block construction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = ["Cartridge", "CartridgeError", "parse_int", "BLOCK_ORDER"]


class CartridgeError(ValueError):
    """A cartridge is malformed or names something SHRUTI cannot build."""


#: Canonical transmit order.  A cartridge may omit blocks but may not reorder
#: them.
#:
#: There are **two scrambler slots**, and that is not redundancy - real standards
#: genuinely disagree about where scrambling belongs:
#:
#:   * CCSDS 131.0-B randomises *between* the outer and inner codes
#:     (RS encode -> interleave -> pseudo-randomise -> attach ASM -> conv encode),
#:     which is the ``scrambler`` slot.
#:   * MIL-STD-188-110A and most HF modems scramble *after* interleaving, just
#:     before the mapper, which is the ``scrambler_post`` slot.
#:
#: A tool that assumes one position will fail on the other half of real traffic
#: for reasons it cannot diagnose, because a scrambled stream and a descrambled
#: one are statistically identical until a parity check is tested.
BLOCK_ORDER = [
    "source",
    "crc",
    "fec_outer",
    "interleaver_outer",
    "scrambler",
    "sync",
    "fec",
    "interleaver",
    "scrambler_post",
    "mapper",
    "shaping",
    "modulator",
]


def parse_int(v: Any) -> int:
    """Accept ``0o133``, ``0x1F``, ``0b1011``, ``"133"`` or a plain int.

    YAML 1.1 (which PyYAML implements) does not agree with YAML 1.2 about octal
    literals, and generator polynomials are conventionally written in octal.
    Rather than depend on which resolver fires, accept the string forms too.
    """
    if isinstance(v, bool):
        raise CartridgeError(f"expected an integer, got boolean {v!r}")
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float) and float(v).is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip().replace("_", "")
        try:
            if s.lower().startswith("0o"):
                return int(s[2:], 8)
            if s.lower().startswith("0x"):
                return int(s[2:], 16)
            if s.lower().startswith("0b"):
                return int(s[2:], 2)
            return int(s, 10)
        except ValueError as exc:
            raise CartridgeError(f"cannot parse integer from {v!r}") from exc
    raise CartridgeError(f"cannot parse integer from {v!r}")


def _parse_rate(v: Any) -> str:
    """Accept ``1/2``, ``0.5`` or ``"1/2"`` and normalise to the string form."""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        for r in ("1/2", "2/3", "3/4", "5/6", "7/8"):
            a, b = r.split("/")
            if abs(float(v) - int(a) / int(b)) < 1e-6:
                return r
    raise CartridgeError(f"unrecognised code rate {v!r}")


@dataclass
class Cartridge:
    """A declarative waveform definition."""

    id: str
    band: str = "unknown"
    name: str = ""
    blocks: dict[str, dict] = field(default_factory=dict)
    priors: dict[str, dict] = field(default_factory=dict)
    identifiability: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    # ------------------------------------------------------------- validation

    @classmethod
    def from_dict(cls, d: dict, source_path: str | None = None) -> "Cartridge":
        if "id" not in d:
            raise CartridgeError("cartridge is missing required key 'id'")

        raw_chain = d.get("chain", [])
        if not isinstance(raw_chain, list):
            raise CartridgeError("'chain' must be a list of single-key blocks")

        blocks: dict[str, dict] = {}
        seen_order: list[str] = []
        for item in raw_chain:
            if not isinstance(item, dict) or len(item) != 1:
                raise CartridgeError(
                    f"each chain entry must be a single-key mapping, got {item!r}"
                )
            (key, val), = item.items()
            if key not in BLOCK_ORDER:
                raise CartridgeError(
                    f"unknown chain block {key!r}; expected one of {BLOCK_ORDER}"
                )
            if key in blocks:
                raise CartridgeError(f"duplicate chain block {key!r}")
            blocks[key] = dict(val or {})
            seen_order.append(key)

        canonical = [b for b in BLOCK_ORDER if b in blocks]
        if seen_order != canonical:
            raise CartridgeError(
                f"chain blocks are out of order.\n  got:      {seen_order}\n"
                f"  expected: {canonical}\n"
                "Transmit order is fixed because it is the order real systems use."
            )

        return cls(
            id=str(d["id"]),
            band=str(d.get("band", "unknown")),
            name=str(d.get("name", d["id"])),
            blocks=blocks,
            priors=dict(d.get("priors", {}) or {}),
            identifiability=dict(d.get("identifiability", {}) or {}),
            meta={k: v for k, v in d.items()
                  if k not in ("id", "band", "name", "chain", "priors", "identifiability")},
            source_path=source_path,
        )

    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means valid."""
        problems: list[str] = []
        if "mapper" not in self.blocks:
            problems.append("no 'mapper' block - nothing to modulate")
        if "modulator" not in self.blocks:
            problems.append("no 'modulator' block - no symbol rate given")
        else:
            if "symbol_rate_bd" not in self.blocks["modulator"]:
                problems.append("modulator has no 'symbol_rate_bd'")

        for name, builder in (
            ("fec", self.build_fec),
            ("fec_outer", self.build_fec_outer),
            ("interleaver", self.build_interleaver),
            ("scrambler", self.build_scrambler),
            ("scrambler_post", self.build_scrambler_post),
            ("interleaver_outer", self.build_interleaver_outer),
            ("mapper", self.build_mapper),
        ):
            if name in self.blocks:
                try:
                    builder()
                except Exception as exc:                      # noqa: BLE001
                    problems.append(f"block '{name}' does not build: {exc}")
        return problems

    # -------------------------------------------------------------- accessors

    @property
    def symbol_rate(self) -> float:
        return float(self.blocks.get("modulator", {}).get("symbol_rate_bd", 0.0))

    @property
    def centre_hz(self) -> float:
        return float(self.blocks.get("modulator", {}).get("centre_hz", 0.0))

    @property
    def ssb(self) -> str | None:
        v = self.blocks.get("modulator", {}).get("ssb")
        return str(v).lower() if v else None

    @property
    def rolloff(self) -> float:
        return float(self.blocks.get("shaping", {}).get("rolloff", 0.35))

    # --------------------------------------------------------------- builders

    def build_mapper(self):
        from ..l4_twin.modulation import build as build_mod
        if "mapper" not in self.blocks:
            raise CartridgeError("cartridge has no mapper block")
        return build_mod(self.blocks["mapper"])

    def _build_code(self, spec: dict):
        from ..l6_fec.conv import ConvCode
        from ..l6_fec.ldpc import LDPCCode
        from ..l6_fec.rs import ReedSolomon
        from ..l6_fec.gf256 import GF256, GF_CONVENTIONAL

        kind = str(spec.get("type", "none")).lower()
        if kind in ("none", ""):
            return None
        if kind in ("convolutional", "convolution", "conv"):
            polys = tuple(parse_int(p) for p in spec.get("poly", [0o171, 0o133]))
            inv = spec.get("invert", [False] * len(polys))
            if isinstance(inv, bool):
                inv = [inv] * len(polys)
            return ConvCode(
                K=parse_int(spec.get("K", 7)),
                polys=polys,
                invert=tuple(bool(x) for x in inv),
                rate=_parse_rate(spec.get("rate", "1/2")),
            )
        if kind in ("rs", "reed_solomon", "reed-solomon"):
            poly = spec.get("field_poly")
            gf = GF256(parse_int(poly)) if poly is not None else GF_CONVENTIONAL
            return ReedSolomon(
                n=parse_int(spec.get("n", 255)),
                k=parse_int(spec.get("k", 223)),
                fcr=parse_int(spec.get("fcr", 0)),
                prim=parse_int(spec.get("prim", 1)),
                gf=gf,
            )
        if kind == "ldpc":
            return LDPCCode(
                n=parse_int(spec.get("n", 1008)),
                wc=parse_int(spec.get("wc", 3)),
                wr=parse_int(spec.get("wr", 6)),
                seed=parse_int(spec.get("seed", 20260919)),
            )
        raise CartridgeError(f"unknown FEC type {kind!r}")

    def build_fec(self):
        return self._build_code(self.blocks["fec"]) if "fec" in self.blocks else None

    def build_fec_outer(self):
        return self._build_code(self.blocks["fec_outer"]) if "fec_outer" in self.blocks else None

    def _build_interleaver(self, key: str):
        from ..l6_fec.interleave import build as build_il
        if key not in self.blocks:
            return None
        spec = dict(self.blocks[key])
        for k in ("rows", "cols", "branches", "delay", "size", "seed"):
            if k in spec:
                spec[k] = parse_int(spec[k])
        return build_il(spec)

    def build_interleaver(self):
        return self._build_interleaver("interleaver")

    def build_interleaver_outer(self):
        return self._build_interleaver("interleaver_outer")

    def _build_scrambler(self, key: str):
        from ..l6_fec.scramble import build as build_sc
        if key not in self.blocks:
            return None
        spec = dict(self.blocks[key])
        for k in ("poly", "seed", "width"):
            if k in spec:
                spec[k] = parse_int(spec[k])
        if "taps" in spec:
            spec["taps"] = tuple(parse_int(t) for t in spec["taps"])
        return build_sc(spec)

    def build_scrambler(self):
        """The inter-code scrambler (CCSDS pseudo-randomiser position)."""
        return self._build_scrambler("scrambler")

    def build_scrambler_post(self):
        """The post-interleave scrambler (MIL-STD / HF modem position)."""
        return self._build_scrambler("scrambler_post")

    def sync_word(self) -> np.ndarray | None:
        """The attached sync marker, as bits, if the cartridge declares one."""
        if "sync" not in self.blocks:
            return None
        spec = self.blocks["sync"]
        if "bits" in spec:
            return np.array([int(b) for b in str(spec["bits"]).strip()], dtype=np.uint8)
        if "hex" in spec:
            raw = str(spec["hex"]).replace("0x", "").replace("_", "")
            val = bytes.fromhex(raw if len(raw) % 2 == 0 else "0" + raw)
            return np.unpackbits(np.frombuffer(val, dtype=np.uint8))
        raise CartridgeError("sync block needs either 'bits' or 'hex'")

    @property
    def sync_period(self) -> int | None:
        """Bits between successive sync markers, if declared."""
        v = self.blocks.get("sync", {}).get("period_bits")
        return int(v) if v is not None else None

    # ----------------------------------------------------------------- digest

    def digest(self) -> str:
        """Stable content hash, recorded in every attestation bundle.

        This is what makes a finding re-derivable: the bundle names the exact
        cartridge content that produced it, so a later change to the library
        cannot silently invalidate an archived conclusion.
        """
        payload = json.dumps(
            {
                "id": self.id,
                "band": self.band,
                "blocks": self.blocks,
                "priors": self.priors,
                "identifiability": self.identifiability,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def describe(self) -> str:
        parts = []
        for key in BLOCK_ORDER:
            if key not in self.blocks:
                continue
            b = self.blocks[key]
            if key == "mapper":
                parts.append(f"{b.get('type','?')}-{b.get('order','?')}")
            elif key in ("fec", "fec_outer"):
                parts.append(f"{b.get('type','?')} {b.get('rate', '')}".strip())
            elif key == "interleaver":
                parts.append(f"{b.get('type','?')} interleaver")
            elif key == "scrambler":
                parts.append(f"{b.get('type','?')} scrambler")
        chain = " -> ".join(p for p in parts if p)
        return f"{self.id} [{self.band}] {chain} @ {self.symbol_rate:g} Bd"
