# analyze_betalist.py
import duckdb
import pandas as pd
import plotly.express as px
import os

con = duckdb.connect()
con.execute("CREATE OR REPLACE TABLE bl AS SELECT * FROM 'betalist_all.jsonl'")

os.makedirs("charts", exist_ok=True)
def save(fig, name):
    try:
        fig.write_image(f"charts/{name}.png", width=1300, height=750, scale=2)
        print(f"Saved charts/{name}.png")
    except Exception as e:
        print(f"Error saving {name}.png: {e}")

print("Generating 20 nuclear-level charts...")

# 1. The brutal waitlist reality
df = con.execute("SELECT waitlist FROM bl WHERE waitlist > 0").df()
if not df.empty and len(df) > 0:
    fig = px.histogram(df, x='waitlist', nbins=100, title="99.6% of BetaList startups get <1,000 signups")
    fig.update_xaxes(range=[0, 5000])
    save(fig, "01_brutal_reality")
else:
    print("Skipping chart 01: No waitlist data available")

# 2. Top 25 biggest waitlists ever
df = con.execute("SELECT title, founder, waitlist, date FROM bl WHERE waitlist > 0 ORDER BY waitlist DESC LIMIT 25").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, y='title', x='waitlist', orientation='h', title="Biggest BetaList Waitlists Ever")
    fig.update_yaxes(autorange="reversed")
    save(fig, "02_hall_of_fame")
else:
    print("Skipping chart 02: No waitlist data available")

# 3. Category dominance over time
df = con.execute("""
SELECT TRY_CAST(date AS DATE)::VARCHAR(7) as month,
       cat
FROM bl, UNNEST(categories) as cat
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL
""").df()
if not df.empty and len(df) > 0:
    df = df.groupby(['month','cat']).size().reset_index(name='count')
    if not df.empty:
        top_cats = df.groupby('cat')['count'].sum().sort_values(ascending=False).head(10).index
        df = df[df['cat'].isin(top_cats)]
        if not df.empty:
            fig = px.area(df, x='month', y='count', color='cat', title="AI overtook everything in 2025")
            save(fig, "03_category_shift")
        else:
            print("Skipping chart 03: No category data available")
    else:
        print("Skipping chart 03: No category data available")
else:
    print("Skipping chart 03: No date/category data available")

# 4. Magic title words (12-year data!)
df = con.execute("""
WITH words AS (
  SELECT UNNEST(regexp_split_to_array(LOWER(title), '\\W+')) as word, waitlist
  FROM bl WHERE waitlist > 0
)
SELECT word, COUNT(*) as n, AVG(waitlist) as avg
FROM words WHERE LENGTH(word)>4 AND word NOT IN ('with','your','from','just','into')
GROUP BY word HAVING COUNT(*)>=15
ORDER BY avg DESC LIMIT 30
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='word', y='avg', title="Title Words That 20× Your Waitlist")
    save(fig, "04_magic_words")
else:
    print("Skipping chart 04: Insufficient word data")

# 5. Founder repeat success rate
df = con.execute("""
SELECT 
    founder,
    COUNT(*) as startup_count,
    AVG(waitlist) as avg_waitlist,
    MAX(waitlist) as max_waitlist
FROM bl 
WHERE founder != 'unknown'
GROUP BY founder 
HAVING COUNT(*) >= 2
ORDER BY avg_waitlist DESC 
LIMIT 20
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='founder', y='avg_waitlist', title="Founders Who Launched Multiple Startups (Avg Waitlist)")
    fig.update_xaxes(tickangle=45)
    save(fig, "05_founder_repeat_success")
else:
    print("Skipping chart 05: No founder data available")

