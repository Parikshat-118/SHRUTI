"""SHRUTI command line.  GUI and CLI are at parity by design.

    shruti analyse capture.wav --report out/       # the whole chain
    shruti synth --cartridge ccsds/tm-concatenated --message "..." out.sigmf
    shruti cartridge list | validate
    shruti selftest                                # end-to-end blind self-test
    shruti gui                                     # the browser interface

CLI/GUI parity is what makes archive-scale batch mode exist at no extra cost:
an analyst with a thousand files will not click a thousand times.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

from . import __version__

BANNER = r"""
  ___ _  _ ___ _   _ _____ ___
 / __| || | _ \ | | |_   _|_ _|   blind signal exploitation, samples to bits
 \__ \ __ |   / |_| | | |  | |    runs air-gapped, no network required
 |___/_||_|_|_\\___/  |_| |___|   Apache-2.0
"""


def _fmt_bits(bits: np.ndarray, limit: int = 32) -> str:
    from .core.bits import bits_to_bytes
    raw = bits_to_bytes(bits)[:limit]
    hexs = " ".join(f"{b:02X}" for b in raw)
    txt = "".join(chr(b) if 32 <= b < 127 else "." for b in raw)
    return f"{hexs}\n  |{txt}|"


# --------------------------------------------------------------------- analyse


def cmd_analyse(args) -> int:
    from .pipeline import analyse

    def progress(stage: str, frac: float) -> None:
        if not args.quiet:
            bar = "#" * int(frac * 28)
            print(f"\r  [{bar:<28}] {stage:<12}", end="", file=sys.stderr, flush=True)

    res = analyse(
        args.path,
        sample_rate=args.sample_rate,
        sps=args.sps,
        hold_out=args.hold_out,
        progress=progress,
    )
    if not args.quiet:
        print("\r" + " " * 50 + "\r", end="", file=sys.stderr)

    print(res.summary())

    if res.proposals:
        print("\nPhysical layer (blind):")
        for p in res.proposals[:3]:
            print(f"  {p.describe()}")

    if res.matches:
        print("\nWaveform candidates:")
        for m in res.matches:
            flag = "OK " if m.ok else "   "
            print(f"  {flag}{m.cartridge_id:34s} score={m.score:8.2f}  {m.detail}")

    if res.fieldmap is not None:
        print("\nFrame structure:")
        print(res.fieldmap.table())

    if res.payload_bits is not None and len(res.payload_bits):
        print(f"\nRecovered payload ({len(res.payload_bits)} bits):")
        print("  " + _fmt_bits(res.payload_bits, 48))

    gated = [c for c in res.capabilities if not c.available]
    if gated:
        print("\nCapabilities gated by data volume:")
        for c in gated:
            print(f"  {c.describe()}")

    if res.notes:
        print("\nNotes:")
        for n in res.notes:
            print(f"  - {n}")

    if args.attest:
        from .l8_report import create_bundle
        bp = create_bundle(res, args.path, args.attest)
        print(f"\nattestation bundle written to {bp}")
        print("  verify it anywhere with:  shruti verify " + str(bp))

    if args.report:
        out = pathlib.Path(args.report)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "path": res.path,
            "verdict": res.verdict,
            "container": res.capture.info.summary() if res.capture else None,
            "container_reasons": res.capture.info.reasons if res.capture else [],
            "proposals": [p.describe() for p in res.proposals],
            "matches": [
                {"id": m.cartridge_id, "score": m.score, "ok": m.ok, "detail": m.detail}
                for m in res.matches
            ],
            "capabilities": [
                {"name": c.name, "available": c.available,
                 "required_bits": c.required_bits, "have_bits": c.have_bits}
                for c in res.capabilities
            ],
            "payload_bits": int(len(res.payload_bits)) if res.payload_bits is not None else 0,
            "payload_preview": res.payload_text(200),
            "timings": res.timings,
            "notes": res.notes,
        }
        (out / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nreport written to {out / 'report.json'}")

    return 0 if res.identified else 1


# ----------------------------------------------------------------------- synth


def cmd_synth(args) -> int:
    from .cartridge import load_library
    from .core.bits import text_to_bits
    from .l0_container import write_sigmf
    from .l4_twin.chain import SynthConfig, synthesise

    lib = load_library()
    cart = lib.by_id(args.cartridge)
    if cart is None:
        print(f"no such cartridge: {args.cartridge}", file=sys.stderr)
        print("available:", file=sys.stderr)
        for c in lib:
            print(f"  {c.id}", file=sys.stderr)
        return 2

    msg = args.message or "SHRUTI synthetic capture. " * 16
    bits = text_to_bits(msg)
    if args.repeat > 1:
        bits = np.tile(bits, args.repeat)

    cfg = SynthConfig(
        sps=args.sps,
        snr_db=args.snr,
        cfo_hz=args.cfo,
        timing_offset=args.timing,
        watterson=args.watterson,
        seed=args.seed,
        render_wav=args.wav,
    )
    r = synthesise(cart, bits, cfg)
    print(r.summary())

    out = pathlib.Path(args.out)
    if args.wav and r.audio is not None:
        import wave
        a = (np.clip(r.audio, -1, 1) * 32000).astype("<i2")
        wp = out.with_suffix(".wav")
        with wave.open(str(wp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(r.audio_fs))
            w.writeframes(a.tobytes())
        print(f"wrote {wp}  (mono SSB audio - the HF .wav case)")
    else:
        meta = write_sigmf(
            out, r.samples, r.fs,
            centre_hz=cart.centre_hz or None,
            description=f"SHRUTI twin render of {cart.id}",
            extensions={"shruti:cartridge": cart.id, "shruti:cartridge_digest": cart.digest()},
        )
        print(f"wrote {meta} and {meta.with_suffix('.sigmf-data')}")

    if args.truth:
        pathlib.Path(args.truth).write_text(
            json.dumps(r.truth, indent=2, default=str), encoding="utf-8"
        )
        print(f"ground truth written to {args.truth}")
    return 0


# ------------------------------------------------------------------- cartridge


def cmd_cartridge(args) -> int:
    from .cartridge import load_library
    from .cartridge.loader import default_library_path

    lib = load_library(args.dir)
    if args.action == "list":
        print(f"{lib.summary()}   ({args.dir or default_library_path()})")
        for c in lib:
            print(f"  {c.digest()}  {c.describe()}")
        for e in lib.errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        return 0

    ok = True
    for c in lib:
        problems = c.validate()
        if problems:
            ok = False
            print(f"INVALID {c.id}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"OK      {c.id}")
    for e in lib.errors:
        ok = False
        print(f"ERROR   {e}", file=sys.stderr)
    return 0 if ok else 1


# -------------------------------------------------------------------- selftest


def cmd_selftest(args) -> int:
    """Blind self-test: a sentence in, a randomised transmitter, the sentence out."""
    from .selftest import run_blind_selftest

    return run_blind_selftest(
        message=args.message,
        seed=args.seed,
        snr_db=args.snr,
        hold_out=args.hold_out,
        verbose=True,
    )


# ------------------------------------------------------------------------- gui


def cmd_verify(args) -> int:
    """Re-derive an archived finding. A finding another agency can check."""
    from .l8_report import verify_bundle

    print(f"verifying {args.bundle}\n")
    res = verify_bundle(args.bundle, args.capture)
    print(res.report())
    return 0 if res.passed else 1


def cmd_gui(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print("the GUI needs fastapi and uvicorn:\n  pip install 'shruti[gui]'", file=sys.stderr)
        return 2
    from .web.app import app

    print(f"SHRUTI GUI on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


# ------------------------------------------------------------------------ main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shruti",
        description="Blind RF signal exploitation: samples to bits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=BANNER,
    )
    p.add_argument("--version", action="version", version=f"SHRUTI {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyse", aliases=["analyze"], help="analyse a capture file")
    a.add_argument("path")
    a.add_argument("--report", help="directory to write report.json into")
    a.add_argument("--sample-rate", type=float, help="override the sample rate in Hz")
    a.add_argument("--sps", type=int, help="override samples per symbol")
    a.add_argument("--hold-out", help="remove one cartridge from the library (blind test)")
    a.add_argument("--attest", help="write an attestation bundle to this path")
    a.add_argument("-q", "--quiet", action="store_true")
    a.set_defaults(func=cmd_analyse)

    s = sub.add_parser("synth", help="render a capture with the twin")
    s.add_argument("out")
    s.add_argument("--cartridge", required=True)
    s.add_argument("--message", help="payload text")
    s.add_argument("--repeat", type=int, default=1)
    s.add_argument("--snr", type=float, default=20.0)
    s.add_argument("--cfo", type=float, default=0.0, help="carrier offset in Hz")
    s.add_argument("--timing", type=float, default=0.0, help="fractional-sample timing offset")
    s.add_argument("--watterson", choices=["good", "moderate", "poor", "flutter", "disturbed"])
    s.add_argument("--sps", type=int, default=8)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--wav", action="store_true", help="render mono SSB audio instead of IQ")
    s.add_argument("--truth", help="write ground truth JSON here")
    s.set_defaults(func=cmd_synth)

    c = sub.add_parser("cartridge", help="inspect the waveform library")
    c.add_argument("action", choices=["list", "validate"])
    c.add_argument("--dir", help="cartridge directory")
    c.set_defaults(func=cmd_cartridge)

    d = sub.add_parser("selftest", help="run the end-to-end blind self-test")
    d.add_argument("--message", default="")
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--snr", type=float, default=22.0)
    d.add_argument("--hold-out", help="hide a cartridge from the analyser")
    d.set_defaults(func=cmd_selftest)

    v = sub.add_parser("verify", help="re-derive a finding from its attestation bundle")
    v.add_argument("bundle")
    v.add_argument("--capture", help="path to the original capture, if not embedded")
    v.set_defaults(func=cmd_verify)

    g = sub.add_parser("gui", help="serve the browser interface")
    g.add_argument("--host", default="127.0.0.1")
    g.add_argument("--port", type=int, default=8000)
    g.set_defaults(func=cmd_gui)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
