# Hacker News 200-Day Analysis

End-to-end workflow to scrape roughly 200 days of Hacker News stories and comments, analyze everything locally, and export publication-ready charts—no external databases required.

## Prerequisites

- Python 3.9+ with `pip`
- Google Chrome/Firefox (optional, only if you want to peek at the HTML being scraped)
- ~12 GB free disk (6–9 GB raw JSONL, ~2 GB zipped)
- 3–5 hours of network time for scraping (HTML crawling is slower than the Firebase API)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install --upgrade pip
pip install duckdb pandas plotly kaleido requests beautifulsoup4
```

## 1. Scrape the last ~200 days (HTML only)

```bash
python scrape_hn_200_days.py
```

- Walks `https://news.ycombinator.com/front?day=YYYY-MM-DD` for every day in the last ~200 days (including multi-page days).
- Fetches each story’s `item?id=` discussion thread, capturing the full HTML comment tree with parent/child links, timestamps, scores, and deleted markers.
- Saves newline-delimited JSON batches of 10k records as `hn_html_partN.jsonl`. Progress logs show the date, story ID range, and batch stats so you can track “which ideas landed in which page.”
- Implements polite scraping: shared HTTP session with retries, small delays between front pages, and bounded thread pools for comment requests.

## 2. Generate charts

```bash
python analyze_and_make_charts.py
```

- Loads all `*.jsonl` files into DuckDB (stories + comments share a table; use `type` to filter).
- Produces Plotly PNGs (1200×700) in `charts/`—daily activity (stories vs. non-deleted comments), best posting hour, top Show HNs, title-word correlations, most discussed threads, plus placeholders for more.

## 3. Share your findings

- Summarize key takeaways and drop the visuals into a blog post or Reddit/X thread.
- Suggested title: “I scraped and analyzed the last 200 days of Hacker News.”

## Tips

- Compress the JSONL files (`zip hn_html_part*.jsonl hn_html_dump.zip`) for archival.
- If the crawler is interrupted, just rerun it—it will start again from today and overwrite batches.
- Extend `analyze_and_make_charts.py` with more DuckDB queries; the dataset now includes `parent`, `kids`, and `deleted` flags, so you can build tree/graph metrics easily.