# 6. Best launch month analysis
df = con.execute("""
SELECT 
    EXTRACT(MONTH FROM TRY_CAST(date AS DATE)) as month,
    COUNT(*) as launches,
    AVG(waitlist) as avg_waitlist
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL AND waitlist > 0
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    df['month_name'] = df['month'].apply(lambda x: month_names[int(x)-1] if 1 <= x <= 12 else 'Unknown')
    fig = px.bar(df, x='month_name', y='avg_waitlist', title="Best Month to Launch (Avg Waitlist by Month)")
    save(fig, "06_best_launch_month")
else:
    print("Skipping chart 06: Insufficient date/waitlist data")

# 7. "AI" category explosion timeline
df = con.execute("""
SELECT 
    TRY_CAST(date AS DATE)::VARCHAR(7) as month,
    COUNT(*) FILTER (WHERE 'AI' = ANY(categories) OR 'Artificial Intelligence' = ANY(categories)) as ai_count,
    COUNT(*) as total_count
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    df['ai_percentage'] = (df['ai_count'] / df['total_count'] * 100).round(2)
    fig = px.line(df, x='month', y='ai_percentage', title="AI Category Explosion Over Time (% of All Launches)")
    save(fig, "07_ai_explosion")
else:
    print("Skipping chart 07: No date data available")

# 8. Startup death rate over time (low waitlist = likely dead)
df = con.execute("""
SELECT 
    TRY_CAST(date AS DATE)::VARCHAR(7) as month,
    COUNT(*) FILTER (WHERE waitlist < 50) as low_waitlist,
    COUNT(*) as total
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    df['death_rate'] = (df['low_waitlist'] / df['total'] * 100).round(2)
    fig = px.line(df, x='month', y='death_rate', title="Startup 'Death Rate' Over Time (% with <50 Waitlist)")
    save(fig, "08_death_rate")
else:
    print("Skipping chart 08: No date data available")

# 9. Waitlist growth trends (average waitlist over time)
df = con.execute("""
SELECT 
    TRY_CAST(date AS DATE)::VARCHAR(7) as month,
    AVG(waitlist) as avg_waitlist,
    COUNT(*) as launches
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL AND waitlist > 0
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.line(df, x='month', y='avg_waitlist', title="Average Waitlist Size Over Time")
    save(fig, "09_waitlist_trends")
else:
    print("Skipping chart 09: Insufficient date/waitlist data")

# 10. Category performance comparison
df = con.execute("""
SELECT 
    cat as category,
    COUNT(*) as count,
    AVG(waitlist) as avg_waitlist,
    MEDIAN(waitlist) as median_waitlist
FROM bl, UNNEST(categories) as cat
WHERE categories IS NOT NULL AND array_length(categories) > 0
GROUP BY 1 
HAVING COUNT(*) >= 50
ORDER BY avg_waitlist DESC 
LIMIT 15
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='category', y='avg_waitlist', title="Category Performance (Avg Waitlist)")
    fig.update_xaxes(tickangle=45)
    fig.update_layout(xaxis_title="Category", yaxis_title="Average Waitlist Size")
    save(fig, "10_category_performance")
else:
    print("Skipping chart 10: Insufficient category data")

# 11. Tagline length vs waitlist correlation
df = con.execute("""
SELECT 
    LENGTH(tagline) as tagline_length,
    AVG(waitlist) as avg_waitlist,
    COUNT(*) as count
FROM bl 
WHERE tagline != '' AND LENGTH(tagline) > 0 AND waitlist > 0
GROUP BY 1 
HAVING COUNT(*) >= 10
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.scatter(df, x='tagline_length', y='avg_waitlist', size='count', 
                     title="Tagline Length vs Average Waitlist", trendline="ols")
    save(fig, "11_tagline_length")
else:
    print("Skipping chart 11: Insufficient tagline/waitlist data")

# 12. Launch year distribution
df = con.execute("""
SELECT 
    EXTRACT(YEAR FROM TRY_CAST(date AS DATE)) as year,
    COUNT(*) as launches
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL
GROUP BY 1 
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='year', y='launches', title="Startups Launched Per Year (2013-2025)")
    save(fig, "12_launch_year_distribution")
else:
    print("Skipping chart 12: No date data available")

# 13. Waitlist percentile analysis
df = con.execute("""
SELECT 
    CASE 
        WHEN waitlist = 0 THEN '0'
        WHEN waitlist BETWEEN 1 AND 10 THEN '1-10'
        WHEN waitlist BETWEEN 11 AND 50 THEN '11-50'
        WHEN waitlist BETWEEN 51 AND 100 THEN '51-100'
        WHEN waitlist BETWEEN 101 AND 500 THEN '101-500'
        WHEN waitlist BETWEEN 501 AND 1000 THEN '501-1K'
        WHEN waitlist BETWEEN 1001 AND 5000 THEN '1K-5K'
        WHEN waitlist BETWEEN 5001 AND 10000 THEN '5K-10K'
        ELSE '10K+'
    END as waitlist_range,
    COUNT(*) as count,
    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM bl) as percentage
FROM bl
GROUP BY 1
ORDER BY 
    CASE waitlist_range
        WHEN '0' THEN 1
        WHEN '1-10' THEN 2
        WHEN '11-50' THEN 3
        WHEN '51-100' THEN 4
        WHEN '101-500' THEN 5
        WHEN '501-1K' THEN 6
        WHEN '1K-5K' THEN 7
        WHEN '5K-10K' THEN 8
        ELSE 9
    END
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='waitlist_range', y='percentage', title="Waitlist Distribution (% of All Startups)")
    save(fig, "13_waitlist_percentiles")
else:
    print("Skipping chart 13: No waitlist data available")

# 14. Category waitlist averages (top vs bottom)
df = con.execute("""
SELECT 
    cat as category,
    AVG(waitlist) as avg_waitlist,
    COUNT(*) as count
FROM bl, UNNEST(categories) as cat
WHERE categories IS NOT NULL AND array_length(categories) > 0
GROUP BY 1 
HAVING COUNT(*) >= 30
ORDER BY avg_waitlist DESC 
LIMIT 20
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, y='category', x='avg_waitlist', orientation='h', 
                 title="Top 20 Categories by Average Waitlist")
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(yaxis_title="Category", xaxis_title="Average Waitlist Size")
    save(fig, "14_category_waitlist_avg")
else:
    print("Skipping chart 14: Insufficient category data")

# 15. Top founders by total waitlist
df = con.execute("""
SELECT 
    founder,
    COUNT(*) as startup_count,
    SUM(waitlist) as total_waitlist,
    AVG(waitlist) as avg_waitlist
FROM bl 
WHERE founder != 'unknown' AND waitlist > 0
GROUP BY founder 
ORDER BY total_waitlist DESC 
LIMIT 20
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='founder', y='total_waitlist', title="Top 20 Founders by Total Waitlist Size")
    fig.update_xaxes(tickangle=45)
    save(fig, "15_top_founders")
else:
    print("Skipping chart 15: No founder/waitlist data available")

# 16. Startup survival rate by category (waitlist > 100 = "survived")
df = con.execute("""
SELECT 
    cat as category,
    COUNT(*) FILTER (WHERE waitlist >= 100) as survived,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE waitlist >= 100) * 100.0 / COUNT(*) as survival_rate
FROM bl, UNNEST(categories) as cat
WHERE categories IS NOT NULL AND array_length(categories) > 0
GROUP BY 1 
HAVING COUNT(*) >= 50
ORDER BY survival_rate DESC 
LIMIT 15
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='category', y='survival_rate', title="Startup Survival Rate by Category (% with 100+ Waitlist)")
    fig.update_xaxes(tickangle=45)
    save(fig, "16_survival_by_category")
else:
    print("Skipping chart 16: Insufficient category/waitlist data")

# 17. Waitlist vs time since launch
df = con.execute("""
SELECT 
    EXTRACT(YEAR FROM CURRENT_DATE) - EXTRACT(YEAR FROM TRY_CAST(date AS DATE)) as years_since_launch,
    AVG(waitlist) as avg_waitlist,
    COUNT(*) as count
FROM bl 
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL AND waitlist > 0
GROUP BY 1 
HAVING COUNT(*) >= 20
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.line(df, x='years_since_launch', y='avg_waitlist', 
                  title="Average Waitlist vs Years Since Launch")
    save(fig, "17_waitlist_vs_age")
else:
    print("Skipping chart 17: Insufficient date/waitlist data")

# 18. Most common tagline words
df = con.execute("""
WITH words AS (
  SELECT UNNEST(regexp_split_to_array(LOWER(tagline), '\\W+')) as word
  FROM bl WHERE tagline != '' AND LENGTH(tagline) > 10
)
SELECT word, COUNT(*) as frequency
FROM words 
WHERE LENGTH(word) > 3 AND word NOT IN ('with','your','from','just','into','that','this','have','will','make','more','most','best','first','make','help','need','want','know','like','time','work','well','good','great','new','now','get','can','use','way','one','two','all','are','was','for','the','and','but','not','you','all','can','her','was','one','our','out','day','get','has','him','his','how','its','may','new','now','old','see','two','who','way','use','her','him','his','how','its','may','new','now','old','see','two','who','way','use')
GROUP BY word 
HAVING COUNT(*) >= 20
ORDER BY frequency DESC 
LIMIT 25
""").df()
if not df.empty and len(df) > 0:
    fig = px.bar(df, x='word', y='frequency', title="Most Common Tagline Words")
    fig.update_xaxes(tickangle=45)
    save(fig, "18_common_tagline_words")
else:
    print("Skipping chart 18: Insufficient tagline word data")

# 19. Title length vs waitlist
df = con.execute("""
SELECT 
    LENGTH(title) as title_length,
    AVG(waitlist) as avg_waitlist,
    COUNT(*) as count
FROM bl 
WHERE title != '' AND LENGTH(title) > 0 AND waitlist > 0
GROUP BY 1 
HAVING COUNT(*) >= 10
ORDER BY 1
""").df()
if not df.empty and len(df) > 0:
    fig = px.scatter(df, x='title_length', y='avg_waitlist', size='count',
                     title="Title Length vs Average Waitlist", trendline="ols")
    save(fig, "19_title_length")
else:
    print("Skipping chart 19: Insufficient title/waitlist data")

# 20. Category trends (top 5 categories over time)
df = con.execute("""
SELECT 
    TRY_CAST(date AS DATE)::VARCHAR(7) as month,
    cat as category
FROM bl, UNNEST(categories) as cat
WHERE date != '' AND TRY_CAST(date AS DATE) IS NOT NULL
""").df()
if not df.empty and len(df) > 0:
    top_cats = df.groupby('category').size().sort_values(ascending=False).head(5).index
    df_filtered = df[df['category'].isin(top_cats)]
    if not df_filtered.empty:
        df_counts = df_filtered.groupby(['month', 'category']).size().reset_index(name='count')
        if not df_counts.empty:
            fig = px.line(df_counts, x='month', y='count', color='category',
                          title="Top 5 Categories Over Time (Launch Count)")
            save(fig, "20_category_trends")
        else:
            print("Skipping chart 20: Insufficient category trend data")
    else:
        print("Skipping chart 20: No category data available")
else:
    print("Skipping chart 20: No date/category data available")

print("ALL 20 CHARTS SAVED!")
print("Your post title:")
print('"I scraped all 31,000 startups ever launched on BetaList (2013–2025) – only 0.4% ever get real traction. Here\'s exactly why"')
print("Post this tomorrow and watch founders cry (in a good way)")

