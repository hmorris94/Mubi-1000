# The Mubi 1000

A Python tool for scraping, visualizing, and sifting through the Mubi Top 1000 movies list with streaming availability, criteria filtering, and watched movies management.

## Features

- **Web Scraping**: Automatically scrape the Mubi 1000 movies list using Selenium and BeautifulSoup
- **Streaming Availability**: Look up which services stream each movie via JustWatch (Netflix, Criterion Channel, Mubi, etc.)
- **Change Tracking**: Track weekly ranking changes (new entries, removed movies, position changes)
- **Watched Movies**: Import your Letterboxd export to track which movies you've seen
- **Statistics Dashboard**: View your progress, decade distribution, top directors/countries with watched breakdowns
- **Advanced Filters**: Filter by decade, country, director, streaming service, or unwatched status
- **Search**: Find movies by title, director, country, or year
- **Browse by Director/Country**: Explore the list organized by filmmaker or country of origin
- **Surprise Me**: Get a random movie suggestion respecting your current filters

## Installation

1. Clone this repository:
```bash
git clone https://github.com/hmorris94/Mubi-1000.git
cd Mubi-1000
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install ChromeDriver (required for scraping):
   - Download from https://chromedriver.chromium.org/
   - Ensure it matches your Chrome version
   - Add to your PATH or place in the project directory

## Usage

### Command Line Interface

```bash
# Scrape the latest Mubi 1000 data (also updates streaming availability)
python main.py scrape
python main.py scrape --limit 50          # Test with fewer movies
python main.py scrape --output myfile     # Custom output filename base

# Start the web interface (http://localhost:8082)
python main.py web
python main.py web --host 127.0.0.1 --port 8080

# Compare latest data with previous version
python main.py compare

# Look up streaming availability separately
python main.py streaming
python main.py streaming --country GB --force --delay 0.5
python main.py streaming --skip-days 3   # Refresh entries older than 3 days

# Get a random movie suggestion
python main.py random

# Search for movies
python main.py search "godfather"
```

### Web Interface

Start the web server with `python main.py web`, then open http://localhost:8082.

**Pages:**
- **Movie List** (`/`) - Browse all movies with filters, search, and Surprise Me
- **Statistics** (`/stats`) - View your progress and collection insights
- **Directors** (`/directors`) - Browse by director
- **Countries** (`/countries`) - Browse by country
- **Changes** (`/changes`) - Compare weekly ranking changes between snapshots

### Streaming Services

The app integrates with JustWatch to show streaming availability. Running `python main.py scrape` automatically fetches this data. You can also run it separately:

```bash
python main.py streaming                    # Default: US, skip entries < 7 days old
python main.py streaming --country GB       # Different country
python main.py streaming --force            # Re-query all movies
python main.py streaming --skip-days 3      # Refresh entries older than 3 days
python main.py streaming --delay 0.5        # Override inter-request delay
```

Configure "My Streaming Services" in the web UI to filter movies by the services you subscribe to.

## Tracking Watched Movies

The app uses your Letterboxd export to track watched movies:

1. Go to https://letterboxd.com/settings/data/ and click "Export Your Data"
2. Extract the ZIP and copy `watched.csv` to the `data/` folder

The app matches movies by title and year (case-insensitive, punctuation-ignored).

## Project Structure

```
Mubi-1000/
├── main.py                      # CLI entry point
├── app/                         # Flask application package
│   ├── __init__.py              # App creation + blueprint registration
│   ├── blueprint.py             # Flask Blueprint with all routes
│   ├── scraper.py               # Selenium/BeautifulSoup scraping
│   ├── data_manager.py          # Data persistence and comparison
│   ├── streaming.py             # JustWatch streaming lookup + caching
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html            # Base template (nav, boilerplate)
│   │   ├── index.html           # Main movie list
│   │   ├── stats.html           # Statistics dashboard
│   │   ├── directors.html       # Directors list
│   │   ├── director.html        # Single director page
│   │   ├── countries.html       # Countries list
│   │   ├── country.html         # Single country page
│   │   └── changes.html         # Ranking changes
│   └── static/                  # Frontend assets
│       ├── styles.css           # Consolidated CSS
│       └── app.js               # Shared JavaScript utilities
├── data/                        # Data storage (gitignored)
│   ├── latest.json              # Current scraped data
│   ├── watched.csv              # Your Letterboxd export
│   ├── streaming.json           # JustWatch streaming cache
│   ├── my_services.json         # Your streaming subscriptions
│   └── mubi_top_1000_*.json     # Historical snapshots
├── requirements.txt             # Python dependencies
├── .gitignore
├── README.md
└── CLAUDE.md
```

## Troubleshooting

- **ChromeDriver not found**: Ensure ChromeDriver is installed and in your PATH
- **Scraping fails**: The Mubi website structure may have changed - check selectors in `app/scraper.py`
- **No data found**: Run `python main.py scrape` first to populate the database
- **Streaming data missing**: Runs automatically with `scrape`, or run `python main.py streaming` separately

## License

This project is for educational and personal use only. Please respect the terms of service of Mubi, Letterboxd, and JustWatch.
