# Startup Platforms Analysis

A comprehensive collection of data analysis projects scraping and analyzing various startup platforms and developer communities. Each project includes complete scraping scripts, data analysis, and publication-ready visualizations.

## 📊 Analysis Projects

### [BetaList Analysis](./betalist-analysis/)

**Platform:** BetaList.com (2013–2025)  
**Dataset:** ~31,000 startups  
**Key Insights:**
- 92% of startups disappear within 12 months
- Average waitlist size in 2025 = 184 signups
- Only 127 startups ever crossed 10,000 signups
- "AI" overtook "SaaS" as #1 category in March 2025

**Charts Generated:** 19+ visualizations including waitlist distributions, category trends, magic words analysis, and founder success patterns.

[View Full Analysis →](./betalist-analysis/)

---

### [DailyPings Analysis](./dailypings-analysis/)

**Platform:** DailyPings.com (2024–2025)  
**Dataset:** ~3,000 pings  
**Key Insights:**
- Growth trends over time
- Best days and hours to post
- Magic words that drive engagement
- Top authors and most discussed content

**Charts Generated:** 12+ visualizations including growth over time, best posting times, upvote distributions, and engagement correlations.

[View Full Analysis →](./dailypings-analysis/)

---

### [DevHunt Analysis](./devhunt-analysis/)

**Platform:** DevHunt.org (2024–2025)  
**Dataset:** ~4,200 dev tool launches  
**Key Insights:**
- Category performance and trends
- Best days to launch
- Magic words in winning titles
- Top makers and engagement patterns

**Charts Generated:** 11+ visualizations including top tools by impressions, category impact, tagline analysis, and title length correlations.

[View Full Analysis →](./devhunt-analysis/)

---

### [Hacker News 200-Day Analysis](./hn-200-days-analysis/)

**Platform:** Hacker News (Last ~200 days)  
**Dataset:** Stories and comments from ~200 days  
**Key Insights:**
- Daily activity patterns
- Best posting hours
- Top Show HN submissions
- Most discussed threads

**Charts Generated:** 5+ visualizations including daily activity, best posting hours, top Show HNs, magic words, and discussion patterns.

[View Full Analysis →](./hn-200-days-analysis/)

---

### [ListYourTool Analysis](./listyourtool-analysis/)

**Platform:** ListYourTool.com (2024–2025)  
**Dataset:** ~8,200 AI tools  
**Key Insights:**
- Monthly submission explosion
- Category saturation analysis
- Pricing vs engagement correlation
- Maker repeat success patterns

**Charts Generated:** 16+ visualizations including monthly trends, top tools, category saturation, pricing analysis, and magic words.

[View Full Analysis →](./listyourtool-analysis/)

---

## 🚀 Quick Start

Each analysis folder contains:
- **Scraping Script**: Python script to collect data from the platform
- **Analysis Script**: Generates charts and insights from the scraped data
- **README**: Detailed instructions and insights specific to that platform
- **Charts Folder**: Publication-ready PNG visualizations

### Common Setup (applies to most projects)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install duckdb pandas plotly kaleido requests beautifulsoup4
```

### Running an Analysis

1. Navigate to the desired analysis folder
2. Follow the README instructions in that folder
3. Run the scraping script to collect data
4. Run the analysis script to generate charts
5. Review the generated visualizations in the `charts/` folder

## 📈 Project Overview

This repository contains comprehensive analyses of major startup and developer platforms:

- **Total Platforms Analyzed:** 5
- **Total Data Points:** 50,000+ startups, tools, and posts
- **Total Visualizations:** 60+ publication-ready charts
- **Time Period Covered:** 2013–2025 (varies by platform)

## 🎯 Use Cases

- **Founders & Makers:** Understand what works on different platforms
- **Data Analysts:** Access clean datasets and analysis scripts
- **Content Creators:** Use insights and charts for blog posts and social media
- **Researchers:** Study startup trends and platform dynamics

## 📝 Notes

- All analyses are performed locally with no API keys required
- Data is stored in JSONL format for easy processing
- Charts are generated using Plotly and saved as high-resolution PNGs
- All scrapers implement polite scraping practices with rate limiting
- Scripts include error handling and incremental saves to prevent data loss

---

**Navigate to any folder above to see the complete analysis, setup instructions, and generated visualizations.**

