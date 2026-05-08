# Static Astrology Data Publisher

This repository generates and publishes astrology and sky-state data as static JSON files. It has no frontend, no backend server, no database, and no JavaScript application. GitHub Actions runs the generator daily, commits changed files into `data/`, and GitHub Pages serves those files directly.

The generator is written in Python and managed with [`uv`](https://docs.astral.sh/uv/). Planetary positions are calculated locally with Swiss Ephemeris through `pyswisseph`; no external APIs are called.

## JSON Architecture

The public data entrypoint is:

```text
data/latest.json
```

Clients should fetch `latest.json` first, then follow the relative URLs inside it:

```json
{
  "today_url": "./days/YYYY-MM-DD.json",
  "tomorrow_url": "./days/YYYY-MM-DD.json",
  "current_month_url": "./months/YYYY-MM.json"
}
```

Daily files live at:

```text
data/days/YYYY-MM-DD.json
```

Each daily file contains 24 hourly UTC snapshots with planet positions, zodiac signs, retrograde flags, Moon phase, major aspects, and deterministic interpretation text.

Monthly files live at:

```text
data/months/YYYY-MM.json
```

Each monthly file is a lightweight index of days for that month, including noon Moon phase, noon Moon sign, Mercury retrograde status, and a headline.

Yearly archives live at:

```text
data/archive/YYYY.json.gz
```

Archives are gzip-compressed JSON files containing full daily JSON documents keyed by date.

## Local Setup

Install `uv` if you do not already have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Install dependencies:

```bash
uv sync
```

Generate or update the JSON files:

```bash
uv run scripts/update_sky.py
```

The script is safe to run repeatedly. It updates today, tomorrow, the current UTC month, the next UTC month, `data/latest.json`, and any yearly archives needed by the retention policy.

## GitHub Pages

To publish the JSON files:

1. Push this repository to GitHub.
2. Open the repository settings.
3. Go to **Pages**.
4. Set the source to the main branch.
5. Set the folder to the repository root.

After Pages is enabled, clients can fetch:

```text
https://OWNER.github.io/REPO/data/latest.json
```

From there, clients should follow the relative URLs for the current daily and monthly data.

## Daily Updates

The workflow at `.github/workflows/update-sky.yml` runs every day at `06:17 UTC` and can also be started manually with `workflow_dispatch`.

The workflow:

1. Checks out the repository.
2. Installs `uv`.
3. Runs `uv sync`.
4. Runs `uv run scripts/update_sky.py`.
5. Commits and pushes `data/` changes with the message `Update astrology data`.
6. Skips the commit when no data files changed.

The workflow uses `permissions: contents: write` so it can push generated JSON back to the repository.

## Retention And Archives

Loose daily files in `data/days/` are kept for the last 730 days by default. The retention period is configured near the top of `scripts/update_sky.py`:

```python
RETENTION_DAYS = 730
```

Daily files older than the retention window are merged into compressed yearly archives at `data/archive/YYYY.json.gz`. If an archive already exists, the script loads it, merges any missing old days, rewrites the archive, verifies the archived dates, and only then deletes the loose daily files.

Monthly summary files in `data/months/` are kept forever.

## Notes On Licensing

This project depends on Swiss Ephemeris through `pyswisseph`. Check the Swiss Ephemeris and `pyswisseph` licensing terms before commercial use or redistribution.
