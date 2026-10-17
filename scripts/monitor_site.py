"""
Monitor visible content on https://government-research-agent.vercel.app/
every 5 minutes. Saves changed page text/tables and sends a desktop
notification. This monitors only content visible to this browser session.
It cannot see private uploads or backend/database changes not exposed by the site.
"""

import asyncio
import csv
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from difflib import unified_diff

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://government-research-agent.vercel.app/"
CHECK_EVERY_SECONDS = 300  # 5 minutes
OUTPUT_DIR = Path("government_agent_monitor")
STATE_FILE = OUTPUT_DIR / "last_seen.json"
LOG_FILE = OUTPUT_DIR / "monitor.log"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

def notify(title: str, message: str) -> None:
    """Desktop notification when plyer is installed; always logs to console/log."""
    logging.info("NOTIFICATION: %s — %s", title, message)
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:240],
            app_name="Government Research Agent Monitor",
            timeout=10,
        )
    except Exception as exc:
        logging.warning(
            "Desktop notification unavailable (%s). Install plyer with "
            "'python -m pip install plyer' if desired.", exc
        )

def normalized_text(text: str) -> str:
    # Normalize whitespace only; do not remove substantive page content.
    return re.sub(r"[ \t]+", " ", text).strip()

def read_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logging.warning("Could not read saved state; starting a new baseline.")
    return {}

def write_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

async def capture(page):
    response = await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    try:
        await page.locator("body").wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        pass

    # Let client-side rendering settle; networkidle can be unreliable on agent apps.
    await page.wait_for_timeout(4000)

    title = await page.title()
    body_text = normalized_text(await page.locator("body").inner_text())

    tables = await page.locator("table").evaluate_all("""
        tables => tables.map(table =>
            Array.from(table.rows).map(row =>
                Array.from(row.cells).map(cell => cell.innerText.trim())
            )
        )
    """)

    # Hash meaningful rendered content, including any HTML tables.
    payload = {
        "url": page.url,
        "title": title,
        "text": body_text,
        "tables": tables,
        "http_status": response.status if response else None,
    }
    stable_payload = json.dumps(
        {"title": title, "text": body_text, "tables": tables},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
    return payload, digest

def save_snapshot(payload, digest):
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")
    text_path = OUTPUT_DIR / f"snapshot_{stamp}.txt"
    json_path = OUTPUT_DIR / f"snapshot_{stamp}.json"

    text_path.write_text(payload["text"], encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for i, table in enumerate(payload["tables"], start=1):
        if not table:
            continue
        csv_path = OUTPUT_DIR / f"snapshot_{stamp}_table_{i}.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(table)

    return stamp, text_path, json_path

def save_diff(old_text: str, new_text: str, stamp: str):
    lines = unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm="",
    )
    diff_text = "\n".join(lines)
    diff_path = OUTPUT_DIR / f"changes_{stamp}.diff.txt"
    diff_path.write_text(diff_text or "(Content hash changed, but text diff is empty.)",
                         encoding="utf-8")
    return diff_path

async def main():
    state = read_state()
    previous_hash = state.get("hash")
    previous_text = state.get("text", "")
    is_first_capture = previous_hash is None

    logging.info("Starting monitor for %s", URL)
    logging.info("Checking every %d seconds (5 minutes).", CHECK_EVERY_SECONDS)
    logging.info("Output folder: %s", OUTPUT_DIR.resolve())

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(15000)

        try:
            while True:
                started = datetime.now().astimezone().isoformat(timespec="seconds")
                try:
                    payload, current_hash = await capture(page)

                    if is_first_capture:
                        stamp, text_path, json_path = save_snapshot(payload, current_hash)
                        state = {
                            "hash": current_hash,
                            "text": payload["text"],
                            "last_checked": started,
                        }
                        write_state(state)
                        previous_hash = current_hash
                        previous_text = payload["text"]
                        is_first_capture = False
                        logging.info(
                            "Baseline saved (no notification on first run): %s",
                            text_path,
                        )

                    elif current_hash != previous_hash:
                        stamp, text_path, json_path = save_snapshot(payload, current_hash)
                        diff_path = save_diff(previous_text, payload["text"], stamp)
                        state = {
                            "hash": current_hash,
                            "text": payload["text"],
                            "last_checked": started,
                        }
                        write_state(state)
                        previous_hash = current_hash
                        previous_text = payload["text"]

                        # Persist hash before notification, preventing duplicate alerts
                        # if the script restarts after a successful capture.
                        notify(
                            "Website content changed",
                            f"New visible content saved. Snapshot: {stamp}",
                        )
                        logging.info(
                            "Change saved: %s | %s | %s",
                            text_path, json_path, diff_path,
                        )
                    else:
                        state["last_checked"] = started
                        write_state(state)
                        logging.info("No visible content change detected.")

                except Exception:
                    logging.exception("Check failed; will retry at the next interval.")
                    # Continue monitoring after transient network/site errors.

                await asyncio.sleep(CHECK_EVERY_SECONDS)

        except asyncio.CancelledError:
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
