# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The Mubi 1000 is a Python tool for scraping, tracking, and visualizing the Mubi 1000 movies list. It provides both a CLI and Flask web interface for browsing movies, tracking watched status, streaming availability, and monitoring ranking changes over time.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt
npm install

# Build Tailwind CSS (required after modifying templates or app.js)
npm run build

# Watch for changes during frontend development
npm run watch

# Scrape the Mubi 1000 list (also runs streaming lookup automatically)
python main.py scrape
python main.py scrape --limit 50          # Test with fewer movies
python main.py scrape --output myfile     # Custom output filename base

# Start web interface at http://localhost:8082
python main.py web
python main.py web --host 127.0.0.1 --port 8080

# Look up streaming availability separately
python main.py streaming
python main.py streaming --country GB --force --delay 0.5
python main.py streaming --skip-days 3   # Refresh entries older than 3 days

# Compare latest data with previous version
python main.py compare

# CLI utilities
python main.py random
python main.py search "godfather"
```

## Architecture

### Core Modules

All source code lives in the `app/` package. `main.py` is the sole root-level Python file.

- **main.py** - CLI entry point using argparse with subcommands: `scrape`, `compare`, `random`, `search`, `streaming`, `web`
- **app/__init__.py** - Flask app creation, `ProxyFix` middleware, and Blueprint registration
- **app/blueprint.py** - Flask Blueprint with all route logic, `MovieCache`, `apply_filters()`, and `create_blueprint()` factory
- **app/scraper.py** - `MubiScraper` class using Selenium + BeautifulSoup for headless Chrome scraping with infinite scroll handling
- **app/data_manager.py** - `DataManager` class for JSON/CSV persistence, version comparison, and search functionality
- **app/streaming.py** - `StreamingLookup` class for querying JustWatch streaming availability via `simplejustwatchapi` and caching results

### Data Flow

1. **Scraping**: `MubiScraper` → scrolls page → extracts from DOM → saves timestamped JSON + `latest.json` → automatically runs streaming lookup
2. **Streaming**: `StreamingLookup` → queries JustWatch API via `simplejustwatchapi` → caches ALL offers unfiltered to `streaming.json`
3. **Comparison**: `DataManager.compare_versions()` diffs two snapshots (excludes movies in `thrown_out_*.json` files)
4. **Web API**: Flask loads `latest.json`, merges with `watched.csv` and `streaming.json` (filtering at render time), returns JSON to frontend

### Streaming Data Pipeline

- `streaming.py` caches ALL JustWatch offers unfiltered (all monetization types, all channels)
- `blueprint.py` `_merge_streaming()` filters at render time: only FLATRATE/FREE, excludes reseller channels and ad-supported tiers
- Reseller detection: prefix-based matching (`_RESELLER_PREFIXES = ("amazon", "rokuchannel", "appletv")`) with first-party allowlist (`_FIRST_PARTY`)
- Explicit exclusions: `_EXCLUDED_SERVICES` (e.g. ad-supported tiers like Netflix with Ads, Amazon Prime Video with Ads)
- Service deduplication: `_SERVICE_ALIASES` collapses duplicates (e.g. `plexplayer` and `justwatchplexchannel` → Plex)
- User's subscriptions stored in `data/my_services.json`, managed via `GET/POST /api/my-services`

### Movie Object Structure

```python
{
    'rank': int,
    'title': str,
    'director': str,
    'country': str,
    'year': str,
    'url': str,              # e.g., '/films/1234567'
    'watchable': bool,       # True if currently streamable on Mubi itself
    'scraped_at': str,       # ISO timestamp
    'watched': bool,         # Added by blueprint from watched.csv
    'streaming_services': [str],  # Added by blueprint (technical names)
    'streaming_services_full': [  # Added by blueprint
        {'name': str, 'technical_name': str, 'monetization_type': str}
    ]
}
```

### API Endpoints

- `GET /api/movies` - All movies with optional filters:
  - `?hide_watched=true` - Exclude watched movies
  - `?streaming_service=netflix` - Filter by streaming service (or `__my__` for user's services)
  - `?decade=1990s` - Filter by decade
  - `?country=France` - Filter by country
  - `?director=Kurosawa` - Filter by director (partial match)
  - `?q=query` - Search by title, director, country, or year
- `GET /api/random` - Random movie (supports same filters as `/api/movies`)
- `GET /api/search?q=query` - Search by title, director, country, or year (supports same filters)
- `GET /api/stats` - Statistics (decade/country/director distribution, watched breakdowns, year stats)
- `GET /api/filter-options` - Available filter values (decades, countries, directors, streaming services with monetization types)
- `GET /api/directors` - All directors with movie counts
- `GET /api/countries` - All countries with movie counts
- `GET /api/snapshots` - All historical snapshot timestamps (newest first)
- `GET /api/changes` - Ranking changes between versions
  - `?from=TIMESTAMP&to=TIMESTAMP` - Compare specific snapshots (defaults to two most recent)
- `GET /api/my-services` - User's selected streaming services
- `POST /api/my-services` - Save user's streaming service selections

### Pages

- `/` - Main movie list with filters and "Surprise Me"
- `/stats` - Statistics dashboard with progress tracking
- `/directors` - Browse all directors
- `/director/<name>` - Movies by specific director
- `/countries` - Browse all countries
- `/country/<name>` - Movies from specific country
- `/changes` - Weekly ranking changes view (dates shown as Monday MM/DD/YY)

### Data Files

All data stored in `data/` directory (gitignored):
- `latest.json` / `latest.csv` - Current movie list
- `mubi_top_1000_YYYYMMDD_HHMMSS.json` / `.csv` - Historical snapshots
- `watched.csv` - Letterboxd export file (columns: `Date`, `Name`, `Year`, `Letterboxd URI`)
- `streaming.json` - JustWatch streaming availability cache (unfiltered, all offers)
- `my_services.json` - User's streaming service subscriptions (JSON array of technical names)
- `thrown_out_*.json` - Lists of removed movies to exclude from comparison reporting
- `comparison_report_*.json` - Generated diff reports

### Frontend

Uses Jinja2 template inheritance, Tailwind CSS v4, and vanilla JS with Fetch API.

Tailwind is compiled via the `@tailwindcss/cli` package. Source: `app/static/input.css` → output: `app/static/output.css` (gitignored, must be built locally). Run `npm run build` after any changes to templates or `app.js`, or `npm run watch` during development.

**Templates** (`app/templates/`):
- `base.html` - Base template with shared boilerplate, nav bar, CSS/JS includes
- `index.html` - Main movie grid with filters, search, Surprise Me, collapsible My Services panel
- `stats.html` - Statistics dashboard with progress, year stats, and watched breakdowns
- `directors.html` / `director.html` - Directors list and detail pages
- `countries.html` / `country.html` - Countries list and detail pages
- `changes.html` - Ranking changes with snapshot comparison picker and "hide trivial moves" toggle

All child templates use `{% extends "base.html" %}` and `{% set active_nav = "..." %}` for nav active state.

**Static files** (`app/static/`):
- `input.css` - Tailwind CSS entry point (`@import "tailwindcss"`)
- `output.css` - Compiled Tailwind output (gitignored; build with `npm run build`)
- `styles.css` - Custom CSS on top of Tailwind (card hovers, transitions, watched styling, active filter highlights, loading states)
- `app.js` - Shared JS: `BASE` URL (from `body[data-api-base]`), `apiFetch()`, `createMovieCardHTML()`, `displayRandomMovie()`

### Deployment

VPS deployment is handled at the gateway level. This project provides `main.py web` and a Flask blueprint only.

The app uses `ProxyFix` middleware in `app/__init__.py` for correct URL generation behind any reverse proxy.

## Key Implementation Details

- Scraper scrolls to bottom repeatedly (5 consecutive no-change attempts) and clicks "Load More" buttons
- Movie extraction relies on `data-testid="director-and-year"` attribute for director/country/year; `img[alt]` for title; `data-testid="play-button"` for `watchable`
- Watched CSV column detection is flexible: accepts `name`/`title`/`movie` and `year` headers (case-insensitive)
- Watched status matching uses normalized (lowercase alphanumeric) title + year; `ALTERNATE_TITLES` in `blueprint.py` handles known title variants (e.g. Dr. Strangelove's full title)
- `data_manager.load_historical_data()` only loads `mubi_top_1000_*.json` files; `load_thrown_out_movies()` loads `thrown_out_*.json`
- `compare_versions()` excludes titles found in thrown_out files from the diff output
- `MovieCache` invalidates by mtime: independently tracks `latest.json`, `watched.csv`, and `streaming.json`; reloads only on change
- Streaming cache stores everything; all filtering (monetization types, reseller channels, aliases) happens at render time in `_merge_streaming()`
- JustWatch matching scores results by title similarity (1.0 exact, 0.5 partial) and year proximity (1.0 exact, 0.7 ±1yr, 0.3 ±2-3yr); requires score ≥ 1.0 or a single result ≥ 0.5
- Search, filters, and Surprise Me work cooperatively via a unified `loadMovies()` function; `buildFilterParams()` includes the search query
- Active filters get a yellow border highlight via the `.filter-active` CSS class
- Director/country templates use `{{ name | tojson }}` for safe JS string interpolation (prevents XSS)
