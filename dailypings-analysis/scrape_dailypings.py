# scrape_dailypings.py
# Downloads EVERY ping ever posted on dailypings.com (2024–2025)
import requests
from bs4 import BeautifulSoup
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://dailypings.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DailyPingsAnalyzer/1.0; +https://yourtwitter.com)"
}

# Configuration
MAX_WORKERS = 5  # Concurrent page processing
REQUEST_DELAY = 0.8  # Reduced delay for faster scraping
RETRY_LIMIT = 3
OUTPUT_FILE = "dailypings_all.jsonl"

# Thread-safe collections
seen_ids = set()
seen_ids_lock = threading.Lock()
pings_lock = threading.Lock()
all_pings = []

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
    """Scrape a single page"""
    session = build_session()
    # Try different URL patterns for pagination
    if page_num == 1:
        url = BASE_URL
    else:
        # Try query parameter first, fallback to /page/ pattern
        url = f"{BASE_URL}?page={page_num}"
    
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            return None, 0
        
        soup = BeautifulSoup(r.text, 'html.parser')
        # New structure: articles instead of ping-card divs
        articles = soup.select("article")
        
        if not articles:
            return None, 0
        
        page_pings = []
        for article in articles:
            try:
                # Find the title link (first link in the article that goes to /posts/)
                title_link = article.find("a", href=lambda x: x and x.startswith("/posts/"))
                if not title_link:
                    continue
                
                post_slug = title_link["href"].split("/")[-1]
                post_id = post_slug  # Use slug as ID
                
                # Thread-safe duplicate check
                with seen_ids_lock:
                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)
                
                # Extract title
                title_text = title_link.get_text(strip=True) if title_link else "No title"
                
                # Extract author (link with /user/ in the article)
                author_link = article.find("a", href=lambda x: x and x.startswith("/user/"))
                author_text = author_link.get_text(strip=True) if author_link else "unknown"
                
                # Extract upvotes (first span in button with upvote icon)
                # The structure is: button > span (with number) > span (with icon)
                upvote_button = article.find("button", title=lambda x: x and "upvote" in x.lower())
                upvotes_count = 0
                if upvote_button:
                    # Find the first span which should contain the number
                    spans = upvote_button.find_all("span")
                    if spans:
                        try:
                            upvotes_count = int(spans[0].get_text(strip=True))
                        except (ValueError, IndexError):
                            upvotes_count = 0
                
                # Extract date - it's in a span after "by" and author link, separated by "|"
                # Structure: <span>by</span><a>author</a><span>|</span><span>date text</span>
                date_str = ""
                # Find all text in the metadata area and look for date patterns
                metadata_div = article.find("div", class_=lambda x: x and "text-muted-foreground" in str(x) and "text-xs" in str(x))
                if metadata_div:
                    # Get all text and find the date part (usually after "|")
                    all_text = metadata_div.get_text(" ", strip=True)
                    # Split by "|" and take the last part which should be the date
                    parts = all_text.split("|")
                    if len(parts) > 1:
                        date_str = parts[-1].strip()
                    else:
                        # Fallback: look for spans with date-like patterns
                        for span in metadata_div.find_all("span"):
                            text = span.get_text(strip=True)
                            if text and ("ago" in text.lower() or "day" in text.lower() or "hour" in text.lower() or "minute" in text.lower()):
                                date_str = text
                                break
                
                # Description not visible in current HTML structure
                desc_text = ""
                
                # Comments count not visible in current HTML structure
                comments_count = 0
                
                ping = {
                    "id": post_id,
                    "title": title_text,
                    "description": desc_text,
                    "author": author_text,
                    "upvotes": upvotes_count,
                    "comments": comments_count,
                    "date": date_str,
                    "url": f"https://dailypings.com{title_link['href']}",
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                }
                page_pings.append(ping)
            except Exception as e:
                continue
        
        return page_pings, len(page_pings)
    except Exception as e:
        return None, 0


def save_incremental():
    """Save pings incrementally to avoid data loss"""
    with pings_lock:
        if all_pings:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for ping in all_pings:
                    f.write(json.dumps(ping, ensure_ascii=False) + "\n")
            saved_count = len(all_pings)
            all_pings.clear()
            return saved_count
    return 0


def main():
    print("Starting DailyPings.com full scrape...")
    print(f"Using {MAX_WORKERS} concurrent workers with {REQUEST_DELAY}s delay between batches")
    
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
    
    page = 1
    total_pings = 0
    consecutive_empty = 0
    last_save = time.time()
    
    while consecutive_empty < 3:  # Stop after 3 empty pages
        # Fetch a batch of pages concurrently
        batch_pages = list(range(page, page + MAX_WORKERS))
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_page = {executor.submit(scrape_page, p): p for p in batch_pages}
            
            batch_added = 0
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    page_pings, added = future.result()
                    if page_pings is None or added == 0:
                        consecutive_empty += 1
                        print(f"Page {page_num} → 0 pings")
                    else:
                        consecutive_empty = 0  # Reset counter
                        # Thread-safe append
                        with pings_lock:
                            all_pings.extend(page_pings)
                        total_pings += added
                        batch_added += added
                        print(f"Page {page_num} → {added} new pings (total: {total_pings:,})")
                except Exception as e:
                    consecutive_empty += 1
                    print(f"Error processing page {page_num}: {e}")
        
        if batch_added == 0:
            consecutive_empty += 1
        
        # Save incrementally every 30 seconds or every 100 pings
        if time.time() - last_save > 30 or total_pings % 100 == 0:
            saved = save_incremental()
            if saved > 0:
                print(f"  → Saved {saved:,} pings to {OUTPUT_FILE}")
            last_save = time.time()
        
        page += MAX_WORKERS
        time.sleep(REQUEST_DELAY)
    
    # Final save
    final_saved = save_incremental()
    if final_saved > 0:
        print(f"  → Saved final {final_saved:,} pings to {OUTPUT_FILE}")
    
    # Count total in file
    total_in_file = 0
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            total_in_file = sum(1 for _ in f)
    except:
        pass
    
    print(f"\nSCRAPING COMPLETE! {total_in_file:,} pings saved to {OUTPUT_FILE}")
    print("Next: run python analyze_dailypings.py")


if __name__ == "__main__":
    main()

