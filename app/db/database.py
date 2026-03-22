"""SQLite connection, schema initialisation, and migration."""

import sqlite3
from app.config import DB_PATH


class Database:
    _instance: "Database | None" = None

    @classmethod
    def get(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id    TEXT UNIQUE NOT NULL,
                title         TEXT,
                handle        TEXT,
                description   TEXT,
                thumbnail_url TEXT,
                added_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS channel_snapshots (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id              TEXT NOT NULL,
                fetched_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
                subscribers             INTEGER,
                total_views             INTEGER,
                video_count             INTEGER,
                estimated_monthly_views INTEGER,
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
            );

            CREATE TABLE IF NOT EXISTS videos (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id       TEXT NOT NULL,
                video_id         TEXT UNIQUE NOT NULL,
                title            TEXT,
                published_at     DATETIME,
                views            INTEGER,
                likes            INTEGER,
                comments         INTEGER,
                duration_seconds INTEGER,
                fetched_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
            );
        """)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
        Database._instance = None
