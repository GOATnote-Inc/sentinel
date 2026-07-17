"""Headless backup capture of the golden path: video (.webm) + README screenshots.

    .venv/bin/python -m sentinel.record          # uses live model if key present

Boots the server itself (port 8790), records ~85s of the glass box, snaps a
mid-story and full-story screenshot into docs/.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

PORT = 8790
BASE = f"http://127.0.0.1:{PORT}"
DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update({"SENTINEL_PORT": str(PORT), "SENTINEL_START_DELAY": "4"})
    srv = subprocess.Popen([sys.executable, "-m", "sentinel.app"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"{BASE}/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.5)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1600, "height": 900},
                                      record_video_dir=str(DOCS),
                                      record_video_size={"width": 1600, "height": 900})
            page = ctx.new_page()
            page.goto(BASE)
            page.wait_for_timeout(24_000)          # feed start + seeded incident resolved
            page.screenshot(path=str(DOCS / "screenshot-selfcorrect.png"))
            print("shot 1 (self-correction) saved")
            page.wait_for_timeout(56_000)          # blocked + escalation + trailing feed
            page.screenshot(path=str(DOCS / "screenshot.png"))
            print("shot 2 (full story) saved")
            page.wait_for_timeout(5_000)
            video = page.video
            ctx.close()
            path = pathlib.Path(video.path())
            final = DOCS / "sentinel-golden-path.webm"
            path.rename(final)
            browser.close()
            print(f"video: {final} ({final.stat().st_size//1024} KB)")
    finally:
        srv.kill()
        srv.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
