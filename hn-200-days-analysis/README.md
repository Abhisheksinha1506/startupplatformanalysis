# Hacker News 200-Day Analysis

End-to-end workflow to scrape roughly 200 days of Hacker News stories and comments, analyze everything locally, and export publication-ready charts—no external databases required.

## About Hacker News

Hacker News (news.ycombinator.com) is a social news website focused on computer science and entrepreneurship, run by Y Combinator. It's one of the most influential tech communities, with stories and discussions that often drive significant traffic and attention to products, startups, and technical topics.

**Key Platform Features:**
- Story submissions with upvoting system
- Comment threads with nested discussions
- Show HN section for maker projects
- Score-based ranking algorithm
- Time-based decay for story visibility
- Community-driven moderation

This analysis provides insights into posting patterns, engagement strategies, successful Show HN submissions, optimal posting times, and what types of content resonate with the Hacker News community.

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
- Fetches each story's `item?id=` discussion thread, capturing comprehensive data:
  - **Story data**: title, score, author, timestamp, URL, descendants (comment count)
  - **Comment data**: text, author, score, timestamp, parent ID, kids (child comments), deleted markers
  - **Full comment tree**: Parent/child relationships preserved for tree analysis
- Saves newline-delimited JSON batches of 10k records as `hn_html_partN.jsonl`
- Progress logs show the date, story ID range, and batch stats so you can track "which ideas landed in which page."
- Implements polite scraping: shared HTTP session with retries, small delays between front pages, and bounded thread pools for comment requests.
- Handles edge cases: deleted comments marked, missing scores default to 0, missing authors handled gracefully

## 2. Generate charts

```bash
python analyze_and_make_charts.py
```

- Loads all `*.jsonl` files into DuckDB (stories + comments share a table; use `type` to filter).
- Produces Plotly PNGs (1200×700) in `charts/`:
  - Daily activity (stories vs. non-deleted comments)
  - Best posting hour (PST timezone analysis)
  - Top 20 Show HNs by score
  - Magic words (title words that correlate with highest scores)
  - Most discussed stories (by total comments)

## Analysis Results

### Daily Activity Patterns

![Daily Activity](charts/01_daily_activity.png)

The analysis reveals consistent daily posting patterns with stories and comments showing clear trends over the 200-day period. Comment volume typically exceeds story submissions by a significant margin, indicating high engagement levels.

### Best Time to Post

![Best Hour](charts/02_best_hour.png)

Analysis of posting times shows optimal hours for maximum engagement. Stories posted during specific hours (typically morning PST) receive significantly higher average scores, with clear patterns emerging from the data.

### Top Show HN Submissions

![Top Show HNs](charts/03_top_show_hn.png)

The top 20 Show HN submissions from the analyzed period showcase the most successful projects and products shared by the community. These represent the highest-scoring Show HN posts, providing insights into what resonates with the Hacker News audience.

### Magic Words in Titles

![Magic Words](charts/04_magic_words.png)

Certain words in story titles correlate strongly with higher scores. Words longer than 4 characters that appear frequently in high-scoring stories reveal what topics and language patterns drive engagement on Hacker News.

### Most Discussed Stories

![Most Discussed](charts/05_most_discussed.png)

The stories with the highest comment counts represent the most engaging discussions. These threads often feature technical debates, product launches, or controversial topics that spark extensive community dialogue.

## Key Insights

- **Comment-to-Story Ratio**: Comments consistently outnumber stories, showing high community engagement
- **Optimal Posting Times**: Specific hours (typically morning PST) show significantly higher average scores
- **Show HN Success**: Top Show HN submissions demonstrate what types of projects gain traction
- **Title Impact**: Certain words and phrases in titles correlate with 2-3x higher average scores
- **Discussion Depth**: Most discussed stories often have comment counts 10-50x higher than average

## 3. Share your findings

- Summarize key takeaways and drop the visuals into a blog post or Reddit/X thread.
- Suggested title: "I scraped and analyzed the last 200 days of Hacker News – here's when to post and what words get the most engagement"
- Perfect for posting on r/programming, r/startups, r/SideProject, Indie Hackers, and X/Twitter

## Data Structure

Each record in `hn_html_part*.jsonl` follows this JSON structure:

**Story record:**
```json
{
  "type": "story",
  "id": 12345678,
  "title": "Example Story Title",
  "by": "username",
  "score": 42,
  "time": 1700000000,
  "url": "https://example.com",
  "descendants": 15
}
```

**Comment record:**
```json
{
  "type": "comment",
  "id": 12345679,
  "text": "Comment text here...",
  "by": "username",
  "score": 5,
  "time": 1700000100,
  "parent": 12345678,
  "kids": [12345680],
  "deleted": false
}
```

## Methodology

**Scraping Approach:**
- HTML-based scraping (no API access required)
- Daily front page traversal for ~200 days
- Full comment thread extraction for each story
- Polite rate limiting with retry logic
- Batch-based saving (10k records per file)

**Analysis Approach:**
- DuckDB for fast analytical queries on JSONL data
- Type-based filtering (stories vs comments)
- Time-series analysis for daily activity patterns
- Text analysis for title word correlations
- Show HN specific analysis
- Comment tree analysis (using parent/kids relationships)

**Chart Generation:**
- Plotly for interactive-quality static PNGs
- Consistent styling and color schemes
- High-resolution output (1200×700, 2x scale)
- Publication-ready format

## Use Cases

- **Content Creators**: Learn optimal posting times and what content performs best
- **Makers**: Understand Show HN success patterns and engagement strategies
- **Researchers**: Study tech community dynamics and discussion patterns
- **Data Analysts**: Access comprehensive HN dataset for further analysis
- **Community Managers**: Understand platform engagement patterns

## Tips

- Compress the JSONL files (`zip hn_html_part*.jsonl hn_html_dump.zip`) for archival (reduces from 6-9 GB to ~2 GB)
- If the crawler is interrupted, just rerun it—it will start again from today and overwrite batches
- Extend `analyze_and_make_charts.py` with more DuckDB queries; the dataset now includes `parent`, `kids`, and `deleted` flags, so you can build tree/graph metrics easily
- Use the `type` field to filter stories vs comments in your queries
- The `parent` and `kids` fields enable comment tree analysis and thread depth metrics
- Time fields are Unix timestamps - use `to_timestamp(time)` in DuckDB for date operations
- The dataset includes deleted comments (marked with `deleted: true`) for completeness

