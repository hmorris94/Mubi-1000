import json
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import csv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

class MubiScraper:
    def __init__(self, limit=None):
        self.base_url = "https://mubi.com/en/lists/the-top-1000"
        self.movies = []
        self.driver = None
        self.limit = limit  # Optional limit for testing
        
    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def wait_for_content(self):
        """Wait for movie list to load"""
        print("Waiting for movie list to load...")
        
        # Wait for the main movie list UL to appear with at least 20 items
        try:
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script("""
                    var uls = document.querySelectorAll('ul');
                    for (var i = 0; i < uls.length; i++) {
                        if (uls[i].querySelectorAll('li').length >= 20) {
                            return uls[i].querySelectorAll('li').length;
                        }
                    }
                    return 0;
                """) >= 20
            )
            print("Movie list loaded")
            return True
        except TimeoutException:
            print("Timeout waiting for movie list, proceeding anyway...")
            return False
            
    def find_movie_list_container(self, soup):
        """Find the UL element that contains the movies"""
        uls = soup.find_all('ul')
        
        for ul in uls:
            lis = ul.find_all('li')
            if len(lis) >= 20:
                print(f"Found movie list container with {len(lis)} movies")
                return ul
                
        return None
        
    def scroll_to_load_all(self):
        """Scroll and click load more to get all movies"""
        print("Scrolling to load all movies...")
        
        last_height = 0
        no_new_content_count = 0
        max_no_new_content = 5
        
        while no_new_content_count < max_no_new_content:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Check for new content
            current_height = self.driver.execute_script("return document.body.scrollHeight")
            if current_height == last_height:
                no_new_content_count += 1
                print(f"No new content found (attempt {no_new_content_count}/{max_no_new_content})")
                
                # Try to find and click load more button
                try:
                    load_more_clicked = self.driver.execute_script("""
                        var buttons = document.querySelectorAll('button, a[role="button"]');
                        for (var i = 0; i < buttons.length; i++) {
                            var button = buttons[i];
                            var text = button.innerText || button.textContent || "";
                            if (text.match(/load|more|show|next|view/i) && 
                                button.offsetParent !== null) { // Visible button
                                button.click();
                                console.log("Clicked load more button:", text);
                                return true;
                            }
                        }
                        return false;
                    """)
                    
                    if load_more_clicked:
                        no_new_content_count = 0  # Reset counter
                        time.sleep(3)  # Wait for content to load
                    else:
                        print("No load more button found")
                except Exception as e:
                    print(f"Error clicking load more: {e}")
            else:
                no_new_content_count = 0
                last_height = current_height
                
            # Progress logging
            movie_count = self.driver.execute_script("""
                var uls = document.querySelectorAll('ul');
                for (var i = 0; i < uls.length; i++) {
                    if (uls[i].querySelectorAll('li').length >= 20) {
                        return uls[i].querySelectorAll('li').length;
                    }
                }
                return 0;
            """)
            print(f"  Current movie count: {movie_count}")

            if self.limit and movie_count >= self.limit:
                break

            # Stop once we have all 1000 movies
            if movie_count >= 1000:
                print("Reached 1000 movies")
                break

        print("Finished scrolling")
        time.sleep(3)
        
    def extract_movie_from_li(self, li, rank):
        """Extract movie data from a list item element"""
        try:
            # Find movie title from img alt attribute
            img = li.find('img')
            title = img.get('alt', '') if img else ''
            
            if not title:
                return None
                
            # Find ranking from div with # pattern - be more flexible
            rank_div = li.find(lambda tag: tag.name == 'div' and tag.string and '#' in tag.string)
            rank = int(rank_div.string.split('#')[1].strip())
            
            # Find director, country, and year from data-testid
            director = ""
            country = ""
            year = ""
            
            director_year_div = li.find('div', {'data-testid': 'director-and-year'})
            if director_year_div:
                spans = director_year_div.find_all('span')
                if len(spans) >= 3:
                    director = spans[0].get_text(strip=True)
                    country = spans[1].get_text(strip=True)
                    year = spans[2].get_text(strip=True)
                elif len(spans) == 2:
                    director = spans[0].get_text(strip=True)
                    year = spans[1].get_text(strip=True)
                elif len(spans) == 1:
                    # Try to parse year from single span
                    text = spans[0].get_text(strip=True)
                    year_match = re.search(r'(\d{4})', text)
                    if year_match:
                        year = year_match.group(1)
                    else:
                        director = text
            
            # Find URL
            link = li.find('a', href=lambda x: x and '/films/' in x)
            url = link.get('href', '') if link else ''

            # Check if movie is watchable (has a play button)
            play_button = li.find('div', {'data-testid': 'play-button'})
            watchable = play_button is not None

            return {
                'rank': rank,
                'title': title.strip(),
                'director': director.strip(),
                'country': country.strip(),
                'year': year.strip(),
                'url': url.strip(),
                'watchable': watchable,
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting movie from LI: {e}")
            return None
            
    def scrape(self):
        print("Starting Mubi 1000 scraper...")
        
        try:
            self.setup_driver()
            self.driver.get(self.base_url)
            
            # Wait for initial load
            print("Waiting for initial page load...")
            time.sleep(10)
            
            # Wait for movie list to load
            self.wait_for_content()
            
            # Scroll to load all movies
            self.scroll_to_load_all()
            
            # Parse the page with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Find the main movie list container
            movie_list = self.find_movie_list_container(soup)
            if not movie_list:
                print("Could not find movie list container")
                return []
                
            # Extract movies from list items
            lis = movie_list.find_all('li')
            print(f"Found {len(lis)} movies in list")
            
            for i, li in enumerate(lis):
                if self.limit and i >= self.limit:
                    break
                    
                movie = self.extract_movie_from_li(li, i + 1)
                if movie:
                    self.movies.append(movie)
                    
                    # Progress logging
                    if (i + 1) % 50 == 0:
                        print(f"Processed {i + 1} movies...")
            
            print(f"Successfully scraped {len(self.movies)} movies")
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return self.movies
        
    def _movies_equal(self, movies1, movies2):
        """Compare two movie lists, ignoring scraped_at timestamps."""
        if len(movies1) != len(movies2):
            return False

        for m1, m2 in zip(movies1, movies2):
            # Compare all fields except scraped_at
            for key in ['rank', 'title', 'director', 'country', 'year', 'url', 'watchable']:
                if m1.get(key) != m2.get(key):
                    return False
        return True

    def _write_csv(self, path):
        """Write movies to CSV using built-in csv module."""
        if not self.movies:
            return
        fieldnames = self.movies[0].keys()
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.movies)

    def save_data(self, filename=None):
        if not self.movies:
            print("No movies to save")
            return

        DATA_DIR.mkdir(exist_ok=True)
        latest_json = DATA_DIR / "latest.json"

        # Check if data has changed from latest
        if latest_json.exists():
            try:
                existing_movies = json.loads(latest_json.read_text(encoding='utf-8'))
                if self._movies_equal(self.movies, existing_movies):
                    print("No changes detected from latest data. Skipping save.")
                    return None
            except (json.JSONDecodeError, IOError) as e:
                print(f"Could not read existing data, will save new data: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if not filename:
            filename = f"mubi_top_1000_{timestamp}"

        json_file = DATA_DIR / f"{filename}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.movies, f, ensure_ascii=False, indent=2)

        csv_file = DATA_DIR / f"{filename}.csv"
        self._write_csv(csv_file)

        latest_csv = DATA_DIR / "latest.csv"

        with open(latest_json, 'w', encoding='utf-8') as f:
            json.dump(self.movies, f, ensure_ascii=False, indent=2)

        self._write_csv(latest_csv)

        print(f"Data saved to {json_file} and {csv_file}")
        print(f"Latest data saved to {latest_json} and {latest_csv}")

        return str(json_file), str(csv_file)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Scrape Mubi 1000 movies')
    parser.add_argument('--limit', type=int, help='Limit number of movies to scrape (for testing)')
    args = parser.parse_args()
    
    scraper = MubiScraper(limit=args.limit)
    movies = scraper.scrape()
    scraper.save_data()
