# YouTube-Stats-Dashboard

> Local channel intelligence tool that fetches full view-count history from the YouTube Data API and gives creators a persistent, exportable performance record.

![YouTube-Stats-Dashboard](repo-card.png)

Built by [Naadir](https://github.com/Naadir-Dev-Portfolio)

---

## Overview

YouTube Analytics locks your channel data behind its platform — no bulk export, no historical snapshots you can query yourself, no way to compare performance across any window you define. This tool connects directly to the YouTube Data API, resolves any channel URL format to a canonical ID, fetches the full upload history with batched requests and automatic pagination, and renders the data locally as an interactive chart with moving average overlay. The result is a persistent, exportable record of channel performance — complete with formatted Excel output — that YouTube's own interface deliberately won't give you.

---

## Features

- Resolves any YouTube channel URL format (@handle, /c/, /channel/, /user/) to a canonical channel ID without manual lookup
- Fetches up to the full upload history with batched API calls (50 videos per request) and automatic pagination handling
- Renders an interactive view-count chart with a dynamic moving average overlay, zoom, and pan
- Exports per-video stats (title, upload date, views) to a formatted .xlsx file with an embedded chart
- Runs API calls in a background thread with real-time progress logging, keeping the UI responsive during long fetches
- Retries failed requests automatically with SSL error handling (up to 3 attempts per call)

---

## Tech Stack

`Python` · `PyQt6` · `YouTube Data API v3` · `pandas` · `openpyxl`

---

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Add your YouTube Data API v3 key to `api.txt`:

```
api.txt = your YouTube Data API v3 key from Google Cloud Console
```

---

> API key placeholder in `api.txt` — replace with your own key from Google Cloud Console before running.

<sub>Python</sub>
