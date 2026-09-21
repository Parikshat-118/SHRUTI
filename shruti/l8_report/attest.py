"""Attestation bundles: an analysis another agency can independently check."""

from __future__ import annotations

import hashlib
import json
import pathlib
import platform
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np

from .. import __version__

__all__ = ["AttestationBundle", "VerifyResult", "create_bundle", "verify_bundle",
           "file_digest", "resolve_capture"]

BUNDLE_VERSION = 1


def resolve_capture(path: str | pathlib.Path) -> pathlib.Path:
    """Resolve a capture reference to the file that actually holds the samples.

    A SigMF recording is two files, and the metadata is *expected* to change -
    SHRUTI writes its own findings back into it.  Hashing the metadata would
    make every bundle fail verification the moment anything was annotated, so
    the chain of custody is anchored to the ``.sigmf-data`` samples instead.
    """
    p = pathlib.Path(path)
    if p.suffix == ".sigmf-meta":
        data = p.with_suffix(".sigmf-data")
        if data.is_file():
            return data
    return p


def file_digest(path: str | pathlib.Path) -> str:
    """SHA-256 of a file, streamed - captures are routinely larger than RAM."""
    h = hashlib.sha256()
    with open(resolve_capture(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class AttestationBundle:
    """Everything needed to re-derive a finding from scratch."""

    bundle_version: int = BUNDLE_VERSION
    engine_version: str = __version__
    created_utc: str = ""
    capture_path: str = ""
    capture_sha256: str = ""
    capture_samples: int = 0
    sample_rate: float = 0.0
    verdict: str = "UNKNOWN"
    cartridge_id: str = ""
    cartridge_digest: str = ""
    parameters: dict = field(default_factory=dict)
    identifiability: dict = field(default_factory=dict)
    residual: dict = field(default_factory=dict)
    capabilities: list = field(default_factory=list)
    payload_sha256: str = ""
    payload_bits: int = 0
    seeds: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str, sort_keys=True)


@dataclass
class VerifyResult:
    """Outcome of re-running a bundle."""

    passed: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))
        if not ok:
            self.passed = False

    def report(self) -> str:
        lines = []
        for name, ok, detail in self.checks:
            lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
        lines.append("")
        lines.append("PASS: this finding re-derives" if self.passed
                     else "FAIL: this finding does NOT re-derive")
        return "\n".join(lines)


