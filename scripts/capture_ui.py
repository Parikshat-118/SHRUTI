"""Capture the SHRUTI interface in each of its states, to docs/ui/.

Serves the built bundle (shruti/web/static) from a throwaway local HTTP server,
so no engine is needed: the two recorded missions ship inside the bundle.

    cd frontend && npm run build && cd ..
    python scripts/capture_ui.py

Every shot is taken at a fixed viewport so the images stay comparable and the
README renders them at a predictable size.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "shruti" / "web" / "static"
OUT = ROOT / "docs" / "ui"
DESKTOP = {"width": 1600, "height": 1000}
PHONE = {"width": 390, "height": 844}


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def serve() -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_Quiet, directory=str(SITE))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def shot(page: Page, name: str) -> None:
    path = OUT / f"{name}.jpg"
    page.screenshot(path=str(path), type="jpeg", quality=88)
    print(f"  docs/ui/{path.name}  ({path.stat().st_size // 1024} kB)")


def section(page: Page, element_id: str) -> None:
    page.evaluate(f"document.getElementById('{element_id}').scrollIntoView({{block: 'start'}})")
    page.wait_for_timeout(700)


def open_mission(page: Page, base: str, mission: str) -> None:
    """Open a mission and let the decode sequence play out."""
    page.goto(f"{base}/#/mission/{mission}")
    page.wait_for_selector(".replay", timeout=15_000)
    page.wait_for_selector(".replay", state="detached", timeout=20_000)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(900)


def main() -> int:
    if not (SITE / "index.html").exists():
        raise SystemExit("no build found - run `npm run build` in frontend/ first")
    OUT.mkdir(parents=True, exist_ok=True)
    httpd, base = serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=DESKTOP)

            # 1 - landing: the hero
            page.goto(f"{base}/#/", wait_until="networkidle")
            page.wait_for_timeout(1500)
            shot(page, "01-landing")

            # 2 - the mission library, as "Explore a mission" brings it into view
            page.locator(".hero-ctas .btn-primary").click()
            page.wait_for_timeout(1600)
            shot(page, "02-missions")

            # 3 - the pipeline, L0 to L8 with the closure feedback
            section(page, "how")
            page.evaluate("window.scrollBy(0, -40)")
            page.wait_for_timeout(500)
            shot(page, "03-pipeline")

            # 4 - the decode sequence, part-way through
            page.goto(f"{base}/#/mission/deep-space-telemetry")
            page.wait_for_selector(".replay", timeout=15_000)
            page.wait_for_timeout(1900)
            shot(page, "04-decode-sequence")

            # 5 - the console once it has landed
            page.wait_for_selector(".replay", state="detached", timeout=20_000)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(900)
            shot(page, "05-console")

            # 6 - what was sent against what came back
            section(page, "truth")
            shot(page, "06-ground-truth")

            # 7 - spectrum, constellation and waterfall
            section(page, "signal")
            shot(page, "07-signal")

            # 8 - bits: one byte selected, traced back through the entropy profile
            page.locator(".hexdump button").nth(3).click()
            section(page, "bits")
            shot(page, "08-bits")

            # 9 - the second mission: an HF modem, drawn on Earth
            open_mission(page, base, "hf-data-relay")
            shot(page, "09-console-hf")

            # 10 - Hindi
            page.goto(f"{base}/#/", wait_until="networkidle")
            page.locator(".topnav .lang").click()
            page.wait_for_timeout(1200)
            shot(page, "10-hindi")

            # 11 - phone
            phone = browser.new_page(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
            open_mission(phone, base, "deep-space-telemetry")
            shot(phone, "11-mobile")

            browser.close()
    finally:
        httpd.shutdown()
    print(f"\nwrote {len(list(OUT.glob('*.jpg')))} screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
