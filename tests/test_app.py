from threading import Lock

import wontnote.gui.app as app_module


def test_unlocked_close_dispatches_javascript_off_ui_thread(monkeypatch):
    scheduled = []

    class DeferredThread:
        def __init__(self, *, target, daemon):
            scheduled.append((target, daemon))

        def start(self):
            pass

    class API:
        _master_key = bytearray(b"unlocked")
        _allow_close = False

    class Window:
        evaluated_scripts = []

        def evaluate_js(self, script):
            self.evaluated_scripts.append(script)

    monkeypatch.setattr(app_module, "Thread", DeferredThread)
    app = app_module.App.__new__(app_module.App)
    app.api = API()
    app.window = Window()
    app._close_request_lock = Lock()
    app._close_request_pending = False

    assert app._on_closing() is False
    assert app.window.evaluated_scripts == []
    assert len(scheduled) == 1
    target, daemon = scheduled[0]
    assert daemon

    target()
    assert app.window.evaluated_scripts == ["void requestClose()"]
    assert not app._close_request_pending


def test_repeated_close_event_does_not_queue_duplicate_javascript(monkeypatch):
    scheduled = []

    class DeferredThread:
        def __init__(self, *, target, daemon):
            scheduled.append(target)

        def start(self):
            pass

    class API:
        _master_key = bytearray(b"unlocked")
        _allow_close = False

    class Window:
        def evaluate_js(self, script):
            pass

    monkeypatch.setattr(app_module, "Thread", DeferredThread)
    app = app_module.App.__new__(app_module.App)
    app.api = API()
    app.window = Window()
    app._close_request_lock = Lock()
    app._close_request_pending = False

    assert app._on_closing() is False
    assert app._on_closing() is False
    assert len(scheduled) == 1
