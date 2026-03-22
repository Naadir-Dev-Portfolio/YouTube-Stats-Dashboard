<div align="center">

<img src="./repo-card.png" alt="YouTube Stats Dashboard project card" width="72%" />
<br /><br />

<p><strong>Multi-channel YouTube analytics desktop app with local snapshots, sortable video insights, growth charts, and quota-aware fetching.</strong></p>

<p>Built for creators and analysts who want a proper local YouTube performance dashboard.</p>

<p>
  <a href="#overview">Overview</a> |
  <a href="#feature-highlights">Feature Highlights</a> |
  <a href="#screenshots">Screenshots</a> |
  <a href="#quick-start">Quick Start</a> |
  <a href="#architecture--data">Architecture & Data</a>
</p>

<h3><strong>Made by Naadir | December 2024</strong></h3>

</div>

---

## Overview

YouTube Analytics is powerful, but it is browser-bound, time-limited, and not built for long-term local tracking across multiple channels. This project gives you a proper desktop dashboard that connects directly to the YouTube Data API v3, stores historical snapshots in SQLite, and makes channel performance easier to inspect over time.

Use it to track subscriber growth, total views, publishing activity, top-performing videos, and engagement trends without relying on a third-party web dashboard.

## What Problem It Solves

- See whether a channel is growing, plateauing, or losing momentum over time.
- Spot whether a topic or content direction is gaining relevance or fading in interest.
- Compare performance across channels and videos instead of relying on one-off snapshots.
- Turn raw YouTube metrics into a clearer view of audience traction, engagement, and trend direction.

### At a glance

| Track | Analyze | Compare |
|---|---|---|
| Channel and topic momentum over time | Audience traction, engagement, and publishing trends | Historical performance across channels, videos, and snapshots |

## Feature Highlights

- Track multiple YouTube channels from one desktop app.
- Save persistent local snapshots for historical comparison.
- Explore a sortable, filterable video table with per-video metrics.
- Visualize growth and engagement with charts and hover tooltips.
- Keep the UI responsive with `QThread` worker-based fetching.
- Monitor API usage with a built-in daily quota guard.

### Core capabilities

| Area | What it gives you |
|---|---|
| **Dashboard** | Channel sidebar, stat cards, date presets, growth charts, engagement breakdown, and top-video visibility |
| **Videos tab** | Sortable and filterable table for title, publish date, views, likes, comments, engagement rate, and duration |
| **Settings tab** | API key management, quota display, and local data directory information |
| **Data layer** | SQLite-backed storage for channels, snapshots, and videos |
| **Fetching model** | Non-blocking worker threads with live status updates |

## Screenshots

<details>
<summary><strong>Open screenshot gallery</strong></summary>

<br />

<div align="center">
  <img src="./screenshots/screenshot.png" alt="Dashboard view" width="88%" />
  <br /><br />
  <img src="./screenshots/screenshot2.png" alt="Videos view" width="88%" />
</div>

</details>

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

On first launch, enter a valid YouTube Data API v3 key. You can create one in the [Google Cloud Console](https://console.cloud.google.com/) under **APIs & Services > Credentials**, then enable **YouTube Data API v3** for the same project.

The key is stored in `api_config.json` and can be updated later from the Settings tab.

## Tech Stack

<details>
<summary><strong>Open tech stack</strong></summary>

<br />

| Category | Tools |
|---|---|
| **Language** | Python |
| **Desktop UI** | PyQt6 |
| **Charts** | matplotlib |
| **Persistence** | SQLite |
| **External API** | YouTube Data API v3 |

</details>

## Architecture & Data

<details>
<summary><strong>Open architecture and data details</strong></summary>

<br />

### Database schema

| Table | Key columns |
|---|---|
| `channels` | `channel_id`, `title`, `handle`, `thumbnail_url` |
| `channel_snapshots` | `channel_id`, `fetched_at`, `subscribers`, `total_views`, `video_count` |
| `videos` | `channel_id`, `video_id`, `title`, `published_at`, `views`, `likes`, `comments`, `duration_seconds` |

### API quota model

The YouTube Data API provides a `10,000` unit daily quota. This app tracks usage in `data/quota.json`, warns when usage passes `8,000` units, and blocks further fetches before the budget is accidentally burned. The counter resets automatically each day.

### Project structure

```text
YouTube-Stats-Dashboard/
|-- main.py
|-- requirements.txt
|-- README.md
|-- app/
|   |-- config.py
|   |-- main_window.py
|   |-- api/
|   |   |-- youtube_client.py
|   |   `-- quota_tracker.py
|   |-- db/
|   |   |-- database.py
|   |   `-- models.py
|   |-- workers/
|   |   `-- fetch_worker.py
|   `-- ui/
|       |-- chart_utils.py
|       |-- dashboard_tab.py
|       |-- videos_tab.py
|       `-- settings_tab.py
`-- data/
    |-- youtube_stats.db
    `-- quota.json
```

</details>

## Contact

Questions, feedback, or collaboration: `naadir.dev.mail@gmail.com`

