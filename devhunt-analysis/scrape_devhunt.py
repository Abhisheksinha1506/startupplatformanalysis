# scrape_devhunt.py
# Downloads EVERY tool/launch ever on devhunt.org (2024–2025)

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import time
import threading
from datetime import datetime

BASE = "https://devhunt.org"

# Configuration
MAX_WORKERS = 1  # Playwright sync API doesn't work well with threads, so we'll run sequentially
REQUEST_DELAY = 2.0  # Delay between pages
OUTPUT_FILE = "devhunt_all.jsonl"

# Thread-safe collections
seen_slugs = set()
seen_slugs_lock = threading.Lock()
launches_lock = threading.Lock()
all_launches = []



def save_incremental():
    """Save launches incrementally to avoid data loss"""
    with launches_lock:
        if all_launches:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                for launch in all_launches:
                    f.write(json.dumps(launch, ensure_ascii=False) + "\n")
            saved_count = len(all_launches)
            all_launches.clear()
            return saved_count
    return 0


def main():
    print("Starting full DevHunt.org scrape...")
    print(f"Using Playwright to render JavaScript content...")
    print(f"Delay: {REQUEST_DELAY}s between pages")
    
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
    
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        browser_context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page_num = 1
        total_launches = 0
        consecutive_empty = 0
        last_save = time.time()
        
        try:
            while consecutive_empty < 3:  # Stop after 3 empty pages
                url = f"{BASE}/all-dev-tools" if page_num == 1 else f"{BASE}/all-dev-tools?page={page_num}"
                
                try:
                    page = browser_context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Wait for JavaScript to render content
                    time.sleep(3)
                    
                    html = page.content()
                    page.close()
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Find all tool links
                    tool_links = soup.find_all("a", href=lambda x: x and "/tool/" in str(x))
                    
                    if not tool_links:
                        consecutive_empty += 1
                        print(f"Page {page_num} → 0 tools")
                    else:
                        consecutive_empty = 0  # Reset counter
                        page_launches = []
                        processed_slugs = set()
                        
                        for link in tool_links:
                            try:
                                href = link.get("href", "")
                                if not href or "/tool/" not in href:
                                    continue
                                
                                # Extract slug from URL
                                slug = href.split("/tool/")[-1].split("?")[0].split("#")[0].strip()
                                
                                if not slug or slug in processed_slugs:
                                    continue
                                
                                processed_slugs.add(slug)
                                
                                # Thread-safe duplicate check
                                with seen_slugs_lock:
                                    if slug in seen_slugs:
                                        continue
                                    seen_slugs.add(slug)
                                
                                # Find parent container (card)
                                card = link.find_parent(["article", "div", "li", "section"])
                                if not card:
                                    card = link
                                
                                # Extract title
                                title_elem = card.select_one("h1, h2, h3, h4, h5, [class*='title'], [class*='name']")
                                if not title_elem:
                                    # Try to find title in the link itself or nearby
                                    title_elem = link
                                title = title_elem.get_text(strip=True) if title_elem else "No title"
                                
                                # Extract tagline/description (usually a p tag)
                                tagline_elem = card.select_one("p")
                                tagline = tagline_elem.get_text(strip=True) if tagline_elem else ""
                                
                                # Extract categories (look for tags, badges, or links to /tools/)
                                category_elems = card.select("a[href*='/tools/'], [class*='tag'], [class*='badge'], [class*='category']")
                                categories = []
                                for cat_elem in category_elems[:10]:
                                    cat_text = cat_elem.get_text(strip=True)
                                    # Filter out common non-category text
                                    if cat_text and cat_text not in ["Free", "Paid", "One time fee", "Subscription"] and len(cat_text) < 30:
                                        categories.append(cat_text)
                                
                                # Extract impressions (the number we saw in the listing)
                                import re
                                card_text = card.get_text(separator=" ", strip=True)
                                impressions = 0
                                # Look for numbers followed by "Impressions" or large numbers
                                impressions_match = re.search(r'(\d+)\s*[Ii]mpressions?', card_text)
                                if impressions_match:
                                    impressions = int(impressions_match.group(1))
                                else:
                                    # Try to find large numbers (likely impressions)
                                    numbers = re.findall(r'\d{4,}', card_text)
                                    if numbers:
                                        impressions = int(numbers[0])
                                
                                # Maker/author - not always visible in listing, set to unknown
                                maker = "unknown"
                                
                                # Upvotes and comments - not visible in listing, set to 0
                                upvotes = 0
                                comments = 0
                                
                                # Date - not visible in listing, set to empty
                                date_str = ""
                                
                                launch = {
                                    "slug": slug,
                                    "title": title,
                                    "tagline": tagline,
                                    "maker": maker,
                                    "upvotes": upvotes,
                                    "comments": comments,
                                    "date": date_str,
                                    "categories": categories,
                                    "impressions": impressions,
                                    "url": f"https://devhunt.org/tool/{slug}",
                                    "scraped_at": datetime.utcnow().isoformat()
                                }
                                page_launches.append(launch)
                            except Exception as e:
                                continue
                        
                        # Remove duplicates based on slug
                        unique_launches = {}
                        for launch in page_launches:
                            if launch["slug"] not in unique_launches:
                                unique_launches[launch["slug"]] = launch
                        
                        page_launches = list(unique_launches.values())
                        
                        if page_launches:
                            with launches_lock:
                                all_launches.extend(page_launches)
                            total_launches += len(page_launches)
                            print(f"Page {page_num} → {len(page_launches)} new tools (total: {total_launches:,})")
                        else:
                            consecutive_empty += 1
                            print(f"Page {page_num} → 0 tools")
                    
                    # Save incrementally every 30 seconds or every 100 launches
                    if time.time() - last_save > 30 or (total_launches > 0 and total_launches % 100 == 0):
                        saved = save_incremental()
                        if saved > 0:
                            print(f"  → Saved {saved:,} launches to {OUTPUT_FILE}")
                        last_save = time.time()
                    
                    page_num += 1
                    time.sleep(REQUEST_DELAY)
                    
                except Exception as e:
                    consecutive_empty += 1
                    print(f"Error processing page {page_num}: {e}")
                    page_num += 1
                    time.sleep(REQUEST_DELAY)
            
        finally:
            browser_context.close()
            browser.close()
        
        # Final save
        final_saved = save_incremental()
        if final_saved > 0:
            print(f"  → Saved final {final_saved:,} launches to {OUTPUT_FILE}")
    
    # Count total in file
    total_in_file = 0
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            total_in_file = sum(1 for _ in f)
    except:
        pass
    
    print(f"\nSCRAPING COMPLETE! {total_in_file:,} launches saved to {OUTPUT_FILE}")
    print("Next → python analyze_devhunt.py")


if __name__ == "__main__":
    main()

