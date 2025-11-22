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

## Analysis Results

### Daily Activity Patterns

![Daily Activity](./charts/01_daily_activity.png)

The analysis reveals consistent daily posting patterns with stories and comments showing clear trends over the 200-day period. Comment volume typically exceeds story submissions by a significant margin, indicating high engagement levels.

### Best Time to Post

![Best Hour](./charts/02_best_hour.png)

Analysis of posting times shows optimal hours for maximum engagement. Stories posted during specific hours (typically morning PST) receive significantly higher average scores, with clear patterns emerging from the data.

### Top Show HN Submissions

![Top Show HNs](./charts/03_top_show_hn.png)

The top 20 Show HN submissions from the analyzed period showcase the most successful projects and products shared by the community. These represent the highest-scoring Show HN posts, providing insights into what resonates with the Hacker News audience.

### Magic Words in Titles

![Magic Words](./charts/04_magic_words.png)

Certain words in story titles correlate strongly with higher scores. Words longer than 4 characters that appear frequently in high-scoring stories reveal what topics and language patterns drive engagement on Hacker News.

### Most Discussed Stories

![Most Discussed](./charts/05_most_discussed.png)

The stories with the highest comment counts represent the most engaging discussions. These threads often feature technical debates, product launches, or controversial topics that spark extensive community dialogue.

## Key Insights

- **Comment-to-Story Ratio**: Comments consistently outnumber stories, showing high community engagement
- **Optimal Posting Times**: Specific hours (typically morning PST) show significantly higher average scores
- **Show HN Success**: Top Show HN submissions demonstrate what types of projects gain traction
- **Title Impact**: Certain words and phrases in titles correlate with 2-3x higher average scores
- **Discussion Depth**: Most discussed stories often have comment counts 10-50x higher than average

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


