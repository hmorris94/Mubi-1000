import json
import csv
import re
import random
from pathlib import Path
from collections import Counter
from flask import Blueprint, render_template, jsonify, request
from .data_manager import DataManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --- Title normalization (moved from app.py, unchanged logic) ---

ALTERNATE_TITLES = {
    "dr strangelove": [
        "dr strangelove or how i learned to stop worrying and love the bomb"
    ],
}


def normalize_title(title):
    if not title:
        return ""
    normalized = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def get_all_title_variants(normalized_title):
    variants = {normalized_title}
    if normalized_title in ALTERNATE_TITLES:
        variants.update(ALTERNATE_TITLES[normalized_title])
    for primary, alternates in ALTERNATE_TITLES.items():
        if normalized_title in alternates:
            variants.add(primary)
            variants.update(alternates)
    return variants


def _load_watched_set(csv_path):
    """Load watched movies from CSV into a set of (normalized_title, year) tuples."""
    watched = set()
    if not csv_path.exists():
        return watched
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        name_col, year_col = 1, 2
        if header:
            for i, col in enumerate(header):
                col_lower = col.lower()
                if col_lower in ['name', 'title', 'movie']:
                    name_col = i
                elif col_lower == 'year':
                    year_col = i
        for row in reader:
            if row and len(row) > name_col:
                title = row[name_col].strip()
                year = row[year_col].strip() if len(row) > year_col else ""
                if title:
                    watched.add((normalize_title(title), year))
    return watched


def _mark_watched(movies, watched_set):
    """Mark movies as watched in-place based on title+year matching."""
    for movie in movies:
        normalized = normalize_title(movie.get('title', ''))
        year = movie.get('year', '').strip()
        variants = get_all_title_variants(normalized)
        movie['watched'] = any((v, year) in watched_set for v in variants)


def _load_my_services(data_dir):
    """Load user's configured streaming services from my_services.json."""
    path = Path(data_dir) / "my_services.json"
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding='utf-8')))
        except (json.JSONDecodeError, TypeError):
            pass
    return set()


# Only surface these monetization types to the UI
_INCLUDED_MONETIZATION = {"FLATRATE", "FREE"}

# Skip reseller/channel services (redundant with first-order subscriptions).
# Any technical_name starting with these prefixes is skipped UNLESS it's
# in the first-party allowlist.
_RESELLER_PREFIXES = ("amazon", "rokuchannel", "appletv")
_FIRST_PARTY = {"amazon", "amazonprime",
                "rokuchannel", "appletvplus"}

# Specific services to always exclude (e.g. ad-supported paid tiers).
_EXCLUDED_SERVICES = {"amazonprimevideowithads", "netflixbasicwithads"}


def _is_reseller(technical_name):
    return (technical_name.startswith(_RESELLER_PREFIXES)
            and technical_name not in _FIRST_PARTY)


# Collapse duplicate services that represent the same platform.
# Maps alias technical_name -> (canonical technical_name, display name).
_SERVICE_ALIASES = {
    "plexplayer": ("plex", "Plex"),
    "justwatchplexchannel": ("plex", "Plex"),
}


def _merge_streaming(movies, streaming_data):
    """Merge streaming service data into movie objects in-place.

    Filters cached data to only include FLATRATE/FREE offers,
    excludes reseller channels, and deduplicates aliased services.
    """
    for movie in movies:
        title = movie.get('title', '').strip()
        year = movie.get('year', '').strip()
        key = f"{title}|||{year}"
        entry = streaming_data.get(key, {})
        all_services = entry.get("services", [])
        filtered = []
        seen = set()
        for s in all_services:
            if s.get('monetization_type') not in _INCLUDED_MONETIZATION:
                continue
            tech = s.get('technical_name', '')
            if tech in _EXCLUDED_SERVICES or _is_reseller(tech):
                continue
            alias = _SERVICE_ALIASES.get(tech)
            canonical = alias[0] if alias else tech
            if canonical in seen:
                continue
            seen.add(canonical)
            if alias:
                s = {**s, 'technical_name': canonical, 'name': alias[1]}
            filtered.append(s)
        movie['streaming_services'] = [s['technical_name'] for s in filtered]
        movie['streaming_services_full'] = filtered


