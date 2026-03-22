"""Data access layer — channels, snapshots, videos."""

from datetime import datetime, timedelta
from typing import Optional

from app.db.database import Database


class ChannelModel:
    @staticmethod
    def all() -> list[dict]:
        db = Database.get()
        rows = db.execute(
            "SELECT * FROM channels ORDER BY title"
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get(channel_id: str) -> Optional[dict]:
        db = Database.get()
        row = db.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def upsert(data: dict) -> None:
        db = Database.get()
        db.execute(
            """
            INSERT INTO channels (channel_id, title, handle, description, thumbnail_url)
            VALUES (:channel_id, :title, :handle, :description, :thumbnail_url)
            ON CONFLICT(channel_id) DO UPDATE SET
                title         = excluded.title,
                handle        = excluded.handle,
                description   = excluded.description,
                thumbnail_url = excluded.thumbnail_url
            """,
            data,
        )
        db.commit()

    @staticmethod
    def delete(channel_id: str) -> None:
        db = Database.get()
        db.execute("DELETE FROM videos WHERE channel_id = ?", (channel_id,))
        db.execute(
            "DELETE FROM channel_snapshots WHERE channel_id = ?", (channel_id,)
        )
        db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        db.commit()


class SnapshotModel:
    @staticmethod
    def insert(data: dict) -> None:
        db = Database.get()
        db.execute(
            """
            INSERT INTO channel_snapshots
                (channel_id, subscribers, total_views, video_count, estimated_monthly_views)
            VALUES
                (:channel_id, :subscribers, :total_views, :video_count, :estimated_monthly_views)
            """,
            data,
        )
        db.commit()

    @staticmethod
    def latest(channel_id: str) -> Optional[dict]:
        db = Database.get()
        row = db.execute(
            """
            SELECT * FROM channel_snapshots
            WHERE channel_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (channel_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def history(channel_id: str, limit: int = 90) -> list[dict]:
        db = Database.get()
        rows = db.execute(
            """
            SELECT * FROM channel_snapshots
            WHERE channel_id = ?
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    @staticmethod
    def history_range(
        channel_id: str, start: datetime, end: datetime
    ) -> list[dict]:
        db = Database.get()
        rows = db.execute(
            """
            SELECT * FROM channel_snapshots
            WHERE channel_id = ?
              AND fetched_at BETWEEN ? AND ?
            ORDER BY fetched_at ASC
            """,
            (channel_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def is_stale(channel_id: str, hours: int = 6) -> bool:
        latest = SnapshotModel.latest(channel_id)
        if not latest:
            return True
        fetched_at = datetime.fromisoformat(latest["fetched_at"])
        return datetime.utcnow() - fetched_at > timedelta(hours=hours)


class VideoModel:
    @staticmethod
    def upsert_many(channel_id: str, videos: list[dict]) -> None:
        db = Database.get()
        for v in videos:
            db.execute(
                """
                INSERT INTO videos
                    (channel_id, video_id, title, published_at,
                     views, likes, comments, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title            = excluded.title,
                    views            = excluded.views,
                    likes            = excluded.likes,
                    comments         = excluded.comments,
                    duration_seconds = excluded.duration_seconds,
                    fetched_at       = CURRENT_TIMESTAMP
                """,
                (
                    channel_id,
                    v["video_id"],
                    v["title"],
                    v["published_at"],
                    v["views"],
                    v["likes"],
                    v["comments"],
                    v["duration_seconds"],
                ),
            )
        db.commit()

    @staticmethod
    def for_channel(channel_id: str) -> list[dict]:
        db = Database.get()
        rows = db.execute(
            "SELECT * FROM videos WHERE channel_id = ? ORDER BY views DESC",
            (channel_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def top_by_views(channel_id: str, limit: int = 10) -> list[dict]:
        db = Database.get()
        rows = db.execute(
            """
            SELECT * FROM videos WHERE channel_id = ?
            ORDER BY views DESC LIMIT ?
            """,
            (channel_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def count(channel_id: str) -> int:
        db = Database.get()
        result = db.execute(
            "SELECT COUNT(*) FROM videos WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return result[0] if result else 0
