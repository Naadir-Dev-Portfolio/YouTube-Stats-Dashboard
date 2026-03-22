"""Videos tab — sortable table with search and per-video detail panel."""

from datetime import datetime

from PyQt6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.db.models import VideoModel
from app.ui.chart_utils import BG, TEXT, SUBTEXT, BLUE, GRID, SURFACE

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _fmt(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None or seconds == 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


# ------------------------------------------------------------------ #
# Table model
# ------------------------------------------------------------------ #

COLUMNS = ["Title", "Published", "Views", "Likes", "Comments", "Eng. Rate", "Duration"]


class VideoTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def load(self, videos: list[dict]) -> None:
        self.beginResetModel()
        self._rows = videos
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return COLUMNS[section]
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(SUBTEXT)
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            views = row.get("views") or 0
            likes = row.get("likes") or 0
            comments = row.get("comments") or 0
            er = ((likes + comments) / views * 100) if views else 0
            return [
                row.get("title", ""),
                _fmt_date(row.get("published_at")),
                _fmt(row.get("views")),
                _fmt(row.get("likes")),
                _fmt(row.get("comments")),
                f"{er:.2f}%",
                _fmt_duration(row.get("duration_seconds")),
            ][col]

        if role == Qt.ItemDataRole.UserRole:
            return row

        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(TEXT)

        if role == Qt.ItemDataRole.BackgroundRole:
            if index.row() % 2 == 0:
                return QColor("#1e1e2e")
            return QColor("#181825")

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (2, 3, 4, 5, 6):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def raw_row(self, proxy_row: int) -> dict:
        return self._rows[proxy_row]


# ------------------------------------------------------------------ #
# Detail panel
# ------------------------------------------------------------------ #

class VideoDetailPanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background: #181825; border-radius: 8px; }"
        )
        self.setMinimumWidth(240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        heading = QLabel("Video Details")
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        heading.setFont(font)
        heading.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(heading)

        self._fields: dict[str, QLabel] = {}
        for key in ("Title", "Published", "Views", "Likes", "Comments",
                    "Eng. Rate", "Duration", "Video ID"):
            row = QVBoxLayout()
            row.setSpacing(1)
            lbl = QLabel(key)
            lbl.setStyleSheet(f"color: {SUBTEXT}; font-size: 10px;")
            val = QLabel("—")
            val.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val)
            layout.addLayout(row)
            self._fields[key] = val

        layout.addStretch()
        self.clear()

    def clear(self) -> None:
        for lbl in self._fields.values():
            lbl.setText("—")

    def show_video(self, video: dict) -> None:
        views = video.get("views") or 0
        likes = video.get("likes") or 0
        comments = video.get("comments") or 0
        er = ((likes + comments) / views * 100) if views else 0

        self._fields["Title"].setText(video.get("title", "—"))
        self._fields["Published"].setText(_fmt_date(video.get("published_at")))
        self._fields["Views"].setText(_fmt(video.get("views")))
        self._fields["Likes"].setText(_fmt(video.get("likes")))
        self._fields["Comments"].setText(_fmt(video.get("comments")))
        self._fields["Eng. Rate"].setText(f"{er:.2f}%")
        self._fields["Duration"].setText(_fmt_duration(video.get("duration_seconds")))
        self._fields["Video ID"].setText(video.get("video_id", "—"))


# ------------------------------------------------------------------ #
# Tab
# ------------------------------------------------------------------ #

class VideosTab(QWidget):
    def __init__(self):
        super().__init__()
        self._channel_id: str | None = None
        self._all_videos: list[dict] = []
        self._model = VideoTableModel()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_lbl = QLabel("Search:")
        search_lbl.setStyleSheet(f"color: {SUBTEXT};")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by title…")
        self._search.setStyleSheet(
            f"background: #313244; color: {TEXT}; border: 1px solid {GRID};"
            " border-radius: 4px; padding: 4px 8px;"
        )
        self._search.textChanged.connect(self._on_search)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self._search, stretch=1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {SUBTEXT}; font-size: 11px;")
        search_row.addWidget(self._count_label)
        root.addLayout(search_row)

        # Splitter: table | detail panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # Table
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            f"""
            QTableView {{
                background: {BG};
                color: {TEXT};
                border: none;
                gridline-color: {GRID};
                outline: 0;
            }}
            QTableView::item:selected {{
                background: #313244;
                color: {BLUE};
            }}
            QHeaderView::section {{
                background: #181825;
                color: {SUBTEXT};
                border: none;
                padding: 4px 8px;
                font-size: 11px;
            }}
            """
        )
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        splitter.addWidget(self._table)

        # Detail panel
        self._detail = VideoDetailPanel()
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    def load_channel(self, channel_id: str) -> None:
        self._channel_id = channel_id
        self._all_videos = VideoModel.for_channel(channel_id)
        self._model.load(self._all_videos)
        self._search.clear()
        self._detail.clear()
        self._count_label.setText(f"{len(self._all_videos)} videos")

    def _on_search(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)
        visible = self._proxy.rowCount()
        total = len(self._all_videos)
        if text:
            self._count_label.setText(f"{visible} / {total} videos")
        else:
            self._count_label.setText(f"{total} videos")

    def _on_selection_changed(self) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._detail.clear()
            return
        proxy_row = indexes[0].row()
        source_row = self._proxy.mapToSource(indexes[0]).row()
        video = self._model.raw_row(source_row)
        self._detail.show_video(video)
