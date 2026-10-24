"""
main.py — WontNote Application Entry Point
===========================================
Launches the modern WontNote desktop application.
"""


def main() -> None:
    """Start the WontNote desktop application."""
    from wontnote.gui.app import App
    App().run()


if __name__ == "__main__":
    main()
