"""QThread workers for non-blocking YouTube API fetches."""

from PyQt6.QtCore import QThread, pyqtSignal

from app.api.youtube_client import YouTubeClient, QuotaExceededError
from app.db.models import ChannelModel, SnapshotModel, VideoModel


class FetchWorker(QThread):
    """Refresh data for an existing tracked channel."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)   # emits channel_id on success
    error = pyqtSignal(str)

    def __init__(self, api_key: str, channel_id: str, force: bool = False):
        super().__init__()
        self._api_key = api_key
        self._channel_id = channel_id
        self._force = force

    def run(self) -> None:
        try:
            if not self._force and not SnapshotModel.is_stale(self._channel_id):
                self.progress.emit("Data is fresh — skipping fetch (< 6 h old)")
                self.finished.emit(self._channel_id)
                return

            client = YouTubeClient(self._api_key)

            self.progress.emit("Fetching channel info…")
            info = client.get_channel_info_full(self._channel_id)

            ChannelModel.upsert(
                {
                    "channel_id": info["channel_id"],
                    "title": info["title"],
                    "handle": info["handle"],
                    "description": info["description"],
                    "thumbnail_url": info["thumbnail_url"],
                }
            )
            SnapshotModel.insert(
                {
                    "channel_id": info["channel_id"],
                    "subscribers": info["subscribers"],
                    "total_views": info["total_views"],
                    "video_count": info["video_count"],
                    "estimated_monthly_views": None,
                }
            )

            uploads_playlist = info.get("uploads_playlist_id")
            if uploads_playlist:
                self.progress.emit("Fetching video list…")
                video_ids = client.get_video_ids_from_playlist(uploads_playlist)

                self.progress.emit(
                    f"Fetching stats for {len(video_ids)} videos…"
                )
                videos = client.get_videos_batch(video_ids)
                VideoModel.upsert_many(info["channel_id"], videos)
                self.progress.emit(f"Saved {len(videos)} videos.")

            self.finished.emit(self._channel_id)

        except QuotaExceededError as exc:
            self.error.emit(f"Quota limit reached: {exc}")
        except Exception as exc:
            self.error.emit(str(exc))


class AddChannelWorker(QThread):
    """Resolve and add a brand-new channel by ID or @handle."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)   # emits parsed channel info dict
    error = pyqtSignal(str)

    def __init__(self, api_key: str, channel_ref: str):
        super().__init__()
        self._api_key = api_key
        self._channel_ref = channel_ref.strip()

    def run(self) -> None:
        try:
            client = YouTubeClient(self._api_key)
            self.progress.emit(f"Resolving {self._channel_ref}…")

            # Heuristic: channel IDs are 24 chars starting with UC/HC
            ref = self._channel_ref
            if len(ref) == 24 and ref.startswith(("UC", "HC")):
                info = client.get_channel_info_full(ref)
            else:
                info = client.get_channel_info_by_handle(ref)

            ChannelModel.upsert(
                {
                    "channel_id": info["channel_id"],
                    "title": info["title"],
                    "handle": info["handle"],
                    "description": info["description"],
                    "thumbnail_url": info["thumbnail_url"],
                }
            )
            SnapshotModel.insert(
                {
                    "channel_id": info["channel_id"],
                    "subscribers": info["subscribers"],
                    "total_views": info["total_views"],
                    "video_count": info["video_count"],
                    "estimated_monthly_views": None,
                }
            )

            uploads_playlist = info.get("uploads_playlist_id")
            if uploads_playlist:
                self.progress.emit("Fetching video list…")
                video_ids = client.get_video_ids_from_playlist(uploads_playlist)
                self.progress.emit(
                    f"Fetching stats for {len(video_ids)} videos…"
                )
                videos = client.get_videos_batch(video_ids)
                VideoModel.upsert_many(info["channel_id"], videos)
                self.progress.emit(f"Saved {len(videos)} videos.")

            self.finished.emit(info)

        except QuotaExceededError as exc:
            self.error.emit(f"Quota limit reached: {exc}")
        except Exception as exc:
            self.error.emit(str(exc))
