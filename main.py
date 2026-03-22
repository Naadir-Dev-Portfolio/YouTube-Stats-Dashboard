"""Entry point for YouTube Stats Dashboard."""

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtGui import QPalette, QColor, QFont
from PyQt6.QtCore import Qt

from app.config import get_api_key, save_config, DATA_DIR
from app.db.database import Database
from app.main_window import MainWindow

# Catppuccin Mocha palette
_BG = QColor("#1e1e2e")
_SURFACE = QColor("#313244")
_SURFACE2 = QColor("#45475a")
_TEXT = QColor("#cdd6f4")
_SUBTEXT = QColor("#a6adc8")
_BLUE = QColor("#89b4fa")


def _apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, _BG)
    pal.setColor(QPalette.ColorRole.WindowText, _TEXT)
    pal.setColor(QPalette.ColorRole.Base, _SURFACE)
    pal.setColor(QPalette.ColorRole.AlternateBase, _SURFACE2)
    pal.setColor(QPalette.ColorRole.ToolTipBase, _SURFACE)
    pal.setColor(QPalette.ColorRole.ToolTipText, _TEXT)
    pal.setColor(QPalette.ColorRole.Text, _TEXT)
    pal.setColor(QPalette.ColorRole.Button, _SURFACE)
    pal.setColor(QPalette.ColorRole.ButtonText, _TEXT)
    pal.setColor(QPalette.ColorRole.BrightText, _TEXT)
    pal.setColor(QPalette.ColorRole.Highlight, _BLUE)
    pal.setColor(QPalette.ColorRole.HighlightedText, _BG)
    pal.setColor(QPalette.ColorRole.PlaceholderText, _SUBTEXT)
    # Disabled
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, _SUBTEXT)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, _SUBTEXT)
    app.setPalette(pal)


def _show_setup_dialog() -> str | None:
    """Modal dialog shown on first launch when no API key is configured."""
    dialog = QDialog()
    dialog.setWindowTitle("YouTube Stats Dashboard — First-time Setup")
    dialog.setMinimumWidth(460)
    dialog.setStyleSheet("QDialog { background: #1e1e2e; }")

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    title = QLabel("Welcome to YouTube Stats Dashboard")
    font = QFont()
    font.setPointSize(14)
    font.setBold(True)
    title.setFont(font)
    title.setStyleSheet("color: #cdd6f4;")
    layout.addWidget(title)

    body = QLabel(
        "To get started, enter your YouTube Data API v3 key below.\n\n"
        "You can obtain one from the Google Cloud Console under "
        "APIs & Services → Credentials.\n\n"
        "The key is stored locally in api_config.json and is never committed to git."
    )
    body.setWordWrap(True)
    body.setStyleSheet("color: #a6adc8; font-size: 12px;")
    layout.addWidget(body)

    key_edit = QLineEdit()
    key_edit.setPlaceholderText("AIzaSy…")
    key_edit.setStyleSheet(
        "background: #313244; color: #cdd6f4; border: 1px solid #45475a;"
        " border-radius: 4px; padding: 6px 10px; font-family: monospace;"
    )
    layout.addWidget(key_edit)

    save_btn = QPushButton("Save and open dashboard")
    save_btn.setStyleSheet(
        "background: #89b4fa; color: #1e1e2e; border-radius: 5px;"
        " padding: 8px 0; font-weight: bold; font-size: 13px;"
    )
    layout.addWidget(save_btn)

    skip_btn = QPushButton("Skip for now (limited functionality)")
    skip_btn.setStyleSheet(
        "background: transparent; color: #6c7086; border: none; font-size: 11px;"
    )
    layout.addWidget(skip_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    result: list[str] = []

    def on_save() -> None:
        key = key_edit.text().strip()
        if not key:
            QMessageBox.warning(dialog, "Empty key", "Please enter an API key.")
            return
        save_config({"api_key": key})
        result.append(key)
        dialog.accept()

    save_btn.clicked.connect(on_save)
    skip_btn.clicked.connect(dialog.reject)
    key_edit.returnPressed.connect(on_save)

    dialog.exec()
    return result[0] if result else None


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Stats Dashboard")
    _apply_dark_palette(app)

    # Ensure data directory and database exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Database.get()

    # First-launch setup if no API key stored
    if not get_api_key():
        _show_setup_dialog()
        # Continue even if skipped — settings tab allows adding the key later

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