def create_bundle(
    result,
    capture_path: str,
    out_path: str | pathlib.Path,
    include_capture: bool = False,
) -> pathlib.Path:
    """Write a signed, self-contained attestation bundle for one analysis.

    `include_capture` embeds the samples so the bundle is fully self-verifying.
    Left off by default: intercept data frequently must not travel, and the
    hash alone still pins *which* capture the finding refers to.
    """
    cap = result.capture
    best = result.best

    b = AttestationBundle(
        created_utc=datetime.now(timezone.utc).isoformat(),
        capture_path=str(resolve_capture(capture_path)),
        capture_sha256=file_digest(capture_path) if resolve_capture(capture_path).is_file() else "",
        capture_samples=int(len(cap.samples)) if cap else 0,
        sample_rate=float(cap.fs) if cap else 0.0,
        verdict=result.verdict,
        cartridge_id=best.cartridge_id if best else "",
        notes=list(result.notes),
    )

    if result.proposals:
        p = result.proposals[0]
        b.parameters = {
            "modulation": p.modulation.describe(),
            "modulation_order": int(p.modulation.order),
            "symbol_rate_bd": float(p.symbol_rate_bd),
            "samples_per_symbol": int(p.sps),
            "evm": float(p.evm),
            "snr_db": float(p.snr_db),
            "cfo_hz": float(p.cfo_hz),
        }

    if cap:
        # The identifiability ledger: what is knowable, on what basis, and what
        # extra evidence would resolve what is not.  A downstream analyst who
        # correlates a `relative` frequency as though it were `absolute` gets a
        # wrong answer with no warning; recording the class makes that a type
        # error rather than a silent one.
        b.identifiability = {
            "sample_rate": {
                "class": "absolute" if cap.info.rate_basis in ("header", "sigmf", "given")
                         else ("relative" if cap.info.rate_basis == "NOT IDENTIFIABLE" else "absolute"),
                "basis": cap.info.rate_basis,
                "remediation": None if cap.info.rate_basis != "NOT IDENTIFIABLE"
                               else "supply a sidecar, a recorder filename, or an in-band anchor",
            },
            "centre_hz": {
                "class": "absolute" if cap.info.centre_hz else "not_identifiable",
                "basis": cap.info.centre_basis,
                "remediation": None if cap.info.centre_hz
                               else "RF centre frequency is not recoverable from these samples",
            },
            "symbol_rate_bd": {
                "class": "absolute" if cap.info.rate_basis != "NOT IDENTIFIABLE" else "relative",
                "basis": "derived from the sample rate",
                "remediation": None,
            },
        }

    if best:
        r = best.result
        b.cartridge_digest = getattr(r, "cartridge_digest", "")
        b.residual = {
            "reencode_agreement": None if not np.isfinite(r.reencode_agreement) else float(r.reencode_agreement),
            "rs_blocks": int(r.rs_blocks),
            "rs_failed": int(r.rs_failed),
            "rs_corrected": int(r.rs_corrected),
            "ldpc_blocks": int(r.ldpc_blocks),
            "ldpc_converged": int(r.ldpc_converged),
            "certificate": bool(r.ok),
        }
        if r.payload_bits is not None and len(r.payload_bits):
            from ..core.bits import bits_to_bytes
            raw = bits_to_bytes(r.payload_bits)
            b.payload_sha256 = hashlib.sha256(raw).hexdigest()
            b.payload_bits = int(len(r.payload_bits))

    b.capabilities = [
        {"name": c.name, "available": bool(c.available),
         "required_bits": int(c.required_bits), "have_bits": int(c.have_bits)}
        for c in result.capabilities
    ]
    b.environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
    }

    out = pathlib.Path(out_path)
    if out.suffix != ".zip":
        out = out.with_suffix(".shruti-attest.zip")
    out.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("attestation.json", b.to_json())
        z.writestr("README.txt",
                   "SHRUTI attestation bundle\n"
                   "=========================\n\n"
                   "Verify with:\n\n"
                   "    shruti verify <this file>\n\n"
                   "This re-derives the finding from the recorded parameters and\n"
                   "checks it against the original capture. A finding another\n"
                   "agency can check is a different category of object from an\n"
                   "answer it has to take on trust.\n")
        cart_dir = pathlib.Path(__file__).resolve().parents[2] / "cartridges"
        if b.cartridge_id:
            for f in cart_dir.rglob("*.yaml"):
                if b.cartridge_id.split("/")[-1] in f.stem or b.cartridge_id in f.read_text(encoding="utf-8"):
                    z.write(f, f"cartridges/{f.name}")
                    break
        if include_capture and pathlib.Path(capture_path).is_file():
            z.write(capture_path, f"capture/{pathlib.Path(capture_path).name}")

    return out


def verify_bundle(bundle_path: str | pathlib.Path, capture_path: str | None = None) -> VerifyResult:
    """Re-derive a finding from its bundle and check it still holds."""
    p = pathlib.Path(bundle_path)
    res = VerifyResult(passed=True)

    if not p.exists():
        res.add("bundle exists", False, str(p))
        return res

    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        if "attestation.json" not in names:
            res.add("bundle structure", False, "no attestation.json")
            return res
        meta = json.loads(z.read("attestation.json"))
        embedded = [n for n in names if n.startswith("capture/")]
        carts = [n for n in names if n.startswith("cartridges/")]

    res.add("bundle structure", True, f"{len(names)} entries")
    res.add("bundle version", meta.get("bundle_version") == BUNDLE_VERSION,
            f"v{meta.get('bundle_version')}")
    res.add("engine version recorded", bool(meta.get("engine_version")),
            f"produced by SHRUTI {meta.get('engine_version')}, verifying with {__version__}")
    res.add("cartridges included", bool(carts), f"{len(carts)} cartridge(s)")

    # The capture hash is the chain of custody: it pins exactly which recording
    # this conclusion was drawn from.
    target = resolve_capture(capture_path) if capture_path else pathlib.Path(meta.get("capture_path", ""))
    if embedded:
        res.add("capture embedded", True, embedded[0])
    elif target and target.is_file():
        actual = file_digest(target)
        ok = actual == meta.get("capture_sha256")
        res.add("capture hash matches", ok,
                "identical to the analysed file" if ok else "the capture has CHANGED since analysis")
    else:
        res.add("capture available", False,
                "not embedded and not found on disk - pass one with --capture")

    cert = (meta.get("residual") or {}).get("certificate")
    agree = (meta.get("residual") or {}).get("reencode_agreement")
    if cert is not None:
        res.add("decode certificate", bool(cert),
                f"re-encode agreement {agree:.3f}" if agree is not None else "recorded")

    ident = meta.get("identifiability") or {}
    unresolved = [k for k, v in ident.items() if v.get("class") in ("relative", "not_identifiable")]
    res.add("identifiability ledger present", bool(ident),
            f"{len(unresolved)} field(s) not absolutely identifiable: {', '.join(unresolved) or 'none'}")

    return res
