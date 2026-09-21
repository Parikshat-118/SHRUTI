"""Capture the SHRUTI GUI in each of its states, to docs/ui/.

Run against a live server (``shruti gui``) so the screenshots are of the real
interface rather than a mock:

    python -m shruti.cli gui --port 8000 &
    python scripts/capture_ui.py

Every shot is taken at a fixed viewport so the images stay comparable and the
README renders them at a predictable size.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "ui"
VIEWPORT = {"width": 1600, "height": 1000}


def shot(page, name: str, full: bool = False) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=full)
    print(f"  {path.relative_to(OUT.parent.parent)}  ({path.stat().st_size // 1024} kB)")


def run_selftest(page, hold_out: bool = False) -> None:
    """Press Randomise & run, then wait for the outcome banner to land."""
    if hold_out:
        page.locator(".selftest .check input[type=checkbox]").check()
    page.locator("button.primary").click()
    page.wait_for_selector(".selftest-outcome", timeout=180_000)
    page.wait_for_timeout(600)  # let the plots finish painting


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(BASE, wait_until="networkidle")

        # 1 - the landing state: drop zone and the self-test panel, nothing else
        shot(page, "01-empty-state")

        # 2 - a completed self-test, above the fold: outcome banner + verdict
        run_selftest(page)
        shot(page, "02-selftest-result")

        # 3 - the same analysis, whole page: plots and every panel
        shot(page, "03-full-analysis", full=True)

        # 4 - the plot grid on its own
        page.locator(".plots-grid").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        shot(page, "04-plots")

        # 5 - the panel grid: container reasoning, measurements, ranking, payload
        page.locator(".panel-grid").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        shot(page, "05-panels")

        # 6 - Hindi. The interface is bilingual; this is not a token gesture
        page.locator("button.lang").click()
        page.wait_for_timeout(400)
        page.mouse.wheel(0, -4000)
        page.wait_for_timeout(400)
        shot(page, "06-hindi")
        page.locator("button.lang").click()
        page.wait_for_timeout(300)

        # 7 - hold-out mode: the waveform's own cartridge is removed from the
        #     library, so the blind tracks have to do the work unaided
        page.reload(wait_until="networkidle")
        run_selftest(page, hold_out=True)
        shot(page, "07-hold-out", full=True)

        browser.close()
    print(f"\nwrote {len(list(OUT.glob('*.png')))} screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
