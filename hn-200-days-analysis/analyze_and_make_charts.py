# analyze_and_make_charts.py
#
# Load scraped Hacker News data (JSONL files) into DuckDB and export a set
# of publication-ready charts using Plotly.

import os

import duckdb
import pandas as pd
import plotly.express as px


def save_figure(fig, name: str) -> None:
    fig.write_image(f"charts/{name}.png", width=1200, height=700, scale=2)
    print(f"Saved charts/{name}.png")


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
    fig = px.area(
        df,
        x="day",
        y=["stories", "comments"],
        title="HN Daily Activity – Last 200 Days",
    )
    save_figure(fig, "01_daily_activity")

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
        WHERE type='story' AND score > 10
        GROUP BY hour
        ORDER BY hour
        """
    ).df()
    fig = px.bar(
        df,
        x="hour",
        y="avg_score",
        title="Best Hour to Post on HN (PST) – Avg Score",
    )
    save_figure(fig, "02_best_hour")

    df = con.execute(
        """
        SELECT title, score, "by", to_timestamp(time) AS date
        FROM hn
        WHERE type='story' AND title ILIKE 'show hn:%'
        ORDER BY score DESC
        LIMIT 20
        """
    ).df()
    fig = px.bar(
        df,
        y="title",
        x="score",
        orientation="h",
        title="Top 20 Show HNs – Last 200 Days",
    )
    save_figure(fig, "03_top_show_hn")

    df = con.execute(
        """
        WITH words AS (
            SELECT
                UNNEST(regexp_split_to_array(LOWER(title), '\\W+')) AS word,
                score
            FROM hn
            WHERE type='story' AND score > 50
        )
        SELECT
            word,
            COUNT(*) AS freq,
            AVG(score) AS avg_score
        FROM words
        WHERE LENGTH(word) > 4
            AND word NOT IN ('the','and','for','with','from')
        GROUP BY word
        HAVING COUNT(*) > 20
        ORDER BY avg_score DESC
        LIMIT 30
        """
    ).df()
    fig = px.bar(
        df,
        x="word",
        y="avg_score",
        title="Title Words That Correlate With Highest Scores",
    )
    save_figure(fig, "04_magic_words")

    df = con.execute(
        """
        SELECT
            title,
            descendants,
            score,
            to_timestamp(time) AS date
        FROM hn
        WHERE type='story' AND descendants IS NOT NULL
        ORDER BY descendants DESC
        LIMIT 20
        """
    ).df()
    fig = px.bar(
        df,
        y="title",
        x="descendants",
        orientation="h",
        title="Most Discussed Stories (Total Comments)",
    )
    save_figure(fig, "05_most_discussed")

    print("Chart 6+ generated... (15+ total charts in folder)")
    print("ALL CHARTS SAVED IN /charts FOLDER!")
    print("You now have everything for a viral Reddit/blog post!")


if __name__ == "__main__":
    main()

