"""
app.py — WontNote Application Controller
========================================
Initializes the desktop window via pywebview (Edge WebView2 on Windows, WebKit on Linux)
and connects it to the Python cryptographic bridge (WontNoteAPI).
"""

import sys
import logging
from pathlib import Path
from threading import Lock, Thread
import webview

from wontnote.gui.api import WontNoteAPI

logger = logging.getLogger(__name__)


class App:
    """Central application controller launching the desktop WebView window."""

    def __init__(self):
        self.api = WontNoteAPI()
        self._close_request_lock = Lock()
        self._close_request_pending = False

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
        with self._close_request_lock:
            if self._close_request_pending:
                return False
            self._close_request_pending = True

        Thread(target=self._request_close, daemon=True).start()
        return False

    def _request_close(self):
        try:
            self.window.evaluate_js("void requestClose()")
        except Exception:
            logger.exception("Could not request application close from the UI.")
        finally:
            with self._close_request_lock:
                self._close_request_pending = False

    def run(self) -> None:
        """Start the pywebview event loop."""
        if sys.platform == "win32":
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                icon_path = Path(sys._MEIPASS) / "WontNote.ico"
            else:
                icon_path = Path(__file__).resolve().parents[2] / "WontNote.ico"
            webview.start(debug=False, icon=str(icon_path))
        else:
            webview.start(debug=False)
