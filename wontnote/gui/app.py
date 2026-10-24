"""
app.py — WontNote Application Controller
========================================
Initializes the desktop window via pywebview (Edge WebView2 on Windows, WebKit on Linux)
and connects it to the Python cryptographic bridge (WontNoteAPI).
"""

import sys
from pathlib import Path
import webview

from wontnote.gui.api import WontNoteAPI


class App:
    """Central application controller launching the desktop WebView window."""

    def __init__(self):
        self.api = WontNoteAPI()

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_dir = Path(sys._MEIPASS)
            html_path = base_dir / "wontnote" / "gui" / "web" / "index.html"
            if not html_path.exists():
                html_path = base_dir / "web" / "index.html"
        else:
            html_path = Path(__file__).parent / "web" / "index.html"
        self.window = webview.create_window(
            title="WontNote",
            url=str(html_path.resolve()),
            js_api=self.api,
            width=1280,
            height=820,
            min_size=(900, 600),
            frameless=False,
            easy_drag=False,
            background_color="#ffffff",
        )
        self.api._set_window(self.window)
        self.window.events.closing += self._on_closing
        self.window.events.minimized += self._on_minimized

    def _on_minimized(self):
        if self.api._master_key is not None:
            try:
                self.window.evaluate_js("if (readPref('wn_lock_minimize', 'true') === 'true') handleLockVault()")
            except Exception:
                pass

    def _on_closing(self):
        if self.api._master_key is None or self.api._allow_close:
            return True
        try:
            self.window.evaluate_js("void requestClose()")
        except Exception:
            # Keep the window open while the bridge is still loading.
            pass
        return False

    def run(self) -> None:
        """Start the pywebview event loop."""
        webview.start(debug=False)
