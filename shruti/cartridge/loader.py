"""Loading cartridges from YAML, and the library that L6 track A searches."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import yaml

from .schema import Cartridge, CartridgeError

__all__ = ["load_cartridge", "load_library", "CartridgeLibrary", "default_library_path"]


def default_library_path() -> pathlib.Path:
    """The ``cartridges/`` directory shipped alongside the package."""
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "cartridges"
        if cand.is_dir():
            return cand
    return here.parent / "cartridges"


def load_cartridge(path: str | pathlib.Path) -> Cartridge:
    """Load and validate one cartridge file."""
    p = pathlib.Path(path)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CartridgeError(f"{p.name}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CartridgeError(f"{p.name}: top level must be a mapping")

    cart = Cartridge.from_dict(data, source_path=str(p))
    problems = cart.validate()
    if problems:
        joined = "\n  - ".join(problems)
        raise CartridgeError(f"{p.name}: cartridge is invalid:\n  - {joined}")
    return cart


@dataclass
class CartridgeLibrary:
    """A loaded set of cartridges, which is what L6 track A matches against.

    The library is *data*, licensed separately from the engine (CC-BY-4.0), which
    is what lets an agency hold restricted or classified cartridges privately
    without forking the code.
    """

    cartridges: list[Cartridge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cartridges)

    def __iter__(self):
        return iter(self.cartridges)

    def by_id(self, cid: str) -> Cartridge | None:
        for c in self.cartridges:
            if c.id == cid:
                return c
        return None

    def by_band(self, band: str) -> list[Cartridge]:
        b = band.lower()
        return [c for c in self.cartridges if c.band.lower() == b]

    def without(self, cid: str) -> "CartridgeLibrary":
        """A copy with one cartridge removed.

        This backs the **hold-out** mode of the self-test: analyse a waveform
        whose cartridge is absent from the analyser's library, so track A cannot
        match and the blind reconstruction tracks must do the work.  It is how
        the blind path is exercised on a waveform the tool has never seen.
        """
        return CartridgeLibrary(
            cartridges=[c for c in self.cartridges if c.id != cid],
            errors=list(self.errors),
        )

    def summary(self) -> str:
        bands: dict[str, int] = {}
        for c in self.cartridges:
            bands[c.band] = bands.get(c.band, 0) + 1
        parts = ", ".join(f"{v} {k}" for k, v in sorted(bands.items()))
        return f"{len(self.cartridges)} cartridges ({parts})"


def load_library(
    path: str | pathlib.Path | None = None, strict: bool = False
) -> CartridgeLibrary:
    """Load every ``*.yaml`` under `path`, recursively.

    Malformed cartridges are collected into ``.errors`` rather than aborting the
    load, unless `strict`.  A library is a long tail maintained by people who are
    not the engine's authors, so one bad file must not take the tool down - but
    ``shruti cartridge validate`` exists to make the failure loud on demand.
    """
    root = pathlib.Path(path) if path is not None else default_library_path()
    lib = CartridgeLibrary()
    if not root.is_dir():
        return lib

    for f in sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")):
        try:
            lib.cartridges.append(load_cartridge(f))
        except CartridgeError as exc:
            if strict:
                raise
            lib.errors.append(str(exc))
    return lib
