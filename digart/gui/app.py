"""Application setup."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from digart.gui.fonts import load_fonts


def _resolve_style_path() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "styles" / "dark.qss"


def create_app() -> QApplication:
    """Create and configure the QApplication."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    app.setStyle("Fusion")
    try:
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    except Exception:
        pass
    try:
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    load_fonts()

    # Default font.
    font = QFont("Space Grotesk", 11)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Load and apply stylesheet.
    style_path = _resolve_style_path()
    if style_path.exists():
        try:
            app.setStyleSheet(style_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return app
