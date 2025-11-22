"""
Scrape ~200 days of Hacker News activity directly from news.ycombinator.com
by walking historical front pages and fetching every story discussion thread.
"""

import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_NEWS_URL = "https://news.ycombinator.com"
FRONT_ENDPOINT = f"{BASE_NEWS_URL}/front"
ITEM_ENDPOINT = f"{BASE_NEWS_URL}/item"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36"

DAYS_OF_HISTORY = 200
FRONT_DELAY_SECONDS = 0.5
THREAD_WORKERS = 16
REQUEST_TIMEOUT = 15
RETRY_LIMIT = 3
BATCH_SIZE = 10000
FRONT_MAX_RETRIES = 5

thread_local = threading.local()


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=RETRY_LIMIT,
        read=RETRY_LIMIT,
        connect=RETRY_LIMIT,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=THREAD_WORKERS * 2,
        pool_maxsize=THREAD_WORKERS * 4,
    )
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    try:
        session.get(BASE_NEWS_URL, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        pass
    return session


def get_thread_session() -> requests.Session:
    session = getattr(thread_local, "session", None)
    if session is None:
        session = build_session()
        setattr(thread_local, "session", session)
    return session


def parse_iso_timestamp(value: str) -> int:
    cleaned = value
    if cleaned.endswith("Z"):
        cleaned = cleaned.replace("Z", "+00:00")
    if "+" not in cleaned and "-" not in cleaned[10:]:
        cleaned += "+00:00"
    dt = datetime.fromisoformat(cleaned)
    return int(dt.timestamp())


def parse_age(span: Optional[BeautifulSoup]) -> int:
    if span and span.has_attr("title"):
        try:
            return parse_iso_timestamp(span["title"])
        except ValueError:
            pass
    return int(time.time())


def parse_comment_count(text: str) -> int:
    stripped = text.strip()
    if not stripped or stripped == "discuss":
        return 0
    for token in stripped.split():
        if token.isdigit():
            return int(token)
    return 0


def normalize_story_url(url: str) -> str:
    return urljoin(f"{BASE_NEWS_URL}/", url)


def daterange(end_date: datetime, days_back: int) -> Iterable[datetime]:
    for offset in range(days_back):
        yield end_date - timedelta(days=offset)


def fetch_front_page(session: requests.Session, day: datetime, page: int) -> Optional[str]:
    params = {"day": day.strftime("%Y-%m-%d")}
    if page > 1:
        params["p"] = page
    for attempt in range(1, FRONT_MAX_RETRIES + 1):
        try:
            response = session.get(FRONT_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.text
            if response.status_code == 403:
                wait = FRONT_DELAY_SECONDS * attempt * 4
                print(f"Front page blocked (403) for {params}, sleeping {wait:.1f}s before retry.")
                time.sleep(wait)
                continue
            print(f"Front page fetch failed ({response.status_code}) for {params}")
            break
        except requests.RequestException as exc:
            wait = FRONT_DELAY_SECONDS * attempt * 2
            print(f"Front page fetch exception for {params}: {exc}. Retrying in {wait:.1f}s")
            time.sleep(wait)
    return None


def parse_front_page(html: str, day: datetime) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    stories: List[Dict] = []
    for row in soup.select("tr.athing"):
        story_id = row.get("id")
        if not story_id:
            continue
        title_link = row.select_one(".titleline > a")
        if not title_link:
            continue
        subtext = row.find_next_sibling("tr")
        score = 0
        author = None
        timestamp = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
        descendants = 0
        if subtext:
            score_span = subtext.select_one("span.score")
            if score_span:
                parts = score_span.text.split()
                if parts:
                    try:
                        score = int(parts[0])
                    except ValueError:
                        score = 0
            author_link = subtext.select_one("a.hnuser")
            if author_link:
                author = author_link.text.strip()
            age_span = subtext.select_one("span.age")
            timestamp = parse_age(age_span)
            for link in subtext.select("a"):
                href = link.get("href", "")
                if href.startswith("item?id="):
                    descendants = parse_comment_count(link.text)
        stories.append(
            {
                "id": int(story_id),
                "type": "story",
                "title": title_link.get_text(strip=True),
                "url": normalize_story_url(title_link.get("href", "")),
                "by": author,
                "time": timestamp,
                "score": score,
                "text": "",
                "descendants": descendants,
                "kids": [],
            }
        )
    return stories


def extract_story_text(soup: BeautifulSoup) -> str:
    block = soup.select_one("table.fatitem span.commtext")
    if block:
        return block.decode_contents().strip()
    return ""


def parse_comment_tree(soup: BeautifulSoup, story_id: int) -> Tuple[List[Dict], DefaultDict[int, List[int]]]:
    comments: List[Dict] = []
    kids_map: DefaultDict[int, List[int]] = defaultdict(list)
    stack: List[int] = []

    for row in soup.select("tr.comtr"):
        comment_id = row.get("id")
        if not comment_id:
            continue
        try:
            numeric_id = int(comment_id)
        except ValueError:
            continue

        indent_img = row.select_one("td.ind img")
        depth = 0
        if indent_img and indent_img.has_attr("width"):
            try:
                depth = int(indent_img["width"]) // 40
            except ValueError:
                depth = 0

        while len(stack) > depth:
            stack.pop()
        parent_id = story_id if not stack else stack[-1]
        stack.append(numeric_id)

        default_td = row.select_one("td.default")
        if not default_td:
            continue
        comm_text = default_td.select_one("span.commtext")
        text_html = comm_text.decode_contents().strip() if comm_text else ""
        deleted = text_html == "[deleted]"

        user_link = default_td.select_one("a.hnuser")
        author = user_link.text.strip() if user_link else None
        age_span = default_td.select_one("span.age")
        timestamp = parse_age(age_span)
        score_span = default_td.select_one("span.score")
        score = 0
        if score_span:
            parts = score_span.text.split()
            if parts:
                try:
                    score = int(parts[0])
                except ValueError:
                    score = 0

        comment_record = {
            "id": numeric_id,
            "type": "comment",
            "time": timestamp,
            "by": author,
            "score": score,
            "title": "",
            "url": "",
            "text": "" if deleted else text_html,
            "descendants": 0,
            "kids": [],
            "parent": parent_id,
            "deleted": deleted,
        }
        comments.append(comment_record)
        kids_map[parent_id].append(numeric_id)

    for comment in comments:
        comment["kids"] = kids_map.get(comment["id"], [])
        comment["descendants"] = len(comment["kids"])

    return comments, kids_map


def fetch_story_thread(meta: Dict) -> Tuple[Dict, List[Dict]]:
    session = get_thread_session()
    item_url = f"{ITEM_ENDPOINT}?id={meta['id']}"
    for attempt in range(RETRY_LIMIT):
        try:
            response = session.get(item_url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                time.sleep(0.5 * (attempt + 1))
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            story_text = extract_story_text(soup)
            comments, kids_map = parse_comment_tree(soup, meta["id"])
            story_record = dict(meta)
            story_record["text"] = story_text
            story_record["descendants"] = len(comments)
            story_record["kids"] = kids_map.get(meta["id"], [])
            return story_record, comments
        except requests.RequestException as exc:
            print(f"Thread fetch error for story {meta['id']} (attempt {attempt + 1}): {exc}")
            time.sleep(0.5 * (attempt + 1))
    print(f"Thread fetch failed for story {meta['id']} after retries.")
    story_record = dict(meta)
    story_record["text"] = ""
    story_record["descendants"] = 0
    story_record["kids"] = []
    return story_record, []


def flush_batch(filename: str, payload: List[Dict]) -> None:
    with open(filename, "w", encoding="utf-8") as handle:
        for item in payload:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def main() -> None:
    front_session = build_session()
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=DAYS_OF_HISTORY - 1)
    total_days = (end_date - start_date).days + 1

    batch: List[Dict] = []
    batch_num = 1
    saved_items = 0

    for index, day in enumerate(daterange(end_date, total_days), start=1):
        current_day = day
        day_label = current_day.strftime("%Y-%m-%d")
        page = 1
        day_stories: List[Dict] = []

        while True:
            html = fetch_front_page(front_session, current_day, page)
            if not html:
                break
            page_stories = parse_front_page(html, current_day)
            if not page_stories:
                break
            day_stories.extend(page_stories)
            soup = BeautifulSoup(html, "html.parser")
            more_link = soup.select_one("a.morelink")
            if more_link:
                page += 1
                time.sleep(FRONT_DELAY_SECONDS)
            else:
                break

        if not day_stories:
            print(f"Day {index}/{total_days} ({day_label}): no stories found.")
            continue

        story_ids = [story["id"] for story in day_stories]
        print(
            f"Day {index}/{total_days} ({day_label}): "
            f"{len(day_stories)} stories (IDs {story_ids[0]}–{story_ids[-1]}) across {page} page(s)."
        )

        with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
            for story_record, comments in executor.map(fetch_story_thread, day_stories):
                for item in [story_record, *comments]:
                    batch.append(item)
                    if len(batch) >= BATCH_SIZE:
                        filename = f"hn_html_part{batch_num}.jsonl"
                        flush_batch(filename, batch)
                        min_id = min(entry["id"] for entry in batch)
                        max_id = max(entry["id"] for entry in batch)
                        print(
                            f"Saved batch {batch_num}: {len(batch)} items "
                            f"(IDs {min_id}–{max_id})"
                        )
                        saved_items += len(batch)
                        batch = []
                        batch_num += 1
        time.sleep(FRONT_DELAY_SECONDS)

    if batch:
        filename = f"hn_html_part{batch_num}.jsonl"
        flush_batch(filename, batch)
        min_id = min(entry["id"] for entry in batch)
        max_id = max(entry["id"] for entry in batch)
        print(
            f"Final batch {batch_num}: {len(batch)} items "
            f"(IDs {min_id}–{max_id})"
        )
        saved_items += len(batch)

    print(f"DOWNLOAD COMPLETE! Total items saved: {saved_items:,}")


if __name__ == "__main__":
    main()

