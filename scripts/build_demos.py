"""Render the two demo missions and precompute their analyses for the GUI.

Each mission is rendered by the twin, written to disk with an uninformative
name and no cartridge hint in its metadata, then handed to the full pipeline
exactly as an uploaded file would be.  The JSON written for the GUI is the same
payload `/api/analyse` returns, plus the withheld transmitter configuration so
the interface can show what went in beside what came out.

    python scripts/build_demos.py

Output: frontend/public/demos/{index,<id>}.json  (served with the static bundle,
so the demos work with no engine running - the T0 GitHub Pages tier).
"""

from __future__ import annotations

import json
import pathlib
import time
import wave

import numpy as np

from shruti.cartridge import load_library
from shruti.core.bits import text_to_bits
from shruti.l0_container import write_sigmf
from shruti.l4_twin.chain import SynthConfig, synthesise
from shruti.pipeline import analyse
from shruti.web.app import _result_payload

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "corpus" / "demos"
OUT = ROOT / "frontend" / "public" / "demos"

MISSIONS = [
    {
        "id": "deep-space-telemetry",
        "title": "Deep-space telemetry",
        "title_hi": "गहन-अंतरिक्ष टेलीमेट्री",
        "tagline": "A spacecraft downlink, received as raw complex IQ",
        "tagline_hi": "अंतरिक्ष यान का डाउनलिंक, कच्चे जटिल IQ के रूप में",
        "band": "X-band · space",
        "container": "SigMF IQ",
        "cartridge": "ccsds/tm-concatenated",
        "message": (
            "TM frame 042: bus 28.4 V, battery 91%, attitude sun-pointing, "
            "star tracker locked, all subsystems nominal. "
        ),
        "repeat": 24,
        "config": dict(sps=8, snr_db=14.0, cfo_hz=3_150.0, timing_offset=0.37, seed=42),
        "centre_hz": 8_420_000_000,
        "file": "capture_0917",
        "wav": False,
    },
    {
        "id": "hf-data-relay",
        "title": "HF data relay",
        "title_hi": "HF डेटा रिले",
        "tagline": "An HF modem, recorded by an SDR as stereo I/Q .wav",
        "tagline_hi": "एक HF मॉडेम, SDR द्वारा स्टीरियो I/Q .wav में रिकॉर्ड",
        "band": "HF · 3-30 MHz",
        "container": "stereo I/Q .wav",
        "cartridge": "mil-std-188-110a/serial-2400",
        "message": (
            "Weather relay from the northern outpost: wind 12 knots, "
            "visibility good, next contact at 0600 UTC. "
        ),
        "repeat": 12,
        # AWGN: the mono-SSB and Watterson-faded paths do not decode yet.
        "config": dict(sps=8, snr_db=22.0, cfo_hz=37.0, timing_offset=0.62, seed=7),
        "centre_hz": None,
        "file": "sdr_iq_0412",
        "wav": True,
    },
]


def render(m: dict, cart) -> pathlib.Path:
    bits = np.tile(text_to_bits(m["message"]), m["repeat"])
    r = synthesise(cart, bits, SynthConfig(**m["config"]))
    m["_truth"] = r.truth
    CAPTURES.mkdir(parents=True, exist_ok=True)
    if m["wav"]:
        # I in the left channel, Q in the right - how SDR software records IQ
        # to .wav.  L0 has to tell this apart from true stereo audio.
        path = CAPTURES / f"{m['file']}.wav"
        x = r.samples / (np.max(np.abs(r.samples)) * 1.05)
        iq = np.stack([x.real, x.imag], axis=1)
        a = (iq * 32000).astype("<i2")
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(int(r.fs))
            w.writeframes(a.tobytes())
        return path
    # No cartridge id and no descriptive text: the analyser gets the samples,
    # the sample rate and the tuned frequency, as a real recorder would give.
    return write_sigmf(
        CAPTURES / m["file"], r.samples, r.fs,
        centre_hz=m["centre_hz"], description="unlabelled capture",
    )


def main() -> None:
    lib = load_library()
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for m in MISSIONS:
        cart = lib.by_id(m["cartridge"])
        path = render(m, cart)
        t0 = time.time()
        res = analyse(str(path))
        elapsed = time.time() - t0

        payload = _result_payload(res, res.capture)
        recovered = res.payload_text(len(m["message"]) * 3)
        cfg = m["config"]
        payload["selftest"] = {
            "message": m["message"].strip(),
            "recovered": recovered[:400],
            "success": m["message"][:40] in recovered,
            "hold_out": None,
            "truth": m["_truth"],
            "transmitter": {
                "cartridge_id": cart.id,
                "snr_db": cfg["snr_db"],
                "cfo_hz": cfg["cfo_hz"],
                "timing_offset": cfg["timing_offset"],
                "watterson": cfg.get("watterson"),
            },
        }
        (OUT / f"{m['id']}.json").write_text(
            json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8"
        )
        # The card shown before decoding carries no answer - no cartridge, no
        # verdict - only what an analyst would know about their own recording,
        # plus a peak-held spectrum thumbnail of the real capture.
        power = np.asarray(payload["plots"]["spectrum"]["power_db"], dtype=float)
        preview = [float(c.max()) for c in np.array_split(power, 96)] if len(power) else []
        entry = {k: v for k, v in m.items()
                 if not k.startswith("_")
                 and k not in ("config", "repeat", "wav", "message", "cartridge")}
        entry.update({
            "file": path.name,
            "analysis_s": round(elapsed, 2),
            "generated": time.strftime("%Y-%m-%d"),
            "preview": [round(v, 1) for v in preview],
        })
        index.append(entry)
        print(f"{m['id']:<24} {payload['verdict']:<11} {elapsed:6.1f} s   "
              f"{res.resolved_physical}   recovered={payload['selftest']['success']}")

    catalogue = {"cartridges": len(lib), "missions": index}
    (OUT / "index.json").write_text(json.dumps(catalogue, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(index)} missions to {OUT}")


if __name__ == "__main__":
    main()
