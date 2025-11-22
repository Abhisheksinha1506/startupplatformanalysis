# HTML Scraper Plan

## Goal
Replace the Firebase API dependency with a pure HTML crawler that:

- Walks ~200 days of stories via `https://news.ycombinator.com/front?day=YYYY-MM-DD`.
- Downloads each story’s discussion thread (`item?id=...`) to capture comments.
- Emits JSON lines compatible with the existing analysis pipeline (story/comment types, ids, timestamps, scores, descendants, kids).

## Pagination Strategy

1. Determine `end_date = today()` and `start_date = end_date - 200 days`.
2. Iterate day-by-day (reverse chronological) constructing `front?day=YYYY-MM-DD`.
3. Parse each front page with BeautifulSoup:
   - Each story is represented by two `<tr>` rows: `tr.athing` (metadata) + following `tr` (subtext).
   - Extract: `id`, title, URL, score, author, time (from `span.age`), comment count (`a[href*='item?id=']`), rank.
4. For robustness, respect `next` pagination buttons when present (some days have multiple pages). Continue until no `more` link remains.

## Queueing Item Pages

- Maintain a queue of story IDs discovered.
- Use a thread/concurrency pool (e.g., `ThreadPoolExecutor(max_workers=16)`) to fetch each `https://news.ycombinator.com/item?id={id}`.
- Parse the thread HTML to capture:
  - Story text (`span.comment`) for “Ask/Show” self-posts.
  - Comment tree: each `tr.comtr` has `id`, `data-parent`, `data-score` (if visible), user handle, timestamp, text, dead/deleted marker, and indentation depth (`img[src='s.gif'].width`).

## Comment Representation

- Use story/comment objects mirroring former schema:
  - `type`: `"story"` or `"comment"`.
  - `time`: convert relative timestamps (e.g., “3 hours ago”) via `datetime.utcnow() - parsed_delta`.
  - `score`: for comments use `span.score`, for stories reuse front-page score.
  - `kids`: collect child IDs based on indentation hierarchy; for flattened processing we can store the list even if we also emit every comment record individually.
  - `descendants`: computed as total comments for the story.

## Output Batching

- Accumulate parsed objects (story record plus all comment records) and write `.jsonl` batches every N items (e.g., 10k) to stay consistent with earlier workflow.
- Log “page” progress messages:
  - Dates processed (e.g., “Day 37/200: 2025-05-05 (2 pages)”).
  - Story ID ranges included per batch file.

## Error Handling

- Retry front/item requests with exponential backoff (HTTP 5xx or connection failures).
- Skip and log placeholder entries for threads that return non-200.
- Detect HTML structure drift (missing selectors) and warn with day/story context.

## Performance Considerations

- Total stories ≈ 30/day ⇒ ~6k front entries. Parallelizing thread fetches keeps runtime manageable (~3–4 hours).
- Respect polite scraping: include `time.sleep(0.5)` after each front-page request and limit concurrent item fetches.

