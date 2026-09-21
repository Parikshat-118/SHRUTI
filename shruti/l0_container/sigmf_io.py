"""SigMF read and write, implemented directly against the specification.

SigMF is JSON metadata beside a raw data file - about two hundred lines to
support properly.  SHRUTI implements it rather than importing ``sigmf-python``
because that binding is **LGPL-3.0**, and keeping every runtime dependency
permissive (BSD/MIT/Apache) matters for adopters in sensitive domains: it is
what lets an organisation fork privately and never publish the fork.

Both directions are supported.  Writing matters as much as reading - a SigMF
recording plus SHRUTI's `shruti:` extension keys is the machine-readable half of
the evidence a finding travels with.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import numpy as np

__all__ = ["read_sigmf", "write_sigmf", "SIGMF_DTYPES"]


#: SigMF `core:datatype` -> (numpy dtype, is_complex)
SIGMF_DTYPES: dict[str, tuple[str, bool]] = {
    "cf32_le": ("<f4", True),
    "cf64_le": ("<f8", True),
    "ci16_le": ("<i2", True),
    "ci8": ("i1", True),
    "cu8": ("u1", True),
    "ci32_le": ("<i4", True),
    "rf32_le": ("<f4", False),
    "ri16_le": ("<i2", False),
    "ri8": ("i1", False),
    "ru8": ("u1", False),
}

_SCALE = {"i1": 128.0, "u1": 128.0, "<i2": 32768.0, "<i4": 2147483648.0}


def _meta_path(path: pathlib.Path) -> pathlib.Path:
    if path.suffix == ".sigmf-meta":
        return path
    if path.suffix == ".sigmf-data":
        return path.with_suffix(".sigmf-meta")
    return path.with_suffix(".sigmf-meta")


def read_sigmf(path: str | pathlib.Path, max_samples: int | None = None):
    """Read a SigMF recording into a :class:`~shruti.l0_container.sniff.Capture`."""
    from .sniff import Capture, ContainerInfo

    p = pathlib.Path(path)
    meta_p = _meta_path(p)
    data_p = meta_p.with_suffix(".sigmf-data")
    if not meta_p.exists():
        raise FileNotFoundError(f"no SigMF metadata beside {p}")

    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    g = meta.get("global", {})
    datatype = g.get("core:datatype", "cf32_le")
    if datatype not in SIGMF_DTYPES:
        raise ValueError(f"unsupported SigMF datatype {datatype!r}")
    np_dt, is_complex = SIGMF_DTYPES[datatype]

    raw = np.memmap(data_p, dtype=np.dtype(np_dt), mode="r")
    if max_samples:
        raw = raw[: max_samples * (2 if is_complex else 1)]
    v = np.asarray(raw, dtype=np.float64)
    scale = _SCALE.get(np_dt)
    if scale:
        v = (v - 128.0) / scale if np_dt == "u1" else v / scale

    if is_complex:
        n = (len(v) // 2) * 2
        samples = (v[0:n:2] + 1j * v[1:n:2]).astype(np.complex128)
    else:
        from ..l4_twin.ssb import analytic_signal
        samples = analytic_signal(v)

    captures = meta.get("captures", [{}])
    info = ContainerInfo(
        path=str(data_p),
        kind="iq" if is_complex else "audio",
        dtype=datatype,
        channels=2 if is_complex else 1,
        is_complex=is_complex,
        sample_rate=float(g.get("core:sample_rate", 0.0)) or None,
        rate_basis="sigmf",
        centre_hz=float(captures[0].get("core:frequency", 0.0)) or None,
        centre_basis="sigmf" if captures and "core:frequency" in captures[0] else "unknown",
        n_samples=len(samples),
    )
    info.add(f"SigMF metadata: {datatype}, {info.sample_rate} Hz")
    if g.get("core:description"):
        info.add(f"description: {g['core:description']}")

    cap = Capture(samples=samples, info=info)
    cap.sigmf = meta                                           # type: ignore[attr-defined]
    return cap


def write_sigmf(
    path: str | pathlib.Path,
    samples: np.ndarray,
    sample_rate: float,
    centre_hz: float | None = None,
    datatype: str = "cf32_le",
    description: str = "",
    author: str = "SHRUTI",
    extensions: dict[str, Any] | None = None,
    annotations: list[dict] | None = None,
) -> pathlib.Path:
    """Write a SigMF recording.  Returns the metadata path.

    `extensions` carries SHRUTI's own namespaced keys - ``shruti:fec``,
    ``shruti:interleaver``, ``shruti:gof_pvalue``, ``shruti:identifiability``
    and so on - so a downstream tool gets the findings, not just the samples.
    """
    p = pathlib.Path(path)
    stem = p.with_suffix("")
    meta_p = stem.with_suffix(".sigmf-meta")
    data_p = stem.with_suffix(".sigmf-data")

    np_dt, is_complex = SIGMF_DTYPES[datatype]
    x = np.asarray(samples)
    if is_complex:
        inter = np.empty(len(x) * 2, dtype=np.float64)
        inter[0::2] = np.real(x)
        inter[1::2] = np.imag(x)
    else:
        inter = np.real(x).astype(np.float64)

    scale = _SCALE.get(np_dt)
    if scale:
        peak = float(np.max(np.abs(inter))) or 1.0
        inter = np.clip(inter / peak * (scale - 1), -(scale - 1), scale - 1)
        if np_dt == "u1":
            inter = inter + 128.0
    inter.astype(np.dtype(np_dt)).tofile(data_p)

    meta: dict[str, Any] = {
        "global": {
            "core:datatype": datatype,
            "core:sample_rate": float(sample_rate),
            "core:version": "1.0.0",
            "core:author": author,
            "core:description": description,
            "core:recorder": "SHRUTI twin",
        },
        "captures": [{"core:sample_start": 0}],
        "annotations": list(annotations or []),
    }
    if centre_hz is not None:
        meta["captures"][0]["core:frequency"] = float(centre_hz)
    if extensions:
        meta["global"].update(extensions)

    meta_p.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta_p
