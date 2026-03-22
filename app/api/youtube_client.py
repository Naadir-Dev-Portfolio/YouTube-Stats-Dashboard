"""YouTube Data API v3 wrapper — quota-aware, no external ISO parser."""

import re
from googleapiclient.discovery import build
from app.api.quota_tracker import QuotaTracker
from app.config import QUOTA_WARNING_THRESHOLD


class QuotaExceededError(Exception):
    pass


def _parse_duration(duration: str) -> int:
    """Convert ISO 8601 duration string (e.g. PT4M33S) to total seconds."""
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


class YouTubeClient:
    def __init__(self, api_key: str):
        self._yt = build("youtube", "v3", developerKey=api_key)
        self.quota = QuotaTracker()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _check_quota(self, needed: int = 1) -> None:
        if self.quota.used() + needed > QUOTA_WARNING_THRESHOLD:
            raise QuotaExceededError(
                f"Daily quota near limit — {self.quota.used()} units used. "
                "Fetch blocked to protect remaining budget."
            )

    def _parse_channel_item(self, item: dict) -> dict:
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        thumb_url = (
            thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url", "")
        )
        return {
            "channel_id": item["id"],
            "title": snippet.get("title", ""),
            "handle": snippet.get("customUrl", ""),
            "description": snippet.get("description", ""),
            "thumbnail_url": thumb_url,
            "subscribers": int(stats.get("subscriberCount", 0)),
            "total_views": int(stats.get("viewCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "uploads_playlist_id": content.get("relatedPlaylists", {}).get("uploads"),
        }

    def _parse_video_item(self, item: dict) -> dict:
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        return {
            "video_id": item["id"],
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration_seconds": _parse_duration(content.get("duration", "")),
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_channel_info_full(self, channel_id: str) -> dict:
        """Fetch channel by ID including uploads playlist ID."""
        self._check_quota(1)
        response = self._yt.channels().list(
            part="snippet,statistics,contentDetails",
            id=channel_id,
        ).execute()
        self.quota.add(1)
        items = response.get("items", [])
        if not items:
            raise ValueError(f"Channel not found: {channel_id}")
        return self._parse_channel_item(items[0])

    def get_channel_info_by_handle(self, handle: str) -> dict:
        """Resolve a @handle or bare handle to full channel info."""
        self._check_quota(1)
        handle_clean = handle.lstrip("@")
        response = self._yt.channels().list(
            part="snippet,statistics,contentDetails",
            forHandle=handle_clean,
        ).execute()
        self.quota.add(1)
        items = response.get("items", [])
        if not items:
            raise ValueError(f"Channel not found for handle: @{handle_clean}")
        return self._parse_channel_item(items[0])

    def get_video_ids_from_playlist(
        self, playlist_id: str, max_videos: int = 500
    ) -> list[str]:
        """Page through an uploads playlist and collect video IDs."""
        video_ids: list[str] = []
        next_page_token: str | None = None

        while len(video_ids) < max_videos:
            self._check_quota(1)
            kwargs: dict = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if next_page_token:
                kwargs["pageToken"] = next_page_token

            response = self._yt.playlistItems().list(**kwargs).execute()
            self.quota.add(1)

            for item in response.get("items", []):
                vid_id = item["snippet"]["resourceId"].get("videoId")
                if vid_id:
                    video_ids.append(vid_id)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return video_ids

    def get_videos_batch(self, video_ids: list[str]) -> list[dict]:
        """Fetch video metadata + stats in batches of 50 (1 unit/batch)."""
        results: list[dict] = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            self._check_quota(1)
            response = self._yt.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            ).execute()
            self.quota.add(1)
            for item in response.get("items", []):
                results.append(self._parse_video_item(item))
        return results
