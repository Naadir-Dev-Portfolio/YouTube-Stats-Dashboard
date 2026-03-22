"""Settings tab — API key management, quota display, data directory info."""

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.api.quota_tracker import QuotaTracker
from app.config import (
    get_api_key, save_config,
    DATA_DIR, DB_PATH,
    QUOTA_DAILY_LIMIT, QUOTA_WARNING_THRESHOLD,
)
from app.ui.chart_utils import TEXT, SUBTEXT, BLUE, GREEN, PEACH, RED, GRID


class SettingsTab(QWidget):
    api_key_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._quota = QuotaTracker()
        self._build_ui()
        self.refresh_quota()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(24)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # API key section
        root.addWidget(self._section_label("API Key"))
        api_frame = self._card()
        api_layout = QVBoxLayout(api_frame)
        api_layout.setSpacing(10)

        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("AIza…")
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setText(get_api_key() or "")
        self._key_edit.setStyleSheet(
            f"background: #313244; color: {TEXT}; border: 1px solid {GRID};"
            " border-radius: 4px; padding: 5px 8px; font-family: monospace;"
        )

        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setStyleSheet(
            f"background: #313244; color: {SUBTEXT}; border: 1px solid {GRID};"
            " border-radius: 4px; padding: 5px 12px;"
        )
        self._show_key_btn.toggled.connect(self._toggle_key_visibility)

        save_btn = QPushButton("Save key")
        save_btn.setStyleSheet(
            f"background: {BLUE}; color: #1e1e2e; border-radius: 4px;"
            " padding: 5px 16px; font-weight: bold;"
        )
        save_btn.clicked.connect(self._on_save_key)

        key_row.addWidget(self._key_edit, stretch=1)
        key_row.addWidget(self._show_key_btn)
        key_row.addWidget(save_btn)
        api_layout.addLayout(key_row)

        note = QLabel(
            "The key is stored in api_config.json (gitignored). "
            "It is never committed to git."
        )
        note.setStyleSheet(f"color: {SUBTEXT}; font-size: 10px;")
        note.setWordWrap(True)
        api_layout.addWidget(note)
        root.addWidget(api_frame)

        # Quota section
        root.addWidget(self._section_label("API Quota"))
        quota_frame = self._card()
        quota_layout = QVBoxLayout(quota_frame)
        quota_layout.setSpacing(10)

        self._quota_label = QLabel("")
        self._quota_label.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        quota_layout.addWidget(self._quota_label)

        self._quota_bar = QProgressBar()
        self._quota_bar.setRange(0, QUOTA_DAILY_LIMIT)
        self._quota_bar.setTextVisible(False)
        self._quota_bar.setFixedHeight(10)
        quota_layout.addWidget(self._quota_bar)

        quota_warn = QLabel(
            f"Fetches are blocked above {QUOTA_WARNING_THRESHOLD:,} units "
            f"(80 % of {QUOTA_DAILY_LIMIT:,} daily limit)."
        )
        quota_warn.setStyleSheet(f"color: {SUBTEXT}; font-size: 10px;")
        quota_layout.addWidget(quota_warn)

        quota_btn_row = QHBoxLayout()
        quota_btn_row.setSpacing(10)

        btn_reset_quota = QPushButton("Reset quota counter")
        btn_reset_quota.setStyleSheet(
            f"background: #313244; color: {PEACH}; border: 1px solid {GRID};"
            " border-radius: 4px; padding: 5px 14px;"
        )
        btn_reset_quota.clicked.connect(self._on_reset_quota)

        btn_refresh = QPushButton("Refresh display")
        btn_refresh.setStyleSheet(
            f"background: #313244; color: {SUBTEXT}; border: 1px solid {GRID};"
            " border-radius: 4px; padding: 5px 14px;"
        )
        btn_refresh.clicked.connect(self.refresh_quota)

        quota_btn_row.addWidget(btn_reset_quota)
        quota_btn_row.addWidget(btn_refresh)
        quota_btn_row.addStretch()
        quota_layout.addLayout(quota_btn_row)
        root.addWidget(quota_frame)

        # Data / storage section
        root.addWidget(self._section_label("Data"))
        data_frame = self._card()
        data_layout = QVBoxLayout(data_frame)
        data_layout.setSpacing(8)

        db_label = QLabel(f"Database: {DB_PATH}")
        db_label.setStyleSheet(f"color: {SUBTEXT}; font-size: 10px; font-family: monospace;")
        db_label.setWordWrap(True)
        data_layout.addWidget(db_label)

        dir_label = QLabel(f"Data directory: {DATA_DIR}")
        dir_label.setStyleSheet(f"color: {SUBTEXT}; font-size: 10px; font-family: monospace;")
        dir_label.setWordWrap(True)
        data_layout.addWidget(dir_label)
        root.addWidget(data_frame)

        root.addStretch()

    # ---------------------------------------------------------------- #
    # Helpers
    # ---------------------------------------------------------------- #

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; letter-spacing: 1px;"
        )
        return lbl

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #181825; border-radius: 8px; }"
        )
        return frame

    # ---------------------------------------------------------------- #
    # Slots
    # ---------------------------------------------------------------- #

    def refresh_quota(self) -> None:
        self._quota = QuotaTracker()
        used = self._quota.used()
        remaining = self._quota.remaining()
        self._quota_label.setText(
            f"{used:,} / {QUOTA_DAILY_LIMIT:,} units used today  —  "
            f"{remaining:,} remaining"
        )
        self._quota_bar.setValue(used)

        color = GREEN if used < QUOTA_WARNING_THRESHOLD else RED
        self._quota_bar.setStyleSheet(
            f"""
            QProgressBar::chunk {{
                background: {color};
                border-radius: 5px;
            }}
            QProgressBar {{
                background: #313244;
                border-radius: 5px;
                border: none;
            }}
            """
        )

    def _on_save_key(self) -> None:
        key = self._key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Empty key", "Please enter an API key.")
            return
        save_config({"api_key": key})
        self.api_key_changed.emit(key)
        QMessageBox.information(self, "Saved", "API key saved to api_config.json.")

    def _on_reset_quota(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset quota counter",
            "Reset the local quota counter to 0?\n\n"
            "Only do this when Google's daily quota has actually reset (midnight Pacific).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._quota.reset()
            self.refresh_quota()

    def _toggle_key_visibility(self, checked: bool) -> None:
        if checked:
            self._key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")
