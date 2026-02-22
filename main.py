#!/usr/bin/env python3
"""
The Mubi 1000 - Main Entry Point

This script provides a command-line interface for scraping and managing
the Mubi 1000 movies list.
"""

import argparse
from pathlib import Path

from app.scraper import MubiScraper
from app.data_manager import DataManager

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = str(PROJECT_ROOT / "data")

def main():
    parser = argparse.ArgumentParser(description='The Mubi 1000')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape Mubi 1000 movies')
    scrape_parser.add_argument('--output', help='Output filename (without extension)')
    scrape_parser.add_argument('--limit', type=int, help='Limit number of movies to scrape (for testing)')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare latest data with previous version')
    
    # Random command
    random_parser = subparsers.add_parser('random', help='Get a random movie')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for movies')
    search_parser.add_argument('query', help='Search query')
    
    # Web command
    web_parser = subparsers.add_parser('web', help='Start the web interface')
    web_parser.add_argument('--host', default='0.0.0.0', help='Bind address')
    web_parser.add_argument('--port', type=int, default=8082, help='Port')

    # Streaming command
    streaming_parser = subparsers.add_parser('streaming', help='Look up streaming availability via JustWatch')
    streaming_parser.add_argument('--country', default='US', help='Country code (default: US)')
    streaming_parser.add_argument('--force', action='store_true', help='Re-query all movies, ignoring cache')
    streaming_parser.add_argument('--skip-days', type=int, default=7, help='Skip movies queried within N days (default: 7)')
    streaming_parser.add_argument('--delay', type=float, default=0.75, help='Delay between API calls in seconds (default: 0.75)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize components
    data_manager = DataManager(DATA_DIR)
    
    if args.command == 'scrape':
        scraper = MubiScraper(limit=args.limit)
        movies = scraper.scrape()
        
        if movies:
            scraper.save_data(args.output)
            print(f"Successfully scraped {len(movies)} movies\n")

            from app.streaming import StreamingLookup
            lookup = StreamingLookup(data_dir=data_manager.data_dir)
            lookup.lookup_all(movies)
        else:
            print("No movies were scraped. Please check the scraper configuration.")
            
    elif args.command == 'compare':
        print("Comparing latest data with previous version...")
        historical_data = data_manager.load_historical_data()
        
        if len(historical_data) < 2:
            print("Not enough historical data for comparison. Need at least 2 versions.")
            return
            
        timestamps = sorted(historical_data.keys(), reverse=True)
        latest_timestamp = timestamps[0]
        previous_timestamp = timestamps[1]
        
        latest_data = historical_data[latest_timestamp]
        previous_data = historical_data[previous_timestamp]
        
        changes = data_manager.compare_versions(previous_data, latest_data)
        data_manager.save_comparison_report(changes)
        
        print(f"Comparison between {previous_timestamp} and {latest_timestamp}:")
        print(f"  Added: {len(changes['added'])}")
        print(f"  Removed: {len(changes['removed'])}")
        print(f"  Moved up: {len(changes['moved_up'])}")
        print(f"  Moved down: {len(changes['moved_down'])}")
        print(f"  Unchanged: {len(changes['unchanged'])}")
        
    elif args.command == 'random':
        movies = data_manager.load_latest_data()

        if not movies:
            print("No movie data found. Please run 'python main.py scrape' first.")
            return

        movie = data_manager.get_random_movie(movies)
        print(f"Random movie: #{movie['rank']} {movie['title']}")
            
    elif args.command == 'search':
        movies = data_manager.search_movies(args.query)

        if not movies:
            print("No movies found.")
            return

        print(f"Found {len(movies)} movies matching '{args.query}':")
        for movie in movies[:10]:  # Show first 10 results
            print(f"  #{movie['rank']} {movie['title']}")

        if len(movies) > 10:
            print(f"  ... and {len(movies) - 10} more")
            
    elif args.command == 'streaming':
        from app.streaming import StreamingLookup

        movies = data_manager.load_latest_data()
        if not movies:
            print("No movie data found. Please run 'python main.py scrape' first.")
            return

        lookup = StreamingLookup(
            data_dir=data_manager.data_dir,
            country=args.country,
        )
        lookup.lookup_all(
            movies,
            force_refresh=args.force,
            skip_recent_days=args.skip_days,
            delay=args.delay,
        )

    elif args.command == 'web':
        print(f"Starting web interface on http://{args.host}:{args.port}")

        # Import here to avoid circular imports
        from app import app

        app.run(debug=True, host=args.host, port=args.port, reloader_type='stat')

if __name__ == "__main__":
    main()
