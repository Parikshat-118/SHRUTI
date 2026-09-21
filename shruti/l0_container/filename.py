"""Recorder filename conventions - unglamorous, and it resolves a lot of files free.

Absolute sample rate and RF centre frequency are not recoverable from samples
alone.  But most real captures were written by one of a handful of SDR programs,
and those programs put the answer in the filename.  Parsing them is an hour of
work that resolves a large fraction of an archive at zero cost - the kind of
thing that does not look clever and matters enormously in practice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["FilenameInfo", "parse_filename", "CONVENTIONS"]


@dataclass
class FilenameInfo:
    """What a filename revealed, and which convention said so."""

    recorder: str | None = None
    centre_hz: float | None = None
    sample_rate: float | None = None
    timestamp: str | None = None
    dtype: str | None = None

    @property
    def found_anything(self) -> bool:
        return any(
            v is not None
            for v in (self.recorder, self.centre_hz, self.sample_rate, self.timestamp)
        )

    def evidence(self) -> str:
        bits = []
        if self.recorder:
            bits.append(f"recorder={self.recorder}")
        if self.centre_hz:
            bits.append(f"centre={self.centre_hz/1e6:.6f} MHz")
        if self.sample_rate:
            bits.append(f"rate={self.sample_rate/1e6:.6f} Msps")
        if self.timestamp:
            bits.append(f"t={self.timestamp}")
        return ", ".join(bits) if bits else "nothing recognised"


#: (recorder, regex, field map).  Ordered most-specific first.
CONVENTIONS: list[tuple[str, re.Pattern, dict]] = [
    # SDRSharp_20240115_120000Z_145500000Hz_IQ.wav
    (
        "SDRSharp",
        re.compile(
            r"SDRSharp_(?P<ts>\d{8}_\d{6}Z)_(?P<cf>\d+)Hz_IQ", re.IGNORECASE
        ),
        {"cf": "centre_hz", "ts": "timestamp"},
    ),
    # gqrx_20240115_120000_145500000_1800000_fc.raw
    (
        "gqrx",
        re.compile(
            r"gqrx_(?P<ts>\d{8}_\d{6})_(?P<cf>\d+)_(?P<sr>\d+)_fc", re.IGNORECASE
        ),
        {"cf": "centre_hz", "sr": "sample_rate", "ts": "timestamp"},
    ),
    # HDSDR_20240115_120000Z_14550kHz_RF.wav
    (
        "HDSDR",
        re.compile(
            r"HDSDR_(?P<ts>\d{8}_\d{6}Z)_(?P<cf>\d+)kHz", re.IGNORECASE
        ),
        {"cf": "centre_khz", "ts": "timestamp"},
    ),
    # SDRuno_20240115_120000_145500000Hz.wav
    (
        "SDRuno",
        re.compile(r"SDRuno_(?P<ts>\d{8}_\d{6})_(?P<cf>\d+)Hz", re.IGNORECASE),
        {"cf": "centre_hz", "ts": "timestamp"},
    ),
    # SDRangel: 20240115_120000_145500000Hz_2400000sps.sdriq
    (
        "SDRangel",
        re.compile(
            r"(?P<ts>\d{8}_\d{6})_(?P<cf>\d+)Hz_(?P<sr>\d+)sps", re.IGNORECASE
        ),
        {"cf": "centre_hz", "sr": "sample_rate", "ts": "timestamp"},
    ),
    # KiwiSDR: kiwi_20240115_120000Z_14550_usb.wav
    (
        "KiwiSDR",
        re.compile(
            r"kiwi[_-](?P<ts>\d{8}_\d{6}Z?)_(?P<cf>\d+)_", re.IGNORECASE
        ),
        {"cf": "centre_khz", "ts": "timestamp"},
    ),
    # Generic trailing hints: ..._8000000sps... / ..._2M4...
    (
        "generic-sps",
        re.compile(r"[_-](?P<sr>\d{4,})(?:sps|Hz_IQ|_sps)", re.IGNORECASE),
        {"sr": "sample_rate"},
    ),
]

#: Extension -> (numpy dtype string, is_complex)
EXTENSION_DTYPES: dict[str, tuple[str, bool]] = {
    ".cf32": ("float32", True),
    ".cfile": ("float32", True),
    ".cs16": ("int16", True),
    ".cs8": ("int8", True),
    ".sc16": ("int16", True),
    ".sc8": ("int8", True),
    ".fc32": ("float32", True),
}


def parse_filename(name: str) -> FilenameInfo:
    """Extract whatever a recorder encoded into the filename."""
    info = FilenameInfo()
    base = name.replace("\\", "/").split("/")[-1]

    for recorder, pattern, fields in CONVENTIONS:
        m = pattern.search(base)
        if not m:
            continue
        info.recorder = recorder
        gd = m.groupdict()
        for key, target in fields.items():
            val = gd.get(key)
            if val is None:
                continue
            if target == "centre_hz":
                info.centre_hz = float(val)
            elif target == "centre_khz":
                info.centre_hz = float(val) * 1e3
            elif target == "sample_rate":
                info.sample_rate = float(val)
            elif target == "timestamp":
                info.timestamp = val
        break

    low = base.lower()
    for ext, (dt, _) in EXTENSION_DTYPES.items():
        if low.endswith(ext):
            info.dtype = dt
            break

    return info
