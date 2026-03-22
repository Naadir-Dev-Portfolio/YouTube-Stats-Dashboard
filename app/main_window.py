"""QMainWindow shell — 3-tab layout, status bar, signal routing."""

from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QProgressBar,
    QTabWidget,
)

from app.config import get_api_key
from app.db.models import ChannelModel

from app.ui.dashboard_tab import DashboardTab
from app.ui.videos_tab import VideosTab
from app.ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Stats Dashboard")
        self.setMinimumSize(1280, 820)
        self._setup_ui()
        self._load_initial_channel()

    # ---------------------------------------------------------------- #
    # UI construction
    # ---------------------------------------------------------------- #

    def _setup_ui(self) -> None:
        # --- Status bar ---
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #a6adc8; padding-left: 4px;")

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)   # indeterminate spinner
        self._progress_bar.setFixedWidth(160)
        self._progress_bar.setFixedHeight(12)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(
            """
            QProgressBar {
                background: #313244;
                border-radius: 6px;
                border: none;
            }
            QProgressBar::chunk {
                background: #89b4fa;
                border-radius: 6px;
            }
            """
        )
        self.statusBar().addWidget(self._status_label)
        self.statusBar().addPermanentWidget(self._progress_bar)
        self.statusBar().setStyleSheet(
            "QStatusBar { background: #181825; color: #a6adc8; }"
        )

        # --- Tabs ---
        api_key = get_api_key() or ""

        self._dashboard = DashboardTab(api_key)
        self._videos = VideosTab()
        self._settings = SettingsTab()

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
                background: #1e1e2e;
            }
            QTabBar::tab {
                background: #181825;
                color: #a6adc8;
                padding: 8px 24px;
                border: none;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #313244;
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }
            QTabBar::tab:hover {
                background: #24273a;
                color: #cdd6f4;
            }
            """
        )
        self._tabs.addTab(self._dashboard, "Dashboard")
        self._tabs.addTab(self._videos, "Videos")
        self._tabs.addTab(self._settings, "Settings")
        self.setCentralWidget(self._tabs)

        # --- Signal wiring ---

        # Dashboard → status bar
        self._dashboard.fetch_started.connect(self._on_fetch_started)
        self._dashboard.fetch_progress.connect(self._on_fetch_progress)
        self._dashboard.fetch_finished.connect(self._on_fetch_finished)
        self._dashboard.fetch_error.connect(self._on_fetch_error)

        # Dashboard channel selection → Videos tab sync
        self._dashboard.channel_selected.connect(self._videos.load_channel)

        # Settings API key change → Dashboard
        self._settings.api_key_changed.connect(self._on_api_key_changed)

    # ---------------------------------------------------------------- #
    # Initial load
    # ---------------------------------------------------------------- #

    def _load_initial_channel(self) -> None:
        """Populate the channel list and pre-load the first channel."""
        self._dashboard.refresh_channel_list()
        channels = ChannelModel.all()
        if channels:
            first_id = channels[0]["channel_id"]
            self._videos.load_channel(first_id)

    # ---------------------------------------------------------------- #
    # Status bar slots
    # ---------------------------------------------------------------- #

    def _on_fetch_started(self) -> None:
        self._progress_bar.setVisible(True)
        self._status_label.setText("Fetching…")

    def _on_fetch_progress(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_fetch_finished(self, channel_id: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText("Fetch complete.")
        # Keep Videos tab in sync after a refresh
        self._videos.load_channel(channel_id)
        self._settings.refresh_quota()

    def _on_fetch_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Error: {msg}")

    # ---------------------------------------------------------------- #
    # Settings slots
    # ---------------------------------------------------------------- #

    def _on_api_key_changed(self, key: str) -> None:
        self._dashboard.set_api_key(key)
