# analyze_dailypings.py
import duckdb
import pandas as pd
import plotly.express as px
import os
import re
from datetime import datetime, timedelta

# Load and preprocess data
print("Loading and preprocessing data...")
df = pd.read_json('dailypings_all.jsonl', lines=True)

# Parse relative dates to actual dates
def parse_relative_date(date_str, scraped_at_str):
    """Parse relative date strings like 'about 3 hours ago' to actual dates"""
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        scraped_at = pd.to_datetime(scraped_at_str)
    except:
        return None
    
    date_lower = date_str.lower().strip()
    
    # Handle "about X hours ago"
    match = re.search(r'about\s+(\d+)\s+hours?\s+ago', date_lower)
    if match:
        hours = int(match.group(1))
        return scraped_at - timedelta(hours=hours)
    
    # Handle "X hours ago" (without "about")
    match = re.search(r'(\d+)\s+hours?\s+ago', date_lower)
    if match:
        hours = int(match.group(1))
        return scraped_at - timedelta(hours=hours)
    
    # Handle "X days ago"
    match = re.search(r'(\d+)\s+days?\s+ago', date_lower)
    if match:
        days = int(match.group(1))
        return scraped_at - timedelta(days=days)
    
    # Handle "X minutes ago"
    match = re.search(r'(\d+)\s+minutes?\s+ago', date_lower)
    if match:
        minutes = int(match.group(1))
        return scraped_at - timedelta(minutes=minutes)
    
    # Handle "just now" or "now"
    if 'just now' in date_lower or date_lower == 'now':
        return scraped_at
    
    return None

# Apply date parsing
df['parsed_date'] = df.apply(lambda row: parse_relative_date(row['date'], row['scraped_at']), axis=1)
df['parsed_date'] = pd.to_datetime(df['parsed_date'])

# Create DuckDB connection and load processed data
con = duckdb.connect()
con.register('df', df)
con.execute("CREATE OR REPLACE TABLE pings AS SELECT * FROM df")

os.makedirs("charts", exist_ok=True)
def save(fig, name):
    try:
        fig.write_image(f"charts/{name}.png", width=1200, height=700, scale=2)
        print(f"Saved charts/{name}.png")
    except Exception as e:
        print(f"Error saving {name}.png: {e}")

print("Generating 12 viral charts...")

# 1. Growth over time
df = con.execute("""
SELECT DATE(parsed_date) as day, COUNT(*) as pings
FROM pings WHERE parsed_date IS NOT NULL
GROUP BY 1 ORDER BY 1
""").df()
if not df.empty:
    fig = px.area(df, x='day', y='pings', title="DailyPings.com Growth – Pings per Day (2024–2025)")
    save(fig, "01_growth_over_time")
else:
    print("Skipping chart 01: No date data available")

# 2. Most upvoted pings ever
df = con.execute("SELECT title, author, upvotes, url FROM pings WHERE upvotes > 0 ORDER BY upvotes DESC LIMIT 15").df()
if not df.empty and len(df) > 0:
    # Truncate long titles
    df['title_short'] = df['title'].apply(lambda x: x[:50] + '...' if len(str(x)) > 50 else x)
    fig = px.bar(df, y='title_short', x='upvotes', orientation='h', title="Top 15 Most Upvoted Pings Ever")
    fig.update_yaxes(autorange="reversed")
    save(fig, "02_most_upvoted")
else:
    print("Skipping chart 02: No upvote data available")

# 3. Best day to post
df = con.execute("""
SELECT 
    strftime(DATE(parsed_date), '%A') as weekday,
    COUNT(*) as posts,
    AVG(upvotes) as avg_upvotes
FROM pings WHERE parsed_date IS NOT NULL
GROUP BY 1 ORDER BY avg_upvotes DESC
""").df()
if not df.empty:
    fig = px.bar(df, x='weekday', y='avg_upvotes', title="Best Day to Post on DailyPings (Avg Upvotes)")
    save(fig, "03_best_day")
else:
    print("Skipping chart 03: No date data available")

# 4. Magic title words
df = con.execute("""
WITH words AS (
  SELECT UNNEST(regexp_split_to_array(LOWER(title), '\\W+')) as word, upvotes
  FROM pings WHERE upvotes > 5 AND title IS NOT NULL
)
SELECT word, COUNT(*) as freq, AVG(upvotes) as avg
FROM words 
WHERE LENGTH(word) > 4 AND word NOT IN ('with','from','this','just','your','that','have','will','make','more','most','best','first')
GROUP BY word HAVING COUNT(*) >= 5
ORDER BY avg DESC LIMIT 25
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='word', y='avg', title="Title Words That Get The Most Upvotes")
    fig.update_xaxes(tickangle=45)
    save(fig, "04_magic_words")
else:
    print("Skipping chart 04: Insufficient word data")

# 5. Top authors by total upvotes
df = con.execute("""
SELECT author, COUNT(*) as ping_count, SUM(upvotes) as total_upvotes, AVG(upvotes) as avg_upvotes
FROM pings
WHERE author != 'unknown'
GROUP BY author
HAVING COUNT(*) >= 2
ORDER BY total_upvotes DESC
LIMIT 20
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='author', y='total_upvotes', title="Top 20 Authors by Total Upvotes")
    fig.update_xaxes(tickangle=45)
    save(fig, "05_top_authors")
