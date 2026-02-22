"""JustWatch streaming availability lookup for Mubi 1000 movies."""

import json
import time
from datetime import datetime
from pathlib import Path

from simplejustwatchapi.justwatch import search as jw_search


# Delay between API calls (seconds)
REQUEST_DELAY = 0.75


class StreamingLookup:
    """Queries JustWatch for streaming availability of movies."""

    def __init__(self, data_dir="data", country="US", language="en"):
        self.data_dir = Path(data_dir)
        self.country = country
        self.language = language
        self.streaming_file = self.data_dir / "streaming.json"
        self._existing_data = self._load_existing()

    def _load_existing(self):
        """Load existing streaming.json if present."""
        if self.streaming_file.exists():
            return json.loads(self.streaming_file.read_text(encoding="utf-8"))
        return {"metadata": {}, "movies": {}}

    def _movie_key(self, movie):
        """Create stable lookup key from movie dict."""
        title = movie.get("title", "").strip()
        year = movie.get("year", "").strip()
        return f"{title}|||{year}"

    def _find_best_match(self, results, title, year):
        """Find the best matching MediaEntry from JustWatch results.

        Scores by title similarity and year proximity. Off-by-one year
        is common for international releases.
        """
        if not results:
            return None

        title_norm = title.lower().strip()
        year_int = None
        try:
            year_int = int(year)
        except (ValueError, TypeError):
            pass

        scored = []
        for i, entry in enumerate(results):
            if entry.object_type and entry.object_type != "MOVIE":
                continue
            t_score = 1.0 if entry.title.lower().strip() == title_norm else 0.5
            y_score = 0.0
            if year_int and entry.release_year:
                diff = abs(entry.release_year - year_int)
                if diff == 0:
                    y_score = 1.0
                elif diff == 1:
                    y_score = 0.7
                elif diff <= 3:
                    y_score = 0.3
            scored.append((t_score + y_score, i, entry))

        if not scored:
            return None

        scored.sort(key=lambda x: (-x[0], x[1]))

        if scored[0][0] >= 1.0:
            return scored[0][2]
        if len(scored) == 1 and scored[0][0] >= 0.5:
            return scored[0][2]
        return None

    def _query_movie(self, title, year):
        """Query JustWatch for a single movie.

        Returns dict with services list, justwatch_id, and last_updated.
        """
        try:
            results = jw_search(
                title,
                country=self.country,
                language=self.language,
                count=5,
                best_only=True,
            )
        except Exception as e:
            print(f"  Error querying JustWatch for '{title}': {e}")
            return {
                "services": [],
                "justwatch_id": None,
                "last_updated": datetime.now().isoformat(),
            }

        best = self._find_best_match(results, title, year)

        if best is None:
            return {
                "services": [],
                "justwatch_id": None,
                "last_updated": datetime.now().isoformat(),
            }

        # Extract all offers, deduplicate by (technical_name, monetization_type)
        services = []
        seen = set()
        for offer in (best.offers or []):
            tech = offer.package.technical_name
            key = (tech, offer.monetization_type)
            if key not in seen:
                seen.add(key)
                services.append({
                    "name": offer.package.name,
                    "technical_name": tech,
                    "monetization_type": offer.monetization_type,
                })

        return {
            "services": services,
            "justwatch_id": best.entry_id if best.entry_id else None,
            "last_updated": datetime.now().isoformat(),
        }

    def lookup_all(self, movies, force_refresh=False, skip_recent_days=7,
                   delay=REQUEST_DELAY):
        """Query JustWatch for all movies.

        Skips recently-queried entries unless force_refresh is True.
        Saves progress every 50 movies for crash resilience.
        """
        existing_movies = self._existing_data.get("movies", {})
        now = datetime.now()
        total = len(movies)
        queried = 0
        skipped = 0
        matched = 0

        print(f"Looking up streaming availability for {total} movies...")
        print(f"Country: {self.country} | Rate limit: {delay}s between requests")
        if not force_refresh:
            print(f"Skipping movies queried within {skip_recent_days} days")
        print()

        for i, movie in enumerate(movies, 1):
            key = self._movie_key(movie)
            title = movie.get("title", "")
            year = movie.get("year", "")

            # Skip recently-queried movies
            if not force_refresh and key in existing_movies:
                last_updated = existing_movies[key].get("last_updated")
                if last_updated:
                    try:
                        last_dt = datetime.fromisoformat(last_updated)
                        if (now - last_dt).days < skip_recent_days:
                            skipped += 1
                            if existing_movies[key].get("services"):
                                matched += 1
                            continue
                    except (ValueError, TypeError):
                        pass

            result = self._query_movie(title, year)
            existing_movies[key] = result
            queried += 1

            if result["services"]:
                matched += 1
                svc_names = ", ".join(s["name"] for s in result["services"])
                print(f"  [{i}/{total}] {title} ({year}) -> {svc_names}")
            else:
                print(f"  [{i}/{total}] {title} ({year}) -> No streaming found")

            # Save periodically for crash resilience
            if queried % 50 == 0:
                self._save(existing_movies, total, matched)

            time.sleep(delay)

        self._save(existing_movies, total, matched)
        print(f"\nDone! Queried: {queried}, Skipped: {skipped}, "
              f"With streaming: {matched}/{total}")

    def _save(self, movies_data, total, matched):
        """Save streaming data to disk."""
        self._existing_data = {
            "metadata": {
                "country": self.country,
                "last_full_run": datetime.now().isoformat(),
                "total_queried": total,
                "total_matched": matched,
            },
            "movies": movies_data,
        }
        self.streaming_file.write_text(
            json.dumps(self._existing_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
