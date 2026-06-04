"""
MedInsight Analytics Platform - Screenshot Capture
Takes full-page screenshots of all 6 dashboard pages.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
OUT_DIR  = Path(__file__).resolve().parent.parent / "screenshots"
OUT_DIR.mkdir(exist_ok=True)

PAGES = [
    ("Executive Overview",   "01_executive_overview.png"),
    ("Doctor Performance",   "02_doctor_performance.png"),
    ("Patient Analytics",    "03_patient_analytics.png"),
    ("Financial Analytics",  "04_financial_analytics.png"),
    ("Operational Metrics",  "05_operational_metrics.png"),
    ("Predictive Analytics", "06_predictive_analytics.png"),
]

def wait_for_charts(page, seconds: int = 5) -> None:
    """Wait for Plotly charts to finish rendering."""
    try:
        page.wait_for_selector(".js-plotly-plot", timeout=10000)
    except Exception:
        pass
    time.sleep(seconds)


def capture() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.5,
        )
        page = context.new_page()

        # Load home page and wait for Streamlit to be ready
        print("→ Home page …")
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        time.sleep(4)
        page.screenshot(path=str(OUT_DIR / "00_home.png"), full_page=True)
        print("  ✓ 00_home.png")

        for nav_text, filename in PAGES:
            print(f"→ {nav_text} …")
            # Click the sidebar navigation link
            link = page.locator(f"[data-testid='stSidebarNav'] a", has_text=nav_text).first
            link.click()
            wait_for_charts(page, seconds=5)
            page.screenshot(path=str(OUT_DIR / filename), full_page=True)
            print(f"  ✓ {filename}")

        browser.close()
    print(f"\nAll screenshots saved to: {OUT_DIR}")


if __name__ == "__main__":
    capture()
