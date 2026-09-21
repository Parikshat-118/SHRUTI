"""FastAPI backend.  The GUI is a named PS deliverable, not decoration.

    *"The GUI based model will have features to take .IQ or .wav file as input
    data..."* and *"improve feature visibility of signals with the help of GUI"*

Design rules this serves (the first two are visible within the first ten seconds
of use):

* **Zero configuration to first answer.**  No dialogue asking for sample rate,
  dtype or centre frequency.  L0 infers all of it, says what it inferred and
  why, and lets the analyst override.
* **Anytime results.**  Progress is streamed, so something is on screen while
  the expensive stages run.
* **CLI/GUI parity.**  Every endpoint here maps onto a CLI subcommand; neither
  can do something the other cannot.
* **No network egress.**  Every asset is served from this process.  Nothing is
  fetched from a CDN, because on an air-gapped machine there is no CDN.
"""

from __future__ import annotations

import io
import json
import pathlib
import tempfile
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import __version__
from ..cartridge import load_library
from ..core.bits import bits_to_bytes, text_to_bits
from ..l0_container import load
from ..l4_twin.chain import SynthConfig, synthesise
from ..pipeline import analyse_capture
from . import plots

app = FastAPI(
    title="SHRUTI",
    version=__version__,
    description="Blind RF signal exploitation: samples to bits.",
)

# Same-origin in production; permissive locally so `npm run dev` can talk to it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_UPLOADS = pathlib.Path(tempfile.gettempdir()) / "shruti_uploads"
_UPLOADS.mkdir(exist_ok=True)
_LIBRARY = load_library()


def _jsonable(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return None if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


# --------------------------------------------------------------------- models


class SynthRequest(BaseModel):
    cartridge: str
    message: str = "SHRUTI synthetic capture."
    snr_db: float = 22.0
    cfo_hz: float = 0.0
    watterson: str | None = None
    seed: int = 0
    repeat: int = 30


class SelfTestRequest(BaseModel):
    message: str = "The quick brown fox jumps over the lazy dog."
    seed: int = 0
    snr_db: float | None = None
    hold_out: str | None = None


# ------------------------------------------------------------------- endpoints


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "cartridges": len(_LIBRARY),
        "offline": True,
    }


@app.get("/api/cartridges")
def cartridges() -> dict:
    return {
        "summary": _LIBRARY.summary(),
        "errors": _LIBRARY.errors,
        "cartridges": [
            {
                "id": c.id,
                "name": c.name,
                "band": c.band,
                "digest": c.digest(),
                "description": c.describe(),
                "symbol_rate_bd": c.symbol_rate,
                "blocks": c.blocks,
                "identifiability": c.identifiability,
            }
            for c in _LIBRARY
        ],
    }


@app.get("/api/requirements")
def requirements() -> dict:
    """The capability matrix, served so the GUI can show it as a live checklist."""
    from ..pipeline import DATA_REQUIREMENTS

    return {
        "data_requirements": {
            k: {"bits": v[0], "reason": v[1]} for k, v in DATA_REQUIREMENTS.items()
        },
        "capabilities": [
            {"id": "i", "text": "Identify signal parameters (sampling frequency, modulation, FEC, interleaving)"},
            {"id": "ii", "text": "Demodulate signals (FSK, QAM, PSK)"},
            {"id": "iii", "text": "De-interleaving (block, convolution, diagonal, pseudo random)"},
            {"id": "iv", "text": "FEC (short-constrained convolutional + Viterbi, RS, concatenated, LDPC)"},
            {"id": "v", "text": "Bit stream correlation for header and payload identification"},
        ],
    }


def _result_payload(res, cap, include_plots: bool = True) -> dict:
    out: dict[str, Any] = {
        "verdict": res.verdict,
        # The physical layer as CONCLUDED (from the decoded waveform), not as
        # first proposed. They disagree under fading, and showing the stale
        # proposal beside the matched waveform reads as self-contradiction.
        "resolved_physical": res.resolved_physical,
        "container": {
            "summary": cap.info.summary(),
            "kind": cap.info.kind,
            "dtype": cap.info.dtype,
            "channels": cap.info.channels,
            "sample_rate": cap.info.sample_rate,
            "rate_basis": cap.info.rate_basis,
            "centre_hz": cap.info.centre_hz,
            "centre_basis": cap.info.centre_basis,
            "n_samples": cap.info.n_samples,
            "reasons": cap.info.reasons,
        },
        "proposals": [
            {
                "modulation": p.modulation.describe(),
                "order": p.modulation.order,
                "bits_per_symbol": p.modulation.bits_per_symbol,
                "symbol_rate_bd": p.symbol_rate_bd,
                "sps": p.sps,
                "evm": p.evm,
                "snr_db": p.snr_db,
                "cfo_hz": p.cfo_hz,
            }
            for p in res.proposals
        ],
        "matches": [
            {"id": m.cartridge_id, "score": m.score, "ok": m.ok, "detail": m.detail,
             "reencode_agreement": m.result.reencode_agreement,
             "rs_blocks": m.result.rs_blocks, "rs_failed": m.result.rs_failed,
             "rs_corrected": m.result.rs_corrected,
             "ldpc_blocks": m.result.ldpc_blocks, "ldpc_converged": m.result.ldpc_converged}
            for m in res.matches
        ],
        "capabilities": [
            {"name": c.name, "available": c.available, "required_bits": c.required_bits,
             "have_bits": c.have_bits, "reason": c.reason}
            for c in res.capabilities
        ],
        "timings": res.timings,
        "notes": res.notes,
    }

    if res.frame is not None:
        out["frame"] = {
            "found": bool(getattr(res.frame, "found", False)),
            "period_bits": res.frame.period_bits,
            "confidence": res.frame.confidence,
            "n_frames": res.frame.n_frames,
            "sync_hex": res.frame.sync_hex(),
            "sync_offset": res.frame.sync_offset,
            "summary": res.frame.summary(),
            "notes": res.frame.notes,
        }
    if res.fieldmap is not None:
        out["fieldmap"] = {
            "summary": res.fieldmap.summary(),
            "period_bits": res.fieldmap.period_bits,
            "header_bits": res.fieldmap.header_bits,
            "payload_bits": res.fieldmap.payload_bits,
            "payload_entropy": res.fieldmap.payload_entropy,
            "looks_encrypted": res.fieldmap.looks_encrypted,
            "entropy": np.asarray(res.fieldmap.entropy).round(4).tolist(),
            "fields": [
                {"start": f.start, "length": f.length, "kind": f.kind.value,
                 "entropy": f.entropy, "note": f.note}
                for f in res.fieldmap.fields
            ],
        }
    if res.payload_bits is not None and len(res.payload_bits):
        raw = bits_to_bytes(res.payload_bits)[:2048]
        out["payload"] = {
            "n_bits": int(len(res.payload_bits)),
            "hex": raw.hex().upper(),
            "text": raw.decode("utf-8", errors="replace"),
        }

    if include_plots:
        x, fs = cap.samples, cap.fs
        out["plots"] = {
            "spectrum": plots.spectrum(x, fs),
            "waterfall": plots.waterfall(x, fs),
            "time": plots.time_series(x, fs),
        }
        if res.proposals:
            from ..l5_demod import demodulate
            p = res.proposals[0]
            try:
                d = demodulate(x, p.modulation, p.sps, fs)
                out["plots"]["constellation"] = plots.constellation(d.symbols)
                out["plots"]["provenance"] = plots.provenance_map(
                    len(d.llr), p.modulation.bits_per_symbol, p.sps
                )
            except Exception:                                  # noqa: BLE001
                out["plots"]["constellation"] = {"i": [], "q": [], "index": []}
    return _jsonable(out)


