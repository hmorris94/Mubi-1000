import json
import os
import random
from datetime import datetime

class DataManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def load_latest_data(self):
        """Load the latest scraped data"""
        try:
            with open(f"{self.data_dir}/latest.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
            
    def load_historical_data(self):
        """Load all historical data files"""
        historical_data = {}
        
        if not os.path.exists(self.data_dir):
            return historical_data
            
        for filename in os.listdir(self.data_dir):
            if filename.startswith('mubi_top_1000_') and filename.endswith('.json'):
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Extract timestamp from filename
                        timestamp = filename.replace('mubi_top_1000_', '').replace('.json', '')
                        historical_data[timestamp] = data
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
                    
        return historical_data
        
    def compare_versions(self, old_data, new_data):
        """Compare two versions of data and identify changes"""
        if not old_data or not new_data:
            return {
                'added': [],
                'removed': [],
                'moved_up': [],
                'moved_down': [],
                'unchanged': []
            }
            
        # Load thrown out movies to exclude them from comparison
        thrown_out_movies = self.load_thrown_out_movies()
        thrown_out_titles = set(thrown_out_movies)
        
        # Create lookup dictionaries
        old_movies = {movie['title']: movie for movie in old_data if movie['title'] not in thrown_out_titles}
        new_movies = {movie['title']: movie for movie in new_data if movie['title'] not in thrown_out_titles}
        
        changes = {
            'added': [],
            'removed': [],
            'moved_up': [],
            'moved_down': [],
            'unchanged': []
        }
        
        # Find added movies
        for title in new_movies:
            if title not in old_movies:
                changes['added'].append(new_movies[title])
                
        # Find removed movies
        for title in old_movies:
            if title not in new_movies:
                changes['removed'].append(old_movies[title])
                
        # Find moved movies
        for title in new_movies:
            if title in old_movies:
                old_rank = old_movies[title]['rank']
                new_rank = new_movies[title]['rank']
                
                if old_rank != new_rank:
                    if new_rank < old_rank:
                        changes['moved_up'].append({
                            'title': title,
                            'director': new_movies[title].get('director', ''),
                            'year': new_movies[title].get('year', ''),
                            'old_rank': old_rank,
                            'new_rank': new_rank,
                            'change': old_rank - new_rank
                        })
                    else:
                        changes['moved_down'].append({
                            'title': title,
                            'director': new_movies[title].get('director', ''),
                            'year': new_movies[title].get('year', ''),
                            'old_rank': old_rank,
                            'new_rank': new_rank,
                            'change': new_rank - old_rank
                        })
                else:
                    changes['unchanged'].append(new_movies[title])
                    
        return changes
        
    def load_thrown_out_movies(self):
        """Load all thrown out movies records"""
        thrown_out_movies = []
        
        if os.path.exists(self.data_dir):
            for filename in os.listdir(self.data_dir):
                if filename.startswith('thrown_out_') and filename.endswith('.json'):
                    filepath = os.path.join(self.data_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            thrown_out_movies.extend(data.get('movies', []))
                    except Exception as e:
                        print(f"Error loading {filename}: {e}")
        
        return thrown_out_movies
        
    def save_comparison_report(self, changes, timestamp=None):
        """Save a comparison report"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        report = {
            'timestamp': timestamp,
            'summary': {
                'total_added': len(changes['added']),
                'total_removed': len(changes['removed']),
                'total_moved_up': len(changes['moved_up']),
                'total_moved_down': len(changes['moved_down']),
                'total_unchanged': len(changes['unchanged'])
            },
            'changes': changes
        }
        
        report_file = f"{self.data_dir}/comparison_report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        print(f"Comparison report saved to {report_file}")
        return report_file
        
    def get_random_movie(self, data=None):
        """Get a random movie from the dataset"""
        if not data:
            data = self.load_latest_data()
            
        if not data:
            return None
            
        return random.choice(data)
        
    def search_movies(self, query, data=None):
        """Search movies by title"""
        if not data:
            data = self.load_latest_data()
            
        if not data:
            return []
            
        query = query.lower()
        results = []
        
        for movie in data:
            if (query in movie.get('title', '').lower()
                    or query in movie.get('director', '').lower()
                    or query in movie.get('country', '').lower()
                    or query in movie.get('year', '').lower()):
                results.append(movie)
                
        return results

if __name__ == "__main__":
    dm = DataManager()
    data = dm.load_latest_data()
    if data:
        print(f"Loaded {len(data)} movies")
        random_movie = dm.get_random_movie(data)
        print(f"Random movie: {random_movie['title']} (Rank #{random_movie['rank']})")
