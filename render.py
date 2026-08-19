"""HTML DM-kartını headless Chromium ile PNG'ye çevirir (Playwright)."""
import html
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATE = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
SENDER = "Sınır Kapıları"


def _fill(body_text: str, time_text: str) -> str:
    # html.escape emoji'yi korur, sadece < > & kaçırır; \n bubble'da pre-wrap ile korunur.
    return (
        TEMPLATE.replace("{{BODY}}", html.escape(body_text))
        .replace("{{TIME}}", html.escape(time_text))
        .replace("{{SENDER}}", html.escape(SENDER))
    )


class Renderer:
    """Tek bir tarayıcı örneğiyle birden çok kartı render eder."""

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(args=["--no-sandbox"])
        self.page = self.browser.new_page(device_scale_factor=2)
        return self

    def render(self, body_text: str, time_text: str) -> bytes:
        self.page.set_content(_fill(body_text, time_text), wait_until="load")
        return self.page.locator("#card").screenshot(type="png")

    def __exit__(self, *exc):
        self.browser.close()
        self._pw.stop()
