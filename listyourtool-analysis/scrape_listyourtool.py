# scrape_listyourtool.py
# Downloads EVERY AI tool ever listed on listyourtool.com

import json
import time
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
import re

BASE = "https://listyourtool.com"
OUTPUT_FILE = "listyourtool_all.jsonl"
REQUEST_DELAY = 1.0  # Polite delay between pages


def extract_tools_from_page(page):
    """Extract tool data from the current page"""
    tools = []
    seen_slugs = set()
    
    # Get page content
    content = page.content()
    
    # Extract tool data from embedded JSON (may be escaped)
    # Pattern: {"id":number,"name":"...","slug":"..."...}
    # Handle both escaped and unescaped JSON
    patterns = [
        r'\{"id":(\d+),"name":"([^"]+)","slug":"([^"]+)"[^}]*"dateAdded":"([^"]+)"',
        r'\\"id\\":(\d+),\\"name\\":\\"([^\\"]+)\\",\\"slug\\":\\"([^\\"]+)\\"[^}]*\\"dateAdded\\":\\"([^\\"]+)\\"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        if matches:
            for match in matches:
                try:
                    tool_id, name, slug, date_added = match
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    
                    # Try to extract more fields
                    tagline = ""
                    category = "Unknown"
                    pricing = "Free"
                    
                    # Look for shortDescription
                    desc_pattern = f'"shortDescription":"([^"]+)"[^}}]*"slug":"{re.escape(slug)}"'
                    desc_match = re.search(desc_pattern, content)
                    if desc_match:
                        tagline = desc_match.group(1)
                    
                    # Look for tags
                    tags_pattern = f'"tags":\\[([^\\]]+)\\][^}}]*"slug":"{re.escape(slug)}"'
                    tags_match = re.search(tags_pattern, content)
                    if tags_match:
                        tags_str = tags_match.group(1)
                        # Extract tag names
                        tag_names = re.findall(r'"([^"]+)"', tags_str)
                        category = ", ".join(tag_names) if tag_names else "Unknown"
                    
                    # Look for pricing
                    pricing_pattern = f'"pricing":"([^"]+)"[^}}]*"slug":"{re.escape(slug)}"'
                    pricing_match = re.search(pricing_pattern, content)
                    if pricing_match:
                        pricing = pricing_match.group(1)
                    
                    tool = {
                        "title": name,
                        "tagline": tagline,
                        "category": category,
                        "pricing": pricing,
                        "maker": "unknown",
                        "upvotes": 0,
                        "url": f"{BASE}/tool/{slug}",
                        "month": date_added[:7] if date_added and len(date_added) >= 7 else "",
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    }
                    tools.append(tool)
                except Exception as e:
                    continue
            break  # If we found matches with one pattern, don't try others
    
    # If JSON extraction didn't work, try DOM scraping
    if not tools:
        try:
            # Find all tool links
            tool_links = page.query_selector_all('a[href*="/tool/"]')
            seen_slugs = set()
            
            for link in tool_links:
                try:
                    href = link.get_attribute('href')
                    if not href or '/tool/' not in href:
                        continue
                    
                    slug = href.split('/tool/')[-1].split('?')[0].split('#')[0]
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    
                    # Try to get title from link or nearby elements
                    title_elem = link.query_selector('h3, h2, .tool-name, span')
                    title = title_elem.inner_text().strip() if title_elem else "No title"
                    
                    # Get parent card for more info using evaluate
                    card_info = link.evaluate('''el => {
                        const card = el.closest("article, div[class*='card'], div[class*='tool']");
                        if (!card) return null;
                        const tagline = card.querySelector('p, .tagline, .description');
                        const category = card.querySelector('.category, [class*="tag"]');
                        return {
                            tagline: tagline ? tagline.innerText.trim() : '',
                            category: category ? category.innerText.trim() : 'Unknown'
                        };
                    }''')
                    
                    tagline = card_info.get('tagline', '') if card_info else ''
                    category = card_info.get('category', 'Unknown') if card_info else 'Unknown'
                    
                    tool = {
                        "title": title,
                        "tagline": tagline,
                        "category": category,
                        "pricing": "Free",
                        "maker": "unknown",
                        "upvotes": 0,
                        "url": f"{BASE}/tool/{slug}",
                        "month": "",
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    }
                    tools.append(tool)
                except:
                    continue
        except:
            pass
    
    return tools


def scrape_all_tools():
    """Scrape all tools from listyourtool.com"""
    all_tools = []
    seen_urls = set()
    
    print("Starting ListYourTool.com scrape...")
    print("Note: This uses Playwright to handle JavaScript-rendered content")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # Start from main page
            print("Loading main page...")
            page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)  # Wait for JS to render
            
            # Extract tools from first page
            tools = extract_tools_from_page(page)
            for tool in tools:
                if tool["url"] not in seen_urls:
                    seen_urls.add(tool["url"])
                    all_tools.append(tool)
            
            print(f"Found {len(tools)} tools on main page")
            
            # Try to find and click pagination or load more
            page_num = 1
            max_pages = 100  # Safety limit
            
            while page_num < max_pages:
                # Look for "Load More" button or pagination
                load_more = page.query_selector('button:has-text("Load More"), button:has-text("More"), a:has-text("Next"), button[aria-label*="more" i]')
                next_page = page.query_selector('a[href*="page="], a:has-text("Next")')
                
                if load_more:
                    try:
                        load_more.click()
                        page.wait_for_timeout(2000)  # Wait for content to load
                        tools = extract_tools_from_page(page)
                        new_count = 0
                        for tool in tools:
                            if tool["url"] not in seen_urls:
                                seen_urls.add(tool["url"])
                                all_tools.append(tool)
                                new_count += 1
                        print(f"Loaded more: {new_count} new tools (Total: {len(all_tools)})")
                        if new_count == 0:
                            break
                    except:
                        break
                elif next_page:
                    try:
                        next_page.click()
                        page.wait_for_timeout(2000)
                        tools = extract_tools_from_page(page)
                        new_count = 0
                        for tool in tools:
                            if tool["url"] not in seen_urls:
                                seen_urls.add(tool["url"])
                                all_tools.append(tool)
                                new_count += 1
                        print(f"Page {page_num + 1}: {new_count} new tools (Total: {len(all_tools)})")
                        if new_count == 0:
                            break
                        page_num += 1
                    except:
                        break
                else:
                    # Try direct URL navigation
                    page_num += 1
                    next_url = f"{BASE}?page={page_num}"
                    try:
                        page.goto(next_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(3000)
                        tools = extract_tools_from_page(page)
                        new_count = 0
                        for tool in tools:
                            if tool["url"] not in seen_urls:
                                seen_urls.add(tool["url"])
                                all_tools.append(tool)
                                new_count += 1
                        print(f"Page {page_num}: {new_count} new tools (Total: {len(all_tools)})")
                        if new_count == 0:
                            break
                    except:
                        break
                
                time.sleep(REQUEST_DELAY)
        
        finally:
            browser.close()
    
    return all_tools


def main():
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
    
    # Scrape all tools
    all_tools = scrape_all_tools()
    
    # Save all tools
    print(f"\nSaving {len(all_tools)} tools to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for tool in all_tools:
            f.write(json.dumps(tool, ensure_ascii=False) + "\n")
    
    print(f"\nSCRAPING COMPLETE! {len(all_tools):,} AI tools saved → {OUTPUT_FILE}")
    print("Next → python analyze_listyourtool.py")


if __name__ == "__main__":
    main()