class MovieCache:
    """Caches movie data + watched/streaming status in memory. Reloads when files change on disk."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self._movies = None
        self._movies_mtime = 0
        self._watched_mtime = 0
        self._streaming_mtime = 0
        self._streaming_data = {}

    def get_movies(self):
        """Return movie list with watched and streaming status, or None if no data exists."""
        latest = self.data_dir / "latest.json"
        watched = self.data_dir / "watched.csv"
        streaming = self.data_dir / "streaming.json"

        movies_mtime = latest.stat().st_mtime if latest.exists() else 0
        watched_mtime = watched.stat().st_mtime if watched.exists() else 0
        streaming_mtime = streaming.stat().st_mtime if streaming.exists() else 0

        if movies_mtime != self._movies_mtime:
            if latest.exists():
                self._movies = json.loads(latest.read_text(encoding='utf-8'))
            else:
                self._movies = None
            self._movies_mtime = movies_mtime
            self._watched_mtime = 0  # force re-mark on next check
            self._streaming_mtime = 0  # force re-merge on next check

        if self._movies is not None and watched_mtime != self._watched_mtime:
            watched_set = _load_watched_set(watched)
            _mark_watched(self._movies, watched_set)
            self._watched_mtime = watched_mtime

        if streaming_mtime != self._streaming_mtime:
            if streaming.exists():
                raw = json.loads(streaming.read_text(encoding='utf-8'))
                self._streaming_data = raw.get("movies", {})
            else:
                self._streaming_data = {}
            self._streaming_mtime = streaming_mtime
            # Re-merge streaming data
            if self._movies is not None:
                _merge_streaming(self._movies, self._streaming_data)

        # Return a shallow copy of the list so filters don't mutate the cache
        return list(self._movies) if self._movies is not None else None


def get_decade(year_str):
    try:
        year = int(year_str)
        return f"{(year // 10) * 10}s"
    except (ValueError, TypeError):
        return None


def apply_filters(movies, args, data_dir="data"):
    """Apply query-string filters to a movie list.

    Supports: hide_watched, streaming_service, decade, country, director.
    """
    if args.get('hide_watched', 'false').lower() == 'true':
        movies = [m for m in movies if not m.get('watched')]

    streaming = args.get('streaming_service')
    if streaming:
        if streaming == '__my__':
            my_services = _load_my_services(data_dir)
            if my_services:
                movies = [m for m in movies
                          if my_services & set(m.get('streaming_services', []))]
            else:
                movies = [m for m in movies if m.get('streaming_services')]
        else:
            requested = set(s.strip().lower() for s in streaming.split(','))
            movies = [m for m in movies
                      if requested & set(m.get('streaming_services', []))]

    decade = args.get('decade')
    if decade:
        movies = [m for m in movies if get_decade(m.get('year')) == decade]

    country = args.get('country')
    if country:
        movies = [m for m in movies if m.get('country', '').lower() == country.lower()]

    director = args.get('director')
    if director:
        movies = [m for m in movies if director.lower() in m.get('director', '').lower()]

    return movies


DEFAULT_CONFIG = {
    "data_dir": str(PROJECT_ROOT / "data"),
}


def create_blueprint(name="mubi", config=None):
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    bp = Blueprint(name, __name__,
                   template_folder="templates",
                   static_folder="static")

    cache = MovieCache(cfg["data_dir"])
    data_manager = DataManager(cfg["data_dir"])

    # --- Page routes ---

    @bp.route('/')
    def index():
        return render_template('index.html')

    @bp.route('/stats')
    def stats_page():
        return render_template('stats.html')

    @bp.route('/directors')
    def directors_list_page():
        return render_template('directors.html')

    @bp.route('/director/<path:name>')
    def director_page(name):
        return render_template('director.html', director_name=name)

    @bp.route('/countries')
    def countries_list_page():
        return render_template('countries.html')

    @bp.route('/country/<path:name>')
    def country_page(name):
        return render_template('country.html', country_name=name)

    @bp.route('/changes')
    def changes_page():
        return render_template('changes.html')

    # --- API routes ---

    @bp.route('/api/movies')
    def get_movies():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found. Please run the scraper first.'}), 404
        return jsonify(apply_filters(movies, request.args, cfg["data_dir"]))

    @bp.route('/api/random')
    def get_random_movie():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found. Please run the scraper first.'}), 404
        query = request.args.get('q', '').lower()
        if query:
            movies = [m for m in movies
                      if query in m.get('title', '').lower()
                      or query in m.get('director', '').lower()
                      or query in m.get('country', '').lower()
                      or query in m.get('year', '').lower()]
        filtered = apply_filters(movies, request.args, cfg["data_dir"])
        if not filtered:
            return jsonify({'error': 'No movies match the selected filters.'}), 404
        return jsonify(random.choice(filtered))

    @bp.route('/api/search')
    def search_movies():
        query = request.args.get('q', '').lower()
        if not query:
            return jsonify({'error': 'No search query provided'}), 400
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found. Please run the scraper first.'}), 404
        movies = [m for m in movies
                  if query in m.get('title', '').lower()
                  or query in m.get('director', '').lower()
                  or query in m.get('country', '').lower()
                  or query in m.get('year', '').lower()]
        filtered = apply_filters(movies, request.args, cfg["data_dir"])
        return jsonify(filtered)

    @bp.route('/api/stats')
    def get_stats():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found. Please run the scraper first.'}), 404

        total_movies = len(movies)
        watched_count = sum(1 for m in movies if m.get('watched'))

        decades = Counter()
        watched_by_decade = Counter()
        countries = Counter()
        watched_by_country = Counter()
        directors = Counter()
        watched_by_director = Counter()
        years = []

        for m in movies:
            watched = m.get('watched')
            decade = get_decade(m.get('year'))
            if decade:
                decades[decade] += 1
                if watched:
                    watched_by_decade[decade] += 1
            country = m.get('country', '').strip()
            if country:
                countries[country] += 1
                if watched:
                    watched_by_country[country] += 1
            director = m.get('director', '').strip()
            if director:
                directors[director] += 1
                if watched:
                    watched_by_director[director] += 1
            if m.get('year') and m['year'].isdigit():
                years.append(int(m['year']))

        return jsonify({
            'total_movies': total_movies,
            'watched_count': watched_count,
            'unwatched_count': total_movies - watched_count,
            'watched_percentage': round((watched_count / total_movies) * 100, 1) if total_movies else 0,
            'decade_distribution': sorted(decades.items()),
            'country_distribution': countries.most_common(20),
            'director_distribution': directors.most_common(20),
            'avg_year': round(sum(years) / len(years)) if years else None,
            'median_year': sorted(years)[len(years) // 2] if years else None,
            'oldest_year': min(years) if years else None,
            'newest_year': max(years) if years else None,
            'watched_by_decade': sorted(watched_by_decade.items()),
            'watched_by_country': watched_by_country.most_common(20),
            'watched_by_director': watched_by_director.most_common(20),
        })

    @bp.route('/api/filter-options')
    def get_filter_options():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found.'}), 404
        decades = set()
        countries = Counter()
        directors = Counter()
        streaming_services = Counter()
        streaming_meta = {}
        for m in movies:
            decade = get_decade(m.get('year'))
            if decade:
                decades.add(decade)
            country = m.get('country', '').strip()
            if country:
                countries[country] += 1
            director = m.get('director', '').strip()
            if director:
                directors[director] += 1
            for svc in m.get('streaming_services_full', []):
                streaming_services[svc['name']] += 1
                streaming_meta[svc['name']] = {
                    'technical_name': svc['technical_name'],
                    'monetization_type': svc.get('monetization_type', 'FLATRATE'),
                }
        return jsonify({
            'decades': sorted(decades),
            'countries': [{'name': c, 'count': n} for c, n in countries.most_common()],
            'directors': [{'name': d, 'count': n} for d, n in directors.most_common()],
            'streaming_services': [
                {
                    'name': name,
                    'technical_name': streaming_meta[name]['technical_name'],
                    'monetization_type': streaming_meta[name]['monetization_type'],
                    'count': count,
                }
                for name, count in streaming_services.most_common()
            ],
        })

    @bp.route('/api/directors')
    def get_directors():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found.'}), 404
        directors = Counter()
        for m in movies:
            d = m.get('director', '').strip()
            if d:
                directors[d] += 1
        return jsonify([{'name': d, 'count': n} for d, n in directors.most_common()])

    @bp.route('/api/countries')
    def get_countries():
        movies = cache.get_movies()
        if movies is None:
            return jsonify({'error': 'No movie data found.'}), 404
        countries = Counter()
        for m in movies:
            c = m.get('country', '').strip()
            if c:
                countries[c] += 1
        return jsonify([{'name': c, 'count': n} for c, n in countries.most_common()])

    @bp.route('/api/snapshots')
    def get_snapshots():
        historical = data_manager.load_historical_data()
        timestamps = sorted(historical.keys(), reverse=True)
        return jsonify(timestamps)

    @bp.route('/api/changes')
    def get_changes():
        historical = data_manager.load_historical_data()
        if len(historical) < 2:
            return jsonify({'error': 'Not enough historical data for comparison'}), 404
        timestamps = sorted(historical.keys(), reverse=True)
        latest_ts = request.args.get('to', timestamps[0])
        prev_ts = request.args.get('from', timestamps[1])
        if latest_ts not in historical or prev_ts not in historical:
            return jsonify({'error': 'Invalid snapshot timestamp'}), 400
        changes = data_manager.compare_versions(historical[prev_ts], historical[latest_ts])
        changes['summary'] = {
            'total_added': len(changes['added']),
            'total_removed': len(changes['removed']),
            'total_moved_up': len(changes['moved_up']),
            'total_moved_down': len(changes['moved_down']),
            'total_unchanged': len(changes['unchanged']),
        }
        return jsonify({
            'latest_timestamp': latest_ts,
            'previous_timestamp': prev_ts,
            'changes': changes,
        })

    @bp.route('/api/my-services')
    def get_my_services():
        services = list(_load_my_services(cfg["data_dir"]))
        return jsonify(services)

    @bp.route('/api/my-services', methods=['POST'])
    def set_my_services():
        data = request.get_json()
        services = data.get('services', [])
        path = Path(cfg["data_dir"]) / "my_services.json"
        path.write_text(json.dumps(services, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'success': True, 'services': services})

    return bp
