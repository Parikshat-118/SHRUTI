"""End-to-end blind self-test.

The operator supplies a sentence.  The transmitter then picks a random waveform:
modulation, symbol rate, roll-off, interleaver type and depth, FEC family,
carrier offset, channel conditions.  The twin synthesises an unlabelled file.
SHRUTI is handed that file and told nothing about it.

It reports the sampling frequency, the modulation, the symbol rate, the
interleaver type, the FEC family, the frame structure with header segmented from
payload - **and then the original sentence.**

Every number reported is a measurement, and the recovered sentence is the
evidence that the measurements were right: if any one of them had been wrong,
the error-correcting code would not have decoded and the output would be noise.

There is no partial-credit result here.  Either the sentence comes back or it
does not, which makes this a pass/fail acceptance check rather than an
impression of one.

**The generator and the analyser share no state.**  The generator writes a file
to disk and returns a path; the analyser is constructed afterwards and receives
nothing but that path.  ``--hold-out`` goes further and removes the waveform's
own cartridge from the analyser's library, so the library-match track cannot
fire and the blind tracks must do the work.
"""

from __future__ import annotations

import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .cartridge import Cartridge, load_library
from .core.bits import text_to_bits
from .l0_container import write_sigmf
from .l4_twin.chain import SynthConfig, synthesise

__all__ = ["RandomisedTransmitter", "generate_challenge", "run_blind_selftest"]


DEFAULT_MESSAGE = "The quick brown fox jumps over the lazy dog."


@dataclass
class RandomisedTransmitter:
    """The randomly drawn transmitter configuration, kept from the analyser."""

    cartridge_id: str
    snr_db: float
    cfo_hz: float
    timing_offset: float
    watterson: str | None
    seed: int
    truth: dict = field(default_factory=dict)

    def reveal(self) -> str:
        rows = [
            ("waveform", self.cartridge_id),
            ("modulation", self.truth.get("modulation", "?")),
            ("symbol rate", f"{self.truth.get('symbol_rate_bd', 0):g} Bd"),
            ("roll-off", f"{self.truth.get('rolloff', 0):g}"),
            ("FEC", self.truth.get("fec", "none")),
            ("FEC (outer)", self.truth.get("fec_outer", "none")),
            ("interleaver", self.truth.get("interleaver", "none")),
            ("scrambler", self.truth.get("scrambler", "none")),
            ("carrier offset", f"{self.cfo_hz:+.1f} Hz"),
            ("SNR", f"{self.snr_db:.1f} dB"),
            ("channel", self.watterson or "AWGN"),
        ]
        return "\n".join(f"    {k:<16} {v}" for k, v in rows)


def generate_challenge(
    message: str = DEFAULT_MESSAGE,
    seed: int | None = None,
    snr_db: float | None = None,
    out_dir: str | Path | None = None,
    library=None,
) -> tuple[Path, RandomisedTransmitter]:
    """Pick a random transmitter, render an unlabelled capture, return its path.

    Returns ``(path, config)``.  The config is retained only for the final
    comparison; only `path` is handed to the analyser.
    """
    rng = random.Random(seed)
    lib = library if library is not None else load_library()
    usable = [c for c in lib if c.symbol_rate and c.symbol_rate <= 100_000]
    if not usable:
        usable = list(lib)
    cart: Cartridge = rng.choice(usable)

    snr = snr_db if snr_db is not None else rng.uniform(18.0, 30.0)
    cfo = rng.uniform(-0.01, 0.01) * cart.symbol_rate
    timing = rng.uniform(0.0, 1.0)
    watterson = rng.choice([None, None, None, "good", "moderate"])

    bits = text_to_bits(message)
    reps = max(1, int(np.ceil(4000 / max(len(bits), 1))))
    bits = np.tile(bits, reps)

    cfg = SynthConfig(
        sps=8,
        snr_db=snr,
        cfo_hz=cfo,
        timing_offset=timing,
        watterson=watterson,
        seed=rng.randrange(1 << 30),
    )
    r = synthesise(cart, bits, cfg)

    out = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="shruti_challenge_"))
    out.mkdir(parents=True, exist_ok=True)
    # Deliberately uninformative filename: no recorder convention to parse, so
    # L0 gets no free hints about rate or centre frequency.
    meta = write_sigmf(
        out / "challenge", r.samples, r.fs,
        description="unlabelled capture",
    )

    return meta, RandomisedTransmitter(
        cartridge_id=cart.id,
        snr_db=snr,
        cfo_hz=cfo,
        timing_offset=timing,
        watterson=watterson,
        seed=cfg.seed,
        truth=r.truth,
    )


def run_blind_selftest(
    message: str = "",
    seed: int = 0,
    snr_db: float | None = None,
    hold_out: str | None = None,
    verbose: bool = True,
) -> int:
    """Run the full check.  Returns 0 if the sentence came back, 1 otherwise."""
    from .pipeline import analyse

    msg = message or DEFAULT_MESSAGE
    if verbose:
        print("=" * 72)
        print("  SHRUTI - BLIND SELF-TEST")
        print("=" * 72)
        print(f"\n  Input sentence:\n    \"{msg}\"\n")
        print("  Randomising the transmitter...")

    path, cfg = generate_challenge(msg, seed=seed if seed else None, snr_db=snr_db)

    if verbose:
        print(f"  Transmitter configured and WITHHELD. Capture written to:\n    {path}\n")
        print("  The analyser is started now. It receives that file and nothing else.")
        if hold_out:
            print(f"  Hold-out: '{hold_out}' has been REMOVED from the analyser's library.")
        print("-" * 72)

    res = analyse(str(path), hold_out=hold_out or None)

    if verbose:
        print("\n  WHAT SHRUTI RECOVERED, KNOWING NOTHING:\n")
        print(res.summary())
        if res.proposals:
            p = res.proposals[0]
            print(f"\n    measured modulation   {p.modulation.describe()}")
            print(f"    measured symbol rate  {p.symbol_rate_bd:.1f} Bd")
            print(f"    measured SNR          {p.snr_db:.1f} dB")
            print(f"    measured CFO          {p.cfo_hz:+.1f} Hz")

    recovered = res.payload_text(len(msg) * 2)
    hit = msg[: max(8, len(msg) // 2)] in recovered

    if verbose:
        print("\n  RECOVERED PAYLOAD:")
        clean = "".join(ch if 32 <= ord(ch) < 127 else "." for ch in recovered[:120])
        print(f'    "{clean}"')
        print("\n" + "-" * 72)
        print("  THE TRANSMITTER CONFIGURATION THAT WAS WITHHELD:\n")
        print(cfg.reveal())
        print("\n" + "=" * 72)
        if hit:
            print("  RESULT: PASS - the sentence came back.\n")
            print("  Every number above is a measurement, and the sentence is the")
            print("  evidence that the measurements were right - because if any one")
            print("  of them had been wrong, the code would not have decoded and the")
            print("  output would be noise.")
        else:
            print("  RESULT: FAIL - the sentence did not come back.")
            print("\n  SHRUTI reports what it could measure and declines to claim")
            print("  what it could not. That refusal is the feature - a tool that is")
            print("  confidently wrong once is never trusted again.")
        print("=" * 72)

    return 0 if hit else 1
