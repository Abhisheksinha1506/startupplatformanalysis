# scrape_betalist.py
# Downloads ALL 31,000+ startups ever listed on BetaList.com (2013–2025)
import requests
from bs4 import BeautifulSoup
import json
import time
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://betalist.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BetaListArchive/1.0)"}

# Configuration
MAX_WORKERS = 8  # Concurrent requests for faster scraping
REQUEST_DELAY = 0.9  # Polite delay between batches
RETRY_LIMIT = 3
OUTPUT_FILE = "betalist_all.jsonl"

# Thread-safe collections
seen_slugs = set()
seen_lock = threading.Lock()
startups_lock = threading.Lock()
all_startups = []

thread_local = threading.local()


def build_session():
    """Create a session with retry logic and connection pooling"""
    session = getattr(thread_local, "session", None)
    if session is None:
        session = requests.Session()
        retry = Retry(
            total=RETRY_LIMIT,
            read=RETRY_LIMIT,
            connect=RETRY_LIMIT,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=MAX_WORKERS * 2,
            pool_maxsize=MAX_WORKERS * 4,
        )
        session.mount("https://", adapter)
        session.headers.update(HEADERS)
        thread_local.session = session
    return session


def scrape_page(page_num):
    """Scrape a single page and return startups found"""
    session = build_session()
    # Updated URL structure: pagination is on main page, not /startups
    if page_num == 1:
        url = f"{BASE}/"
    else:
        url = f"{BASE}/?page={page_num}"
    
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            return page_num, 0, []
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find all startup divs - they have id="startup-{id}"
        startup_divs = soup.find_all("div", id=lambda x: x and x.startswith("startup-"))
        
        if not startup_divs:
            return page_num, 0, []
        
        # Build a map of dates by finding date headers and associating them with following startups
        date_headers = soup.find_all("div", class_=lambda x: x and "col-span-full" in str(x) and "text-3xl" in str(x))
        startup_date_map = {}
        current_date = ""
        
        # Find the startup grid container
        startup_grid = soup.select_one(".startupGrid, [data-infinite-scroll-target='entries']")
        if startup_grid:
            # Process all children to track dates
            for element in startup_grid.find_all(True):
                classes = element.get('class', [])
                class_str = ' '.join(classes) if classes else ''
                
                # Check if it's a date header
                if 'col-span-full' in class_str and 'text-3xl' in class_str:
                    date_text = element.get_text(strip=True)
                    if date_text:
                        current_date = date_text
                # Check if it's a startup div
                elif element.get('id', '').startswith('startup-'):
                    if current_date:
                        startup_date_map[element.get('id')] = current_date
        
        page_startups = []
        for card in startup_divs:
            try:
                # Find the startup link
                link = card.find("a", href=lambda x: x and x.startswith("/startups/"))
                if not link:
                    continue
                
                slug = link["href"].split("/")[-1]
                
                # Thread-safe duplicate check
                with seen_lock:
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                
                # Extract title - look for link with font-medium class
                title_link = card.find("a", class_=lambda x: x and "font-medium" in str(x))
                title_text = title_link.get_text(strip=True) if title_link else "No title"
                
                # Extract tagline - look for link with text-gray-500 class
                tagline_link = card.find("a", class_=lambda x: x and "text-gray-500" in str(x))
                tagline_text = tagline_link.get_text(strip=True) if tagline_link else ""
                
                # Get date from map
                card_id = card.get('id', '')
                date_str = startup_date_map.get(card_id, "")
                
                # Categories - may not be visible in this view
                categories = []
                
                startup = {
                    "slug": slug,
                    "title": title_text,
                    "tagline": tagline_text,
                    "waitlist": 0,  # Not visible in main listing
                    "founder": "unknown",  # Not visible in main listing
                    "date": date_str,
                    "categories": categories,
                    "url": f"https://betalist.com{link['href']}",
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }
                page_startups.append(startup)
            except Exception:
                continue
        
        return page_num, len(page_startups), page_startups
    except Exception as e:
        return page_num, 0, []


def save_incremental():
    """Save startups incrementally to avoid data loss"""
    with startups_lock:
        if all_startups:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for startup in all_startups:
                    f.write(json.dumps(startup, ensure_ascii=False) + "\n")
            saved_count = len(all_startups)
            all_startups.clear()
            return saved_count
    return 0

def main():
    print("Starting FULL BetaList.com historical scrape (31,000+ startups)...")
    print(f"Using {MAX_WORKERS} concurrent workers with {REQUEST_DELAY}s delay between batches")
    
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
    
    page = 1
    consecutive_empty = 0
    max_pages = 2000  # Safety limit
    total_startups = 0
    last_save = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        
        while page <= max_pages and consecutive_empty < 5:
            # Submit batch of pages
            while len(futures) < MAX_WORKERS * 3 and page <= max_pages:
                future = executor.submit(scrape_page, page)
                futures[future] = page
                page += 1
            
            # Process completed futures
            for future in as_completed(futures):
                page_num = futures.pop(future)
                try:
                    page_num, count, page_startups = future.result()
                    if count == 0:
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0
                        # Thread-safe append
                        with startups_lock:
                            all_startups.extend(page_startups)
                        total_startups += count
                        print(f"Page {page_num} → {count} new | Total: {total_startups:,}")
                except Exception as e:
                    print(f"Error on page {page_num}: {e}")
                    consecutive_empty += 1
            
            # Save incrementally every 30 seconds or every 1000 startups
            if time.time() - last_save > 30 or total_startups % 1000 == 0:
                saved = save_incremental()
                if saved > 0:
                    print(f"  → Saved {saved:,} startups to {OUTPUT_FILE}")
                last_save = time.time()
            
            time.sleep(REQUEST_DELAY)  # Polite delay between batches
    
    # Final save
    final_saved = save_incremental()
    if final_saved > 0:
        print(f"  → Saved final {final_saved:,} startups to {OUTPUT_FILE}")
    
    # Count total in file
    total_in_file = 0
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            total_in_file = sum(1 for _ in f)
    except:
        pass
    
    print(f"\nSCRAPING COMPLETE! {total_in_file:,} startups saved → {OUTPUT_FILE}")
    print("Next → python analyze_betalist.py")


if __name__ == "__main__":
    main()