@app.post("/api/analyse")
async def api_analyse(file: UploadFile = File(...), hold_out: str | None = None) -> dict:
    """Upload a capture and analyse it.  Nothing is asked of the user."""
    name = pathlib.Path(file.filename or "capture.bin").name
    dest = _UPLOADS / name
    data = await file.read()
    dest.write_bytes(data)

    try:
        cap = load(dest)
    except Exception as exc:                                   # noqa: BLE001
        raise HTTPException(400, f"could not read {name}: {exc}") from exc

    if len(cap.samples) > 4_000_000:
        cap.samples = cap.samples[:4_000_000]
        cap.info.n_samples = len(cap.samples)

    lib = _LIBRARY.without(hold_out) if hold_out else _LIBRARY
    res = analyse_capture(cap, lib, path=str(dest))
    return _result_payload(res, cap)


@app.post("/api/synth")
def api_synth(req: SynthRequest) -> dict:
    """Render a capture with the twin - the Act 3 transmitter, driven from the GUI."""
    cart = _LIBRARY.by_id(req.cartridge)
    if cart is None:
        raise HTTPException(404, f"no such cartridge: {req.cartridge}")

    bits = np.tile(text_to_bits(req.message), max(1, req.repeat))
    r = synthesise(
        cart, bits,
        SynthConfig(sps=8, snr_db=req.snr_db, cfo_hz=req.cfo_hz,
                    watterson=req.watterson, seed=req.seed),
    )
    out = _UPLOADS / f"synth_{cart.id.replace('/', '_')}_{req.seed}"
    from ..l0_container import write_sigmf
    meta = write_sigmf(out, r.samples, r.fs, description=f"twin render of {cart.id}")
    return _jsonable({
        "path": str(meta),
        "download": f"/api/download/{meta.name}",
        "data_file": f"/api/download/{meta.with_suffix('.sigmf-data').name}",
        "truth": r.truth,
        "summary": r.summary(),
        "plots": {
            "spectrum": plots.spectrum(r.samples, r.fs),
            "waterfall": plots.waterfall(r.samples, r.fs),
        },
    })


@app.post("/api/selftest")
def api_selftest(req: SelfTestRequest) -> dict:
    """The end-to-end blind self-test, driven from the browser.

    The generator writes a file and the analyser is handed nothing but its path -
    the same separation the CLI enforces, so the result survives scrutiny.
    """
    from ..selftest import generate_challenge
    from ..pipeline import analyse

    path, cfg = generate_challenge(req.message, seed=req.seed or None, snr_db=req.snr_db)
    res = analyse(str(path), hold_out=req.hold_out or None)
    cap = res.capture

    recovered = res.payload_text(len(req.message) * 3)
    hit = req.message[: max(8, len(req.message) // 2)] in recovered

    payload = _result_payload(res, cap) if cap else {}
    payload["selftest"] = {
        "message": req.message,
        "recovered": recovered[:400],
        "success": bool(hit),
        "hold_out": req.hold_out,
        "truth": cfg.truth,
        "transmitter": {
            "cartridge_id": cfg.cartridge_id,
            "snr_db": cfg.snr_db,
            "cfo_hz": cfg.cfo_hz,
            "timing_offset": cfg.timing_offset,
            "watterson": cfg.watterson,
        },
    }
    return _jsonable(payload)


@app.get("/api/download/{name}")
def download(name: str):
    p = _UPLOADS / pathlib.Path(name).name
    if not p.exists():
        raise HTTPException(404, "no such file")
    return FileResponse(p, filename=p.name)


# ------------------------------------------------------------- static frontend

_DIST = pathlib.Path(__file__).parent / "static"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
