# analyze_and_make_charts.py
#
# Load scraped Hacker News data (JSONL files) into DuckDB and export a set
# of publication-ready charts using Plotly.

import os

import duckdb
import pandas as pd
import plotly.express as px


def save_figure(fig, name: str) -> None:
    try:
        fig.write_image(f"charts/{name}.png", width=1200, height=700, scale=2)
        print(f"Saved charts/{name}.png")
    except Exception as e:
        print(f"Error saving {name}.png: {e}")


def main() -> None:
    os.makedirs("charts", exist_ok=True)

    con = duckdb.connect()
    print("Loading all data (this takes 10-30 seconds)...")
    # Load JSONL files with union_by_name to handle schema differences
    con.execute("""
        CREATE OR REPLACE TABLE hn AS 
        SELECT * FROM read_json_auto('*.jsonl', union_by_name=true, ignore_errors=true)
    """)

    print("Data loaded! Generating charts...")

    df = con.execute(
        """
        SELECT
            DATE_TRUNC('day', to_timestamp(time))::DATE AS day,
            COUNT(*) FILTER (WHERE type='story') AS stories,
            COUNT(*) FILTER (
                WHERE type='comment'
            ) AS comments
        FROM hn
        WHERE time IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.area(
            df,
            x="day",
            y=["stories", "comments"],
            title="HN Daily Activity – Last 200 Days",
        )
        save_figure(fig, "01_daily_activity")
    else:
        print("Skipping chart 01: No time data available")

    df = con.execute(
        """
        SELECT
            EXTRACT(HOUR FROM
                to_timestamp(time)
                AT TIME ZONE 'UTC'
                AT TIME ZONE 'America/Los_Angeles'
            ) AS hour,
            COUNT(*) AS n,
            AVG(score) AS avg_score
        FROM hn
        WHERE type='story' AND score > 10 AND time IS NOT NULL
        GROUP BY hour
        HAVING COUNT(*) >= 5
        ORDER BY hour
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.bar(
            df,
            x="hour",
            y="avg_score",
            title="Best Hour to Post on HN (PST) – Avg Score",
        )
        save_figure(fig, "02_best_hour")
    else:
        print("Skipping chart 02: Insufficient time/score data")

    df = con.execute(
        """
        SELECT title, score, "by", to_timestamp(time) AS date
        FROM hn
        WHERE type='story' AND title ILIKE 'show hn:%' AND score IS NOT NULL
        ORDER BY score DESC
        LIMIT 20
        """
    ).df()
    if not df.empty and len(df) > 0:
        # Truncate long titles for better display
        df['title_short'] = df['title'].apply(lambda x: x[:60] + '...' if len(str(x)) > 60 else x)
        fig = px.bar(
            df,
            y="title_short",
            x="score",
            orientation="h",
            title="Top 20 Show HNs – Last 200 Days",
        )
        fig.update_yaxes(autorange="reversed")
        save_figure(fig, "03_top_show_hn")
    else:
        print("Skipping chart 03: No Show HN data available")

    df = con.execute(
        """
        WITH words AS (
            SELECT
                UNNEST(regexp_split_to_array(LOWER(title), '\\W+')) AS word,
                score
            FROM hn
            WHERE type='story' AND score > 50 AND title IS NOT NULL
        )
        SELECT
            word,
            COUNT(*) AS freq,
            AVG(score) AS avg_score
        FROM words
        WHERE LENGTH(word) > 4
            AND word NOT IN ('the','and','for','with','from','this','that','have','will','make','more','most','best','first')
        GROUP BY word
        HAVING COUNT(*) > 20
        ORDER BY avg_score DESC
        LIMIT 30
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.bar(
            df,
            x="word",
            y="avg_score",
            title="Title Words That Correlate With Highest Scores",
        )
        fig.update_xaxes(tickangle=45)
        save_figure(fig, "04_magic_words")
    else:
        print("Skipping chart 04: Insufficient word data")

    df = con.execute(
        """
        SELECT
            title,
            descendants,
            score,
            to_timestamp(time) AS date
        FROM hn
        WHERE type='story' AND descendants IS NOT NULL AND descendants > 0
        ORDER BY descendants DESC
        LIMIT 20
        """
    ).df()
    if not df.empty and len(df) > 0:
        # Truncate long titles for better display
        df['title_short'] = df['title'].apply(lambda x: x[:60] + '...' if len(str(x)) > 60 else x)
        fig = px.bar(
            df,
            y="title_short",
            x="descendants",
            orientation="h",
            title="Most Discussed Stories (Total Comments)",
        )
        fig.update_yaxes(autorange="reversed")
        save_figure(fig, "05_most_discussed")
    else:
        print("Skipping chart 05: No discussion data available")

    # 6. Score distribution
    df = con.execute(
        """
        SELECT
            CASE
                WHEN score = 0 THEN '0'
                WHEN score BETWEEN 1 AND 10 THEN '1-10'
                WHEN score BETWEEN 11 AND 50 THEN '11-50'
                WHEN score BETWEEN 51 AND 100 THEN '51-100'
                WHEN score BETWEEN 101 AND 500 THEN '101-500'
                ELSE '500+'
            END as score_range,
            COUNT(*) as count
        FROM hn
        WHERE type='story' AND score IS NOT NULL
        GROUP BY 1
        ORDER BY 
            CASE score_range
                WHEN '0' THEN 1
                WHEN '1-10' THEN 2
                WHEN '11-50' THEN 3
                WHEN '51-100' THEN 4
                WHEN '101-500' THEN 5
                ELSE 6
            END
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.bar(df, x='score_range', y='count', title="Story Score Distribution on Hacker News")
        save_figure(fig, "06_score_distribution")
    else:
        print("Skipping chart 06: No score data available")

    # 7. Top domains
    df = con.execute(
        """
        SELECT
            CASE
                WHEN url LIKE '%github.com%' THEN 'github.com'
                WHEN url LIKE '%youtube.com%' OR url LIKE '%youtu.be%' THEN 'youtube.com'
                WHEN url LIKE '%medium.com%' THEN 'medium.com'
                WHEN url LIKE '%arxiv.org%' THEN 'arxiv.org'
                WHEN url LIKE '%techcrunch.com%' THEN 'techcrunch.com'
                WHEN url IS NULL OR url = '' THEN 'self-post'
                ELSE 'other'
            END as domain,
            COUNT(*) as stories,
            AVG(score) as avg_score
        FROM hn
        WHERE type='story'
        GROUP BY 1
        ORDER BY stories DESC
        LIMIT 10
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.bar(df, x='domain', y='stories', title="Top 10 Domains by Story Count")
        fig.update_xaxes(tickangle=45)
        save_figure(fig, "07_top_domains")
    else:
        print("Skipping chart 07: No domain data available")

    # 8. Comments per story distribution
    df = con.execute(
        """
        SELECT
            CASE
                WHEN descendants = 0 OR descendants IS NULL THEN '0'
                WHEN descendants BETWEEN 1 AND 10 THEN '1-10'
                WHEN descendants BETWEEN 11 AND 50 THEN '11-50'
                WHEN descendants BETWEEN 51 AND 100 THEN '51-100'
                WHEN descendants BETWEEN 101 AND 500 THEN '101-500'
                ELSE '500+'
            END as comment_range,
            COUNT(*) as count
        FROM hn
        WHERE type='story' AND descendants IS NOT NULL
        GROUP BY 1
        ORDER BY 
            CASE comment_range
                WHEN '0' THEN 1
                WHEN '1-10' THEN 2
                WHEN '11-50' THEN 3
                WHEN '51-100' THEN 4
                WHEN '101-500' THEN 5
                ELSE 6
            END
        """
    ).df()
    if not df.empty and len(df) > 0:
        fig = px.bar(df, x='comment_range', y='count', title="Comments per Story Distribution")
        save_figure(fig, "08_comments_distribution")
    else:
        print("Skipping chart 08: No comment data available")

    # 9. Score vs Comments correlation
    df = con.execute(
        """
        SELECT score, descendants as comments
        FROM hn
        WHERE type='story' AND score > 0 AND descendants > 0
        LIMIT 1000
        """
    ).df()
    if not df.empty and len(df) > 10:
        fig = px.scatter(df, x='score', y='comments', title="Score vs Comments Correlation", 
                        trendline="ols", labels={'score': 'Story Score', 'comments': 'Number of Comments'})
        save_figure(fig, "09_score_vs_comments")

    # 10. Weekly activity pattern
    df = con.execute(
        """
        SELECT
            EXTRACT(DOW FROM to_timestamp(time) AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles') as day_of_week,
            COUNT(*) FILTER (WHERE type='story') as stories,
            AVG(score) FILTER (WHERE type='story' AND score > 0) as avg_score
        FROM hn
        WHERE time IS NOT NULL AND type='story'
        GROUP BY 1
        ORDER BY 1
        """
    ).df()
    if not df.empty and len(df) > 0:
        day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        df['day_name'] = df['day_of_week'].apply(lambda x: day_names[int(x)] if 0 <= x < 7 else 'Unknown')
        fig = px.bar(df, x='day_name', y='avg_score', title="Average Story Score by Day of Week")
        save_figure(fig, "10_best_day_of_week")
    else:
        print("Skipping chart 10: No time/score data available")

    print("ALL CHARTS SAVED IN /charts FOLDER!")
    print("You now have everything for a viral Reddit/blog post!")


if __name__ == "__main__":
    main()

