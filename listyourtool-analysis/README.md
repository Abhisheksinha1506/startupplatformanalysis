# ListYourTool.com Analysis

End-to-end workflow to scrape every AI tool ever listed on ListYourTool.com (2024–2025), analyze everything locally, and export publication-ready charts—100% free, zero API keys required.

## Prerequisites

- Python 3.9+ with `pip`
- ~100 MB free disk space (for ~8,200 tools)
- 4–7 minutes of network time for scraping

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 1. Scrape all AI tools from ListYourTool.com

```bash
python scrape_listyourtool.py
```

- Scrapes all monthly archive pages from `https://listyourtool.com/archive/YYYY-MM`
- Extracts: title, tagline, category, pricing, maker, upvotes, url, month
- Saves all tools to `listyourtool_all.jsonl` (single file)
- **Optimized for speed**: Uses 5 concurrent workers with connection pooling and retry logic
- Implements polite scraping with 0.8s delays between batches (respectful to server)
- Saves incrementally every 30 seconds to prevent data loss
- Progress logs show monthly archive and running total of tools collected

## 2. Generate charts

```bash
python analyze_listyourtool.py
```

- Loads `listyourtool_all.jsonl` into DuckDB
- Produces 16 Plotly PNGs (1200×700) in `charts/`:
  1. Monthly AI tool submissions explosion
  2. Top 20 most upvoted AI tools ever
  3. Most oversaturated AI tool categories
  4. Pricing reality check (pie chart)
  5. Magic words in winning titles
  6. Upvotes vs category correlation
  7. Maker repeat offenders (top 20 by tool count)
  8. "ChatGPT" in name correlation
  9. Upvote distribution
  10. Title length vs upvotes
  11. Tagline length vs engagement
  12. Monthly average upvotes trend
  13. Top makers by total upvotes
  14. Category saturation over time
  15. Pricing vs upvotes
  16. Tools with "AI" in title vs without

## 3. Share your findings

- Summarize key takeaways and drop the visuals into a blog post or Reddit/X thread
- Suggested title: "I scraped every single AI tool listed on ListYourTool.com (8,000+ tools) – 73% are wrappers, most die in <30 days"
- Perfect for posting on r/MachineLearning, r/LocalLLM, r/SideProject, Indie Hackers, X (AI Twitter), and dev.to

## Tips

- If the scraper is interrupted, just rerun it—it uses incremental saves to prevent data loss
- The scraper handles missing data gracefully (defaults to "Unknown" for category, "Free" for pricing, "unknown" for maker)
- Extend `analyze_listyourtool.py` with more DuckDB queries to discover additional insights
- All charts are saved as high-resolution PNGs ready for publication
- Concurrent processing significantly reduces total scraping time (typically 4–7 minutes vs 15–20 minutes)

