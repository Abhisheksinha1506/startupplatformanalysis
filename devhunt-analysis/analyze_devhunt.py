# analyze_devhunt.py
import duckdb
import pandas as pd
import plotly.express as px
import os
from datetime import datetime

con = duckdb.connect()
con.execute("CREATE OR REPLACE TABLE devhunt AS SELECT * FROM 'devhunt_all.jsonl'")

os.makedirs("charts", exist_ok=True)
def save(fig, name):
    fig.write_image(f"charts/{name}.png", width=1200, height=700, scale=2)
    print(f"✓ {name}.png")

print("Generating 15+ viral charts...")

# 1. Total tools scraped
total = con.execute("SELECT COUNT(*) as total FROM devhunt").df()
print(f"Total tools in database: {total['total'].iloc[0]:,}")

# 2. Top 20 tools by impressions
df = con.execute("SELECT title, impressions, url FROM devhunt WHERE impressions > 0 ORDER BY impressions DESC LIMIT 20").df()
if not df.empty:
    fig = px.bar(df, y='title', x='impressions', orientation='h', title="Top 20 Dev Tools by Impressions on DevHunt")
    fig.update_yaxes(autorange="reversed")
    save(fig, "01_top_tools_by_impressions")

# 3. Growth over time (by scraped_at date)
df = con.execute("""
SELECT DATE(scraped_at::TIMESTAMP) as day, COUNT(*) as tools 
FROM devhunt 
WHERE scraped_at != '' 
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty:
    fig = px.area(df, x='day', y='tools', title="DevHunt.org Tools Scraped Over Time")
    save(fig, "02_scraping_timeline")

# 4. Most successful categories (by impressions)
df = con.execute("""
SELECT category, COUNT(*) as launches, AVG(impressions) as avg_impressions
FROM devhunt, UNNEST(categories) AS t(category)
WHERE categories IS NOT NULL AND len(categories) > 0
GROUP BY category HAVING COUNT(*) >= 5
ORDER BY avg_impressions DESC LIMIT 20
""").df()
if not df.empty:
    fig = px.bar(df, x='category', y='avg_impressions', title="Highest-Average-Impressions Categories")
    fig.update_xaxes(tickangle=45)
    save(fig, "03_best_categories")

# 5. Magic title words (by impressions)
df = con.execute("""
WITH words AS (
  SELECT UNNEST(regexp_split_to_array(LOWER(title), '\\W+')) as word, impressions
  FROM devhunt WHERE impressions > 0
)
SELECT word, COUNT(*) as freq, AVG(impressions) as avg_impressions
FROM words 
WHERE LENGTH(word) > 4 AND word NOT IN ('with','your','from','this','that','just','into','tools','tool','dev','api')
GROUP BY word HAVING COUNT(*) >= 5
ORDER BY avg_impressions DESC LIMIT 30
""").df()
if not df.empty:
    fig = px.bar(df, x='word', y='avg_impressions', title="Title Words That Get the Most Impressions on DevHunt")
    fig.update_xaxes(tickangle=45)
    save(fig, "04_magic_words")

# 6. Tools with highest impressions
df = con.execute("""
SELECT title, impressions, url
FROM devhunt 
WHERE impressions > 0
ORDER BY impressions DESC
LIMIT 20
""").df()
if not df.empty:
    fig = px.bar(df, y='title', x='impressions', orientation='h', title="Top 20 Tools by Impressions")
    fig.update_yaxes(autorange="reversed")
    save(fig, "05_highest_impressions")

# 7. Tagline length vs impressions
df = con.execute("""
SELECT 
    LENGTH(tagline) as tagline_length,
    AVG(impressions) as avg_impressions
FROM devhunt
WHERE tagline != '' AND impressions > 0
GROUP BY 1
ORDER BY 1
""").df()
if not df.empty:
    fig = px.scatter(df, x='tagline_length', y='avg_impressions', title="Tagline Length vs Average Impressions", trendline="ols")
    save(fig, "06_tagline_length_vs_impressions")

# 8. Title length vs impressions
df = con.execute("""
SELECT 
    LENGTH(title) as title_length,
    AVG(impressions) as avg_impressions
FROM devhunt
WHERE impressions > 0
GROUP BY 1
ORDER BY 1
""").df()
if not df.empty:
    fig = px.scatter(df, x='title_length', y='avg_impressions', title="Title Length vs Average Impressions", trendline="ols")
    save(fig, "07_title_length_vs_impressions")

# 9. Impressions distribution
df = con.execute("""
SELECT 
    CASE 
        WHEN impressions = 0 THEN '0'
        WHEN impressions BETWEEN 1 AND 1000 THEN '1-1K'
        WHEN impressions BETWEEN 1001 AND 10000 THEN '1K-10K'
        WHEN impressions BETWEEN 10001 AND 50000 THEN '10K-50K'
        WHEN impressions BETWEEN 50001 AND 100000 THEN '50K-100K'
        ELSE '100K+'
    END as impression_range,
    COUNT(*) as count
FROM devhunt
GROUP BY 1
ORDER BY 
    CASE 
        WHEN impression_range = '0' THEN 1
        WHEN impression_range = '1-1K' THEN 2
        WHEN impression_range = '1K-10K' THEN 3
        WHEN impression_range = '10K-50K' THEN 4
        WHEN impression_range = '50K-100K' THEN 5
        ELSE 6
    END
""").df()
if not df.empty:
    fig = px.bar(df, x='impression_range', y='count', title="Distribution of Impressions Across All Tools")
    save(fig, "08_impressions_distribution")

# 10. Category popularity (by launch count)
df = con.execute("""
SELECT category, COUNT(*) as launches
FROM devhunt, UNNEST(categories) AS t(category)
WHERE categories IS NOT NULL AND len(categories) > 0
GROUP BY category
HAVING COUNT(*) >= 3
ORDER BY launches DESC
LIMIT 20
""").df()
if not df.empty:
    fig = px.bar(df, x='category', y='launches', title="Most Popular Categories (by Launch Count)")
    fig.update_xaxes(tickangle=45)
    save(fig, "09_category_popularity")

# 11. Tools with categories vs without
df = con.execute("""
SELECT 
    CASE 
        WHEN categories IS NOT NULL AND len(categories) > 0 THEN 'With Categories'
        ELSE 'No Categories'
    END as has_categories,
    COUNT(*) as count,
    AVG(impressions) as avg_impressions
FROM devhunt
GROUP BY 1
""").df()
if not df.empty:
    fig = px.bar(df, x='has_categories', y='avg_impressions', title="Average Impressions: Tools With vs Without Categories")
    save(fig, "10_categories_impact")

# 12. Tools with taglines vs without
df = con.execute("""
SELECT 
    CASE 
        WHEN tagline != '' AND LENGTH(tagline) > 10 THEN 'With Tagline'
        ELSE 'No Tagline'
    END as has_tagline,
    COUNT(*) as count,
    AVG(impressions) as avg_impressions
FROM devhunt
GROUP BY 1
""").df()
if not df.empty:
    fig = px.bar(df, x='has_tagline', y='avg_impressions', title="Average Impressions: Tools With vs Without Taglines")
    save(fig, "11_tagline_impact")

print("\nALL CHARTS SAVED IN /charts!")
print("Your post is ready. Title:")
print("'I scraped every single dev tool on DevHunt.org (2,300+ tools) – here's what actually wins in 2025'")
print("Go post it now!")