else:
    print("Skipping chart 05: No author data available")

# 6. Upvotes vs Comments correlation
df = con.execute("SELECT upvotes, comments FROM pings WHERE upvotes > 0 AND comments > 0").df()
if not df.empty and len(df) > 10:
    fig = px.scatter(df, x='upvotes', y='comments', title="Upvotes vs Comments Correlation", trendline="ols")
    save(fig, "06_upvotes_vs_comments")
else:
    print("Skipping chart 06: Insufficient upvote/comment data")

# 7. Monthly posting activity
df = con.execute("""
SELECT 
    DATE_TRUNC('month', parsed_date) as month,
    COUNT(*) as pings,
    AVG(upvotes) as avg_upvotes
FROM pings 
WHERE parsed_date IS NOT NULL
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty:
    fig = px.bar(df, x='month', y='pings', title="Monthly Posting Activity on DailyPings")
    save(fig, "07_monthly_activity")
else:
    print("Skipping chart 07: No date data available")

# 8. Description length vs engagement
df = con.execute("""
SELECT 
    LENGTH(description) as desc_length,
    AVG(upvotes) as avg_upvotes,
    AVG(comments) as avg_comments
FROM pings
WHERE description != '' AND upvotes > 0
GROUP BY 1
HAVING COUNT(*) >= 5
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.scatter(df, x='desc_length', y='avg_upvotes', title="Description Length vs Average Upvotes", trendline="ols")
    save(fig, "08_desc_length_vs_upvotes")
else:
    print("Skipping chart 08: Insufficient description/upvote data")

# 9. Hour of day analysis (if time data available)
df = con.execute("""
SELECT 
    EXTRACT(HOUR FROM parsed_date) as hour,
    COUNT(*) as pings,
    AVG(upvotes) as avg_upvotes
FROM pings 
WHERE parsed_date IS NOT NULL
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty:
    fig = px.bar(df, x='hour', y='avg_upvotes', title="Best Hour to Post (Avg Upvotes by Hour)")
    save(fig, "09_best_hour")
else:
    print("Skipping chart 09: No date data available")

# 10. Engagement rate distribution
df = con.execute("""
SELECT 
    CASE 
        WHEN upvotes = 0 THEN '0'
        WHEN upvotes BETWEEN 1 AND 5 THEN '1-5'
        WHEN upvotes BETWEEN 6 AND 10 THEN '6-10'
        WHEN upvotes BETWEEN 11 AND 20 THEN '11-20'
        WHEN upvotes BETWEEN 21 AND 50 THEN '21-50'
        ELSE '50+'
    END as upvote_range,
    COUNT(*) as count
FROM pings
GROUP BY 1
ORDER BY 
    CASE 
        WHEN upvote_range = '0' THEN 1
        WHEN upvote_range = '1-5' THEN 2
        WHEN upvote_range = '6-10' THEN 3
        WHEN upvote_range = '11-20' THEN 4
        WHEN upvote_range = '21-50' THEN 5
        ELSE 6
    END
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='upvote_range', y='count', title="Distribution of Upvotes Across All Pings")
    save(fig, "10_upvote_distribution")
else:
    print("Skipping chart 10: No upvote data available")

# 11. Most discussed pings (by comments)
df = con.execute("SELECT title, author, comments, upvotes, url FROM pings WHERE comments > 0 ORDER BY comments DESC LIMIT 15").df()
if not df.empty and len(df) > 0:
    # Truncate long titles
    df['title_short'] = df['title'].apply(lambda x: x[:50] + '...' if len(str(x)) > 50 else x)
    fig = px.bar(df, y='title_short', x='comments', orientation='h', title="Top 15 Most Discussed Pings (by Comments)")
    fig.update_yaxes(autorange="reversed")
    save(fig, "11_most_discussed")
else:
    print("Skipping chart 11: No comment data available")

# 12. Title length vs engagement
df = con.execute("""
SELECT 
    LENGTH(title) as title_length,
    AVG(upvotes) as avg_upvotes,
    AVG(comments) as avg_comments
FROM pings
WHERE title != '' AND upvotes > 0
GROUP BY 1
HAVING COUNT(*) >= 5
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.scatter(df, x='title_length', y='avg_upvotes', title="Title Length vs Average Upvotes", trendline="ols")
    save(fig, "12_title_length_vs_upvotes")
else:
    print("Skipping chart 12: Insufficient title/upvote data")

print("ALL CHARTS READY IN /charts !")
print("Post title: 'I scraped every single ping on DailyPings.com (3000+ launches) – here's what gets makers excited'")
print("You're done. Go post it!")

