"""Dashboard tab — channel sidebar + multi-chart analytics panel."""

import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QCursor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.db.models import ChannelModel, SnapshotModel, VideoModel
from app.workers.fetch_worker import AddChannelWorker, FetchWorker
from app.ui.chart_utils import (
    BG, BLUE, GRID, GREEN, MAUVE, PEACH, SUBTEXT, TEXT,
    make_figure_grid, style_axes,
)

# ------------------------------------------------------------------ #
# Design tokens
# ------------------------------------------------------------------ #
_BG       = "#0d0d1f"
_SURF0    = "#11111e"   # sidebar / header panels
_SURF1    = "#0d0d1f"   # page background
_SURF2    = "#181830"   # cards
_SURF2H   = "#1f1f3c"   # card hover
_BORDER   = "#252545"
_BORDER_H = "#4e4e90"
_BLUE_H   = "#a0b4ff"
_BLUE_P   = "#5a74e8"
_GREEN    = "#50dba8"
_RED      = "#ff6b8a"

# Consistent chart colours — cool-toned, not rainbow
_BAR_PRIMARY   = BLUE             # all bar charts
_BAR_ACCENT    = "#5a74e8"        # subtle second shade (for monthly)
_PIE_LIKED     = BLUE             # engaged — liked
_PIE_COMMENTED = MAUVE            # engaged — commented
_PIE_PASSIVE   = "#252550"        # passive — muted dark
_TREND_LINE    = PEACH            # warm contrast on trend line

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _fmt(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(
            iso.replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _moving_avg(values: list[float], window: int) -> list[float]:
    result = []
    half = window // 2
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        result.append(sum(values[lo:hi]) / (hi - lo))
    return result


def _set_card_value(card: QFrame, text: str) -> None:
    labels = card.findChildren(QLabel)
    if len(labels) >= 2:
        labels[1].setText(text)


def _make_card(label: str, value: str = "—", accent: str = BLUE) -> QFrame:
    frame = QFrame()
    frame.setObjectName("SummaryCard")
    frame.setStyleSheet(
        f"""
        QFrame#SummaryCard {{
            background: {_SURF2};
            border-radius: 10px;
            border: 1px solid {_BORDER};
        }}
        QFrame#SummaryCard:hover {{
            background: {_SURF2H};
            border: 1px solid {_BORDER_H};
        }}
        """
    )
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    vl = QVBoxLayout(frame)
    vl.setContentsMargins(16, 12, 16, 14)
    vl.setSpacing(5)

    lbl = QLabel(label.upper())
    lbl.setStyleSheet(
        f"color: {SUBTEXT}; font-size: 9px; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    vl.addWidget(lbl)

    val = QLabel(value)
    f = QFont()
    f.setPointSize(18)
    f.setBold(True)
    val.setFont(f)
    val.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
    val.setWordWrap(True)
    vl.addWidget(val)
    return frame


def _clean_ax(ax) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(False)


def _empty_text(ax, msg: str, title: str = "") -> None:
    _clean_ax(ax)
    if title:
        ax.set_title(title, color=TEXT, fontsize=9, pad=8)
    if msg:
        ax.text(
            0.5, 0.5, msg,
            ha="center", va="center",
            color=SUBTEXT, fontsize=9, linespacing=1.7,
            transform=ax.transAxes,
        )


def _preset_btn(label: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(24)
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: {_SURF2}; color: {SUBTEXT};
            border: 1px solid {_BORDER}; border-radius: 4px;
            padding: 0 10px; font-size: 11px;
        }}
        QPushButton:hover  {{ background: {_SURF2H}; color: {TEXT}; border-color: {_BORDER_H}; }}
        QPushButton:pressed {{ background: #252550; color: {BLUE}; }}
        """
    )
    return btn


# ------------------------------------------------------------------ #
# Avatar loader thread
# ------------------------------------------------------------------ #

class _AvatarLoader(QThread):
    loaded = pyqtSignal(bytes)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            with urllib.request.urlopen(self._url, timeout=8) as r:
                self.loaded.emit(r.read())
        except Exception:
            pass


# ------------------------------------------------------------------ #
# Dashboard tab
# ------------------------------------------------------------------ #

class DashboardTab(QWidget):
    fetch_started    = pyqtSignal()
    fetch_progress   = pyqtSignal(str)
    fetch_finished   = pyqtSignal(str)
    fetch_error      = pyqtSignal(str)
    channel_selected = pyqtSignal(str)

    def __init__(self, api_key: str):
        super().__init__()
        self._api_key  = api_key
        self._active_channel_id: str | None = None
        self._worker: FetchWorker | AddChannelWorker | None = None
        self._avatar_loader: _AvatarLoader | None = None

        # Hover data — filled after each draw
        self._timeline_hover: list[tuple] = []   # (x_index, y_val, tip)  — line chart points
        self._monthly_hover:  list[tuple] = []
        self._bar_hover:      list[tuple] = []   # horizontal bars

        self._build_ui()

    def set_api_key(self, key: str) -> None:
        self._api_key = key

    # ---------------------------------------------------------------- #
    # UI construction
    # ---------------------------------------------------------------- #

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setHandleWidth(1)
        sp.setStyleSheet("QSplitter::handle { background: #1e1e38; }")
        root.addWidget(sp)

        sp.addWidget(self._build_sidebar())
        sp.addWidget(self._build_content())
        sp.setStretchFactor(0, 0)
        sp.setStretchFactor(1, 1)
        sp.setSizes([220, 1060])

    # ---- Sidebar ------------------------------------------------- #

    def _build_sidebar(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(180)
        w.setMaximumWidth(260)
        w.setStyleSheet(f"background: {_SURF0};")

        vl = QVBoxLayout(w)
        vl.setContentsMargins(14, 18, 14, 18)
        vl.setSpacing(10)

        heading = QLabel("CHANNELS")
        heading.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; letter-spacing: 2px; font-weight: bold;"
        )
        vl.addWidget(heading)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"""
            QListWidget {{
                background: transparent; color: {TEXT};
                border: none; outline: 0; padding: 2px 0;
            }}
            QListWidget::item {{
                padding: 8px 10px; border-radius: 6px;
                margin: 1px 0; color: {SUBTEXT}; font-size: 12px;
            }}
            QListWidget::item:hover      {{ background: #1a1a32; color: {TEXT}; }}
            QListWidget::item:selected   {{
                background: #1e1e42; color: {BLUE};
                font-weight: bold;
                border-left: 2px solid {BLUE};
                padding-left: 8px;
            }}
            """
        )
        self._list.currentItemChanged.connect(self._on_channel_selected)
        vl.addWidget(self._list, stretch=1)

        self._btn_fetch = QPushButton("↻  Sync YouTube Data")
        self._btn_fetch.setObjectName("FetchBtn")
        self._btn_fetch.setToolTip(
            "Pull the latest statistics from the YouTube Data API\n"
            "for the selected channel. Required to update view counts,\n"
            "subscriber numbers and video data."
        )
        self._btn_fetch.setStyleSheet(
            f"""
            QPushButton#FetchBtn {{
                background: {BLUE}; color: #0d0d1f;
                border-radius: 6px; padding: 9px 0;
                font-weight: bold; font-size: 12px; border: none;
            }}
            QPushButton#FetchBtn:hover   {{ background: {_BLUE_H}; }}
            QPushButton#FetchBtn:pressed {{ background: {_BLUE_P}; }}
            QPushButton#FetchBtn:disabled {{
                background: #252545; color: #4a4a70;
            }}
            """
        )
        self._btn_fetch.setEnabled(False)
        self._btn_fetch.clicked.connect(self._on_fetch)
        vl.addWidget(self._btn_fetch)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_add = QPushButton("＋  Add")
        self._btn_add.setObjectName("AddBtn")
        self._btn_add.setToolTip("Add a YouTube channel by ID (UCxxxxxx) or @handle")
        self._btn_add.setStyleSheet(
            f"""
            QPushButton#AddBtn {{
                background: #182830; color: {_GREEN};
                border: 1px solid #254030; border-radius: 5px;
                padding: 6px 0; font-size: 11px;
            }}
            QPushButton#AddBtn:hover   {{ background: #1f3338; border-color: {_GREEN}; }}
            QPushButton#AddBtn:pressed {{ background: #0f1a1e; }}
            """
        )
        self._btn_add.clicked.connect(self._on_add)

        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setObjectName("RemoveBtn")
        self._btn_remove.setToolTip("Remove the selected channel and all its stored data")
        self._btn_remove.setStyleSheet(
            f"""
            QPushButton#RemoveBtn {{
                background: #281820; color: {_RED};
                border: 1px solid #402030; border-radius: 5px;
                padding: 6px 0; font-size: 11px;
            }}
            QPushButton#RemoveBtn:hover   {{ background: #331e28; border-color: {_RED}; }}
            QPushButton#RemoveBtn:pressed {{ background: #1a0f14; }}
            """
        )
        self._btn_remove.clicked.connect(self._on_remove)

        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        vl.addLayout(btn_row)

        self._sb_status = QLabel("")
        self._sb_status.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; padding-top: 2px;"
        )
        self._sb_status.setWordWrap(True)
        vl.addWidget(self._sb_status)
        return w

    # ---- Content area -------------------------------------------- #

    def _build_content(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_SURF1};")

        vl = QVBoxLayout(w)
        vl.setContentsMargins(20, 16, 20, 16)
        vl.setSpacing(12)

        vl.addWidget(self._build_header())

        # Stat cards
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self._card_subs  = _make_card("Subscribers",      "—")
        self._card_views = _make_card("Total views",       "—")
        self._card_delta = _make_card("30-day sub change", "—", _GREEN)
        self._card_top   = _make_card("Top video",         "—", PEACH)
        for c in (self._card_subs, self._card_views,
                  self._card_delta, self._card_top):
            cards.addWidget(c)
        vl.addLayout(cards)

        vl.addWidget(self._build_date_filter())

        # 2×2 chart canvas
        self._fig = make_figure_grid(width_in=12, height_in=6.8)
        self._gs  = GridSpec(
            2, 2, figure=self._fig,
            hspace=0.55, wspace=0.30,
            left=0.07, right=0.97,
            top=0.93, bottom=0.14,
        )
        self._ax_timeline = self._fig.add_subplot(self._gs[0, 0], facecolor=BG)
        self._ax_monthly  = self._fig.add_subplot(self._gs[0, 1], facecolor=BG)
        self._ax_pie      = self._fig.add_subplot(self._gs[1, 0], facecolor=BG)
        self._ax_bar      = self._fig.add_subplot(self._gs[1, 1], facecolor=BG)
        for ax in (self._ax_timeline, self._ax_monthly,
                   self._ax_pie, self._ax_bar):
            _empty_text(ax, "")

        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(360)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas.setStyleSheet(
            f"background: {_SURF0}; border-radius: 10px;"
        )
        # Hover tooltips on chart
        self._canvas.mpl_connect("motion_notify_event", self._on_chart_hover)
        vl.addWidget(self._canvas, stretch=1)
        return w

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background: {_SURF0}; border-radius: 10px;
                border-left: 3px solid {BLUE};
            }}
            """
        )
        frame.setFixedHeight(70)

        row = QHBoxLayout(frame)
        row.setContentsMargins(18, 10, 18, 10)
        row.setSpacing(14)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(46, 46)
        self._avatar_label.setStyleSheet(
            "border-radius: 23px; background: #252545; border: none;"
        )
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._avatar_label)

        info = QVBoxLayout()
        info.setSpacing(2)
        self._title_label = QLabel("No channel loaded — add one in the sidebar")
        tf = QFont(); tf.setPointSize(13); tf.setBold(True)
        self._title_label.setFont(tf)
        self._title_label.setStyleSheet(
            f"color: {TEXT}; background: transparent; border: none;"
        )
        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 11px; background: transparent; border: none;"
        )
        info.addWidget(self._title_label)
        info.addWidget(self._subtitle_label)
        row.addLayout(info)
        row.addStretch()
        return frame

    def _build_date_filter(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_SURF0}; border-radius: 8px;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(8)

        lbl = QLabel("Date range")
        lbl.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; letter-spacing: 0.8px;"
            " font-weight: bold; background: transparent;"
        )
        hl.addWidget(lbl)

        presets = [
            ("2M",  60,  "Videos published in the last 2 months"),
            ("3M",  90,  "Videos published in the last 3 months"),
            ("6M",  180, "Videos published in the last 6 months"),
            ("1Y",  365, "Videos published in the last year"),
            ("All", 0,   "All videos ever published on this channel"),
        ]
        for label, days, tip in presets:
            btn = _preset_btn(label)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _, d=days: self._apply_preset(d))
            hl.addWidget(btn)

        hl.addSpacing(6)

        _ds = (
            f"background: {_SURF2}; color: {TEXT};"
            f" border: 1px solid {_BORDER}; border-radius: 4px;"
            " padding: 2px 6px; font-size: 11px;"
        )

        from_lbl = QLabel("From")
        from_lbl.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; background: transparent;"
        )
        hl.addWidget(from_lbl)

        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDate(QDate.currentDate().addDays(-60))
        self._date_from.setStyleSheet(_ds)
        self._date_from.setFixedHeight(26)
        self._date_from.setToolTip("Start of the date range (video publish date)")
        hl.addWidget(self._date_from)

        to_lbl = QLabel("To")
        to_lbl.setStyleSheet(
            f"color: {SUBTEXT}; font-size: 10px; background: transparent;"
        )
        hl.addWidget(to_lbl)

        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setStyleSheet(_ds)
        self._date_to.setFixedHeight(26)
        self._date_to.setToolTip("End of the date range (video publish date)")
        hl.addWidget(self._date_to)

        apply_btn = QPushButton("Apply")
        apply_btn.setFixedHeight(26)
        apply_btn.setToolTip("Redraw the top charts using the selected date range")
        apply_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {BLUE}; color: #0d0d1f;
                border-radius: 4px; padding: 0 14px;
                font-size: 11px; font-weight: bold; border: none;
            }}
            QPushButton:hover   {{ background: {_BLUE_H}; }}
            QPushButton:pressed {{ background: {_BLUE_P}; }}
            """
        )
        apply_btn.clicked.connect(self._on_apply_dates)
        hl.addWidget(apply_btn)

        hl.addStretch()
        return w

    # ---------------------------------------------------------------- #
    # Channel list
    # ---------------------------------------------------------------- #

    def refresh_channel_list(self) -> None:
        prev = self._active_channel_id
        self._list.blockSignals(True)
        self._list.clear()
        for ch in ChannelModel.all():
            item = QListWidgetItem(ch["title"] or ch["channel_id"])
            item.setData(Qt.ItemDataRole.UserRole, ch["channel_id"])
            self._list.addItem(item)
        self._list.blockSignals(False)

        if prev:
            for i in range(self._list.count()):
                if self._list.item(i).data(Qt.ItemDataRole.UserRole) == prev:
                    self._list.setCurrentRow(i)
                    return
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_channel_selected(
        self, current: QListWidgetItem | None, _prev
    ) -> None:
        if current is None:
            return
        cid = current.data(Qt.ItemDataRole.UserRole)
        self._active_channel_id = cid
        self._btn_fetch.setEnabled(True)
        self.load_channel(cid)
        self.channel_selected.emit(cid)

    # ---------------------------------------------------------------- #
    # Add / Remove
    # ---------------------------------------------------------------- #

    def _on_add(self) -> None:
        if not self._api_key:
            QMessageBox.warning(
                self, "No API Key",
                "Set your YouTube API key in the Settings tab first.",
            )
            return
        text, ok = QInputDialog.getText(
            self, "Add Channel",
            "Enter a YouTube channel ID (UCxxxxxx) or @handle:",
        )
        if not ok or not text.strip():
            return
        self._set_buttons_enabled(False)
        self._sb_status.setText(f"Adding {text.strip()}…")
        self.fetch_started.emit()
        self._worker = AddChannelWorker(self._api_key, text.strip())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_add_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_add_finished(self, info: dict) -> None:
        self._set_buttons_enabled(True)
        self._sb_status.setText(f"Added: {info['title']}")
        self._active_channel_id = info["channel_id"]
        self.refresh_channel_list()
        self.fetch_finished.emit(info["channel_id"])

    def _on_remove(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        cid     = item.data(Qt.ItemDataRole.UserRole)
        channel = ChannelModel.get(cid)
        title   = channel["title"] if channel else cid
        reply   = QMessageBox.question(
            self, "Remove channel",
            f"Remove '{title}' and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ChannelModel.delete(cid)
        self._active_channel_id = None
        self._btn_fetch.setEnabled(False)
        self._title_label.setText("No channel loaded — add one in the sidebar")
        self._subtitle_label.setText("")
        self.refresh_channel_list()

    # ---------------------------------------------------------------- #
    # Fetch
    # ---------------------------------------------------------------- #

    def fetch_channel(self, channel_id: str, force: bool = False) -> None:
        if not self._api_key:
            QMessageBox.warning(
                self, "No API Key",
                "Set your YouTube API key in the Settings tab first.",
            )
            return
        self._set_buttons_enabled(False)
        self._sb_status.setText("Fetching…")
        self.fetch_started.emit()
        self._worker = FetchWorker(self._api_key, channel_id, force=force)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_fetch_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_fetch(self) -> None:
        if self._active_channel_id:
            self.fetch_channel(self._active_channel_id)

    def _on_fetch_done(self, cid: str) -> None:
        self._set_buttons_enabled(True)
        self._sb_status.setText("Done.")
        self.load_channel(cid)
        self.refresh_channel_list()
        self.fetch_finished.emit(cid)

    def _on_progress(self, msg: str) -> None:
        self._sb_status.setText(msg)
        self.fetch_progress.emit(msg)

    def _on_error(self, msg: str) -> None:
        self._set_buttons_enabled(True)
        self._sb_status.setText("Error")
        QMessageBox.critical(self, "Fetch Error", msg)
        self.fetch_error.emit(msg)

    def _set_buttons_enabled(self, en: bool) -> None:
        self._btn_add.setEnabled(en)
        self._btn_remove.setEnabled(en)
        self._btn_fetch.setEnabled(en and self._active_channel_id is not None)

    # ---------------------------------------------------------------- #
    # Date range
    # ---------------------------------------------------------------- #

    def _apply_preset(self, days: int) -> None:
        today = QDate.currentDate()
        self._date_to.setDate(today)
        self._date_from.setDate(
            QDate(2000, 1, 1) if days == 0 else today.addDays(-days)
        )
        if self._active_channel_id:
            self._draw_date_charts(self._active_channel_id)

    def _on_apply_dates(self) -> None:
        if self._active_channel_id:
            self._draw_date_charts(self._active_channel_id)

    def _current_range(self) -> tuple[datetime, datetime]:
        qf = self._date_from.date()
        qt = self._date_to.date()
        return (
            datetime(qf.year(), qf.month(), qf.day()),
            datetime(qt.year(), qt.month(), qt.day(), 23, 59, 59),
        )

    # ---------------------------------------------------------------- #
    # Data loading
    # ---------------------------------------------------------------- #

    def load_channel(self, cid: str) -> None:
        self._active_channel_id = cid
        channel = ChannelModel.get(cid)
        if not channel:
            return

        self._title_label.setText(channel["title"] or cid)
        snap = SnapshotModel.latest(cid)
        if snap:
            handle = channel.get("handle") or ""
            h_str  = f"@{handle.lstrip('@')}  ·  " if handle else ""
            self._subtitle_label.setText(
                f"{h_str}"
                f"{_fmt(snap['subscribers'])} subscribers  ·  "
                f"{_fmt(snap['total_views'])} total views"
            )
            self._update_cards(cid, snap)
        else:
            self._subtitle_label.setText(
                "No data yet — click Sync YouTube Data to pull statistics"
            )

        thumb = channel.get("thumbnail_url", "")
        if thumb:
            if self._avatar_loader and self._avatar_loader.isRunning():
                self._avatar_loader.terminate()
            self._avatar_loader = _AvatarLoader(thumb)
            self._avatar_loader.loaded.connect(self._on_avatar_loaded)
            self._avatar_loader.start()

        self._draw_date_charts(cid)
        self._draw_pie(cid)
        self._draw_bar(cid)
        self._canvas.draw()

    def _update_cards(self, cid: str, latest: dict) -> None:
        _set_card_value(self._card_subs,  _fmt(latest["subscribers"]))
        _set_card_value(self._card_views, _fmt(latest["total_views"]))

        history = SnapshotModel.history(cid, limit=90)
        if len(history) >= 2:
            cutoff = datetime.utcnow() - timedelta(days=30)
            old    = next(
                (s for s in history
                 if datetime.fromisoformat(s["fetched_at"]) <= cutoff),
                history[0],
            )
            delta = (latest["subscribers"] or 0) - (old["subscribers"] or 0)
            _set_card_value(self._card_delta, f"{'+'if delta>=0 else ''}{_fmt(delta)}")
        else:
            _set_card_value(self._card_delta, "—")

        top = VideoModel.top_by_views(cid, limit=1)
        if top:
            v = top[0]; t = v["title"]
            _set_card_value(self._card_top,
                            f"{(t[:34]+'…') if len(t)>34 else t}\n{_fmt(v['views'])} views")
        else:
            _set_card_value(self._card_top, "No data yet")

    # ---------------------------------------------------------------- #
    # Chart drawing — date-filtered (top row)
    # ---------------------------------------------------------------- #

    def _draw_date_charts(self, cid: str) -> None:
        all_videos = VideoModel.for_channel(cid)
        start, end = self._current_range()
        in_range   = sorted(
            [v for v in all_videos
             if (dt := _parse_dt(v.get("published_at"))) and start <= dt <= end],
            key=lambda v: v.get("published_at") or "",
        )
        self._draw_timeline(in_range, start, end)
        self._draw_monthly(in_range)
        self._canvas.draw()

    def _draw_timeline(
        self, videos: list[dict], start: datetime, end: datetime
    ) -> None:
        """Line chart — views per video by publish date."""
        ax = self._ax_timeline
        ax.clear()
        ax.set_facecolor(BG)
        self._timeline_hover = []
        title = "Video views by publish date"

        if not videos:
            _empty_text(ax,
                        "No videos published in this date range.\n"
                        "Try a wider window using the presets above.",
                        title)
            return

        style_axes(ax)

        # Sort by publish date and build (x_index, views, label) triples
        sorted_vids = sorted(
            [v for v in videos if _parse_dt(v.get("published_at"))],
            key=lambda v: v["published_at"],
        )
        x_vals  = list(range(len(sorted_vids)))
        y_vals  = [v.get("views") or 0 for v in sorted_vids]
        labels  = [
            _parse_dt(v["published_at"]).strftime("%d %b '%y")
            for v in sorted_vids
        ]
        titles  = [v.get("title") or "" for v in sorted_vids]

        # Line + markers
        ax.plot(x_vals, y_vals, color=_BAR_PRIMARY, linewidth=1.8,
                alpha=0.9, zorder=4)
        ax.scatter(x_vals, y_vals, color=_BAR_PRIMARY, s=28,
                   zorder=5, alpha=0.95)

        # Dashed trend line overlay
        if len(y_vals) >= 3:
            ma = _moving_avg(y_vals, min(5, max(3, len(y_vals) // 4)))
            ax.plot(x_vals, ma, color=_TREND_LINE, linewidth=1.6,
                    linestyle="--", alpha=0.85, zorder=6)

        # X-axis labels — show every Nth to avoid crowding
        step = max(1, len(x_vals) // 8)
        ax.set_xticks(x_vals[::step])
        ax.set_xticklabels(labels[::step], rotation=30, ha="right",
                           fontsize=6, color=SUBTEXT)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: _fmt(int(v)))
        )
        ax.set_ylabel("Views", color=SUBTEXT, fontsize=7)
        ax.set_title(
            f"{title}  ·  {len(sorted_vids)} video{'s' if len(sorted_vids)!=1 else ''}",
            color=TEXT, fontsize=9, pad=8,
        )

        # Hover data — store (x_index, y_val, tooltip_text) for each point
        for xi, yi, lbl, ttl in zip(x_vals, y_vals, labels, titles):
            short = (ttl[:38] + "…") if len(ttl) > 38 else ttl
            self._timeline_hover.append((xi, yi, f"{lbl}\n{short}\n{_fmt(yi)} views"))

    def _draw_monthly(self, videos: list[dict]) -> None:
        """Bar chart of video count + views per publish month."""
        ax = self._ax_monthly
        ax.clear()
        ax.set_facecolor(BG)
        self._monthly_hover = []
        title = "Monthly totals (publish date)"

        if not videos:
            _empty_text(ax,
                        "No videos published in this date range.\n"
                        "Try a wider window using the presets above.",
                        title)
            return

        style_axes(ax)

        monthly_views: dict[str, int]      = defaultdict(int)
        monthly_count: dict[str, int]      = defaultdict(int)
        month_order:   dict[str, datetime] = {}

        for v in videos:
            dt = _parse_dt(v.get("published_at"))
            if not dt:
                continue
            key = dt.strftime("%b '%y")
            monthly_views[key] += v.get("views") or 0
            monthly_count[key] += 1
            if key not in month_order:
                month_order[key] = dt.replace(day=1)

        labels = sorted(monthly_views.keys(),
                        key=lambda k: month_order.get(k, datetime.min))
        values = [monthly_views[k] for k in labels]
        counts = [monthly_count[k] for k in labels]

        x    = list(range(len(labels)))
        bars = ax.bar(x, values, color=_BAR_ACCENT, alpha=0.85, width=0.6)

        step = max(1, len(labels) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], rotation=30, ha="right",
                           fontsize=6, color=SUBTEXT)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: _fmt(int(v)))
        )
        ax.set_ylabel("Total views", color=SUBTEXT, fontsize=7)
        ax.set_title(title, color=TEXT, fontsize=9, pad=8)

        for bar, lbl, val, cnt in zip(bars, labels, values, counts):
            self._monthly_hover.append((
                bar.get_x(),
                bar.get_x() + bar.get_width(),
                bar.get_height(),
                f"{lbl}  ·  {cnt} video{'s' if cnt!=1 else ''}\n{_fmt(val)} total views",
            ))

    # ---------------------------------------------------------------- #
    # Chart drawing — all-time (bottom row)
    # ---------------------------------------------------------------- #

    def _draw_pie(self, cid: str) -> None:
        videos = VideoModel.for_channel(cid)
        ax     = self._ax_pie
        ax.clear()
        ax.set_facecolor(BG)
        title = "Engagement breakdown"

        if not videos:
            _empty_text(ax, "No video data yet.\nSync channel data to populate.", title)
            return

        total_likes    = sum(v["likes"]    or 0 for v in videos)
        total_comments = sum(v["comments"] or 0 for v in videos)
        total_views    = sum(v["views"]    or 0 for v in videos)
        engaged        = total_likes + total_comments
        passive        = max(0, total_views - engaged)

        if total_views == 0:
            _empty_text(ax, "No view data available.", title)
            return

        pct = lambda n: n / total_views * 100  # noqa

        # Draw pie — passive section is muted so engaged sections pop
        wedges, _, autotexts = ax.pie(
            [total_likes, total_comments, passive],
            colors=[_PIE_LIKED, _PIE_COMMENTED, _PIE_PASSIVE],
            autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"linewidth": 1.5, "edgecolor": _BG},
            pctdistance=0.72,
            labeldistance=None,   # suppress outer labels — use legend instead
        )
        for at in autotexts:
            at.set_color(TEXT)
            at.set_fontweight("bold")
            at.set_fontsize(7)

        # Clean, self-contained legend inside the axes
        legend_handles = [
            Patch(facecolor=_PIE_LIKED,     edgecolor="none",
                  label=f"Liked  ·  {_fmt(total_likes)}  ({pct(total_likes):.1f}%)"),
            Patch(facecolor=_PIE_COMMENTED, edgecolor="none",
                  label=f"Commented  ·  {_fmt(total_comments)}  ({pct(total_comments):.1f}%)"),
            Patch(facecolor="#4a4a80",       edgecolor="none",
                  label=f"Watched only  ·  {_fmt(passive)}  ({pct(passive):.1f}%)"),
        ]
        ax.legend(
            handles=legend_handles,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.28),
            frameon=True,
            framealpha=0.0,
            facecolor=_SURF0,
            edgecolor=_BORDER,
            labelcolor=SUBTEXT,
            fontsize=7.5,
            ncol=1,
            handlelength=1.2,
            borderpad=0.6,
        )

        eng_pct = pct(engaged)
        ax.set_title(
            f"{title}  ·  {eng_pct:.2f}% engagement rate",
            color=TEXT, fontsize=9, pad=8,
        )

    def _draw_bar(self, cid: str) -> None:
        videos = VideoModel.for_channel(cid)
        ax     = self._ax_bar
        ax.clear()
        ax.set_facecolor(BG)
        self._bar_hover = []
        title = "Top videos by engagement rate"

        rated = [
            (v["title"],
             ((v["likes"] or 0) + (v["comments"] or 0)) / v["views"] * 100,
             v["views"] or 0)
            for v in videos
            if (v["views"] or 0) > 0
        ]
        rated.sort(key=lambda x: x[1], reverse=True)
        top = rated[:8]

        if not top:
            _empty_text(ax, "No engagement data yet.\nSync channel data to populate.", title)
            return

        style_axes(ax)
        labels = [(t[:26] + "…") if len(t) > 26 else t for t, _, _ in top]
        rates  = [r for _, r, _ in top]
        views  = [v for _, _, v in top]
        full_titles = [t for t, _, _ in top]

        # Single primary colour — fade by rank using alpha via RGBA
        from matplotlib.colors import to_rgba
        base_rgba = to_rgba(_BAR_PRIMARY)
        bar_colors = [
            (base_rgba[0], base_rgba[1], base_rgba[2],
             1.0 - (i / max(len(top) - 1, 1)) * 0.45)
            for i in range(len(top))
        ]

        bars = ax.barh(range(len(top)), rates, color=bar_colors, height=0.55)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(labels, color=SUBTEXT, fontsize=7)
        ax.invert_yaxis()
        ax.set_xlabel(
            "(likes + comments) ÷ views × 100",
            color=SUBTEXT, fontsize=6.5,
        )
        ax.set_title(title, color=TEXT, fontsize=9, pad=8)

        for bar, rate in zip(bars, rates):
            ax.text(
                bar.get_width() + max(rates) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{rate:.2f}%",
                va="center", color=TEXT, fontsize=6.5,
            )

        # Hover data for horizontal bars
        for bar, ft, rate, vc in zip(bars, full_titles, rates, views):
            self._bar_hover.append((
                bar.get_y(),
                bar.get_y() + bar.get_height(),
                bar.get_width(),
                f"{ft}\n{_fmt(vc)} views  ·  {rate:.2f}% engagement",
            ))

    # ---------------------------------------------------------------- #
    # Chart hover tooltips
    # ---------------------------------------------------------------- #

    def _on_chart_hover(self, event) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            QToolTip.hideText()
            return

        tip = None
        ax, x, y = event.inaxes, event.xdata, event.ydata

        if ax is self._ax_timeline:
            tip = self._hit_point(x, y, self._timeline_hover)
        elif ax is self._ax_monthly:
            tip = self._hit_vbar(x, y, self._monthly_hover)
        elif ax is self._ax_bar:
            tip = self._hit_hbar(x, y, self._bar_hover)

        if tip:
            QToolTip.showText(QCursor.pos(), tip)
        else:
            QToolTip.hideText()

    @staticmethod
    def _hit_point(x, y, data, radius: float = 0.6):
        """Hit-test scatter/line chart points. data = [(xi, yi, tip), ...]."""
        best_d, best_tip = radius, None
        for (xi, yi, tip) in data:
            d = abs(x - xi)
            if d < best_d:
                best_d, best_tip = d, tip
        return best_tip

    @staticmethod
    def _hit_vbar(x, y, data):
        for (x0, x1, height, label) in data:
            if x0 <= x <= x1 and 0 <= y <= height:
                return label
        return None

    @staticmethod
    def _hit_hbar(x, y, data):
        for (y0, y1, width, label) in data:
            if y0 <= y <= y1 and 0 <= x <= width:
                return label
        return None

    # ---------------------------------------------------------------- #
    # Avatar
    # ---------------------------------------------------------------- #

    def _on_avatar_loaded(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            px = px.scaled(
                46, 46,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._avatar_label.setPixmap(px)
