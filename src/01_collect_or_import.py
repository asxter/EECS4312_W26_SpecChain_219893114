"""imports or reads your raw dataset; if you scraped, include scraper here"""
#!/usr/bin/env python3
"""
Collect Google Play reviews for the assigned app and save them to data/reviews_raw.jsonl.

App used here:
    MindDoc / Moodpath
    https://play.google.com/store/apps/details?id=de.moodpath.android&hl=en_CA

Output:
    data/reviews_raw.jsonl          – one JSON object per line, each representing a single review
    data/dataset_metadata.json      – summary info about the collection run (app details, counts, notes)

Install first:
    pip install google-play-scraper

Run:
    python src/01_collect_or_import.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# google-play-scraper is a third-party library that wraps the (unofficial)
# Google Play Store internal API to pull app metadata and user reviews.
# Sort  – enum for sort order (NEWEST, MOST_RELEVANT)
# reviews – function that fetches a batch of reviews
# app    – function that fetches app-level metadata (title, rating, installs, etc.)
from google_play_scraper import Sort, reviews, app


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Unique package identifier for MindDoc (formerly Moodpath) on Google Play.
APP_ID = "de.moodpath.android"

# Direct Play Store URL – stored in every review record for traceability.
APP_URL = "https://play.google.com/store/apps/details?id=de.moodpath.android&hl=en_CA"

# How many reviews we want to collect.  The course project asks for roughly
# 1,000–5,000.  The scraper will stop early if Google Play runs out of results.
TARGET_REVIEW_COUNT = 3000

# ---------------------------------------------------------------------------
# FILE / DIRECTORY PATHS
# ---------------------------------------------------------------------------

# Resolve the project root by going two levels up from this script's location
# (i.e. src/01_collect_or_import.py → project_root/).
ROOT_DIR = Path(__file__).resolve().parent.parent

# All data files live under <project_root>/data/
DATA_DIR = ROOT_DIR / "data"

# Output file for the raw reviews – one JSON object per line (JSONL format).
RAW_OUTPUT_PATH = DATA_DIR / "reviews_raw.jsonl"

# Output file for high-level metadata about the scraping run.
METADATA_PATH = DATA_DIR / "dataset_metadata.json"


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def ensure_data_dir() -> None:
    """Create the data/ directory (and any parents) if it doesn't already exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def safe_get_app_info(app_id: str) -> Dict[str, Any]:
    """
    Try to fetch app metadata (title, rating, install count, etc.) from Google Play.

    If the call fails for any reason (network error, app delisted, etc.) we
    return a dictionary with sensible defaults so the rest of the pipeline can
    continue without crashing.
    """
    try:
        info = app(app_id, lang="en", country="ca")
        return info
    except Exception as exc:
        print(f"[WARN] Could not fetch app metadata: {exc}")
        # Fallback dict – ensures downstream code that reads these keys won't break.
        return {
            "appId": app_id,
            "title": "Unknown",
            "installs": None,
            "ratings": None,
            "reviews": None,
            "score": None,
            "url": APP_URL,
        }


def normalize_review(raw_review: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Transform one raw review dictionary (as returned by google-play-scraper)
    into a clean, consistently-keyed record suitable for our JSONL file.

    Parameters
    ----------
    raw_review : dict
        A single review object straight from the scraper.  Key names and value
        types vary depending on library version; we cherry-pick what we need.
    index : int
        A running counter used to generate a fallback review ID if the scraper
        doesn't provide one.

    Returns
    -------
    dict
        A normalised record with these fields:
        - review_id            : unique ID from Google, or a generated one
        - app_id / app_url     : identifies which app was reviewed
        - user_name            : reviewer's display name
        - score                : star rating (1–5)
        - thumbs_up_count      : how many other users found the review helpful
        - review_created_version : app version the reviewer was using
        - at                   : ISO-8601 timestamp of when the review was posted
        - reply_content        : developer's reply text (if any)
        - replied_at           : ISO-8601 timestamp of the developer reply (if any)
        - content              : the actual review text
    """
    user_name = raw_review.get("userName")
    review_text = raw_review.get("content")
    review_id = raw_review.get("reviewId")

    return {
        # Use the Google-assigned review ID when available; otherwise generate
        # a zero-padded ID like "generated_000001" so every record has one.
        "review_id": review_id if review_id else f"generated_{index:06d}",
        "app_id": APP_ID,
        "app_url": APP_URL,
        "user_name": user_name,
        "score": raw_review.get("score"),
        "thumbs_up_count": raw_review.get("thumbsUpCount"),
        "review_created_version": raw_review.get("reviewCreatedVersion"),
        # Convert datetime objects to ISO-8601 strings for JSON serialisation.
        "at": raw_review.get("at").isoformat() if raw_review.get("at") else None,
        "reply_content": raw_review.get("replyContent"),
        "replied_at": raw_review.get("repliedAt").isoformat() if raw_review.get("repliedAt") else None,
        "content": review_text,
    }


# ---------------------------------------------------------------------------
# CORE SCRAPING LOGIC
# ---------------------------------------------------------------------------

def fetch_reviews(app_id: str, target_count: int) -> List[Dict[str, Any]]:
    """
    Fetch reviews in successive batches until we have *target_count* unique
    reviews or Google Play stops returning results.

    The google-play-scraper `reviews()` function returns at most ~200 reviews
    per call.  It also returns a *continuation_token* that must be passed back
    into the next call to get the next page of results (like a cursor).

    De-duplication is handled via a set of seen review IDs, because the API
    can occasionally return duplicates across pages.

    Parameters
    ----------
    app_id : str
        The Google Play package name.
    target_count : int
        The desired number of reviews.

    Returns
    -------
    list[dict]
        A list of normalised review dictionaries.
    """
    all_reviews: List[Dict[str, Any]] = []       # accumulates the final results
    seen_review_ids = set()                       # tracks IDs we've already stored
    continuation_token: Optional[str] = None      # pagination cursor from the API
    batch_num = 1                                 # human-readable batch counter for logging

    # Keep fetching until we reach the target or exhaust available reviews.
    while len(all_reviews) < target_count:
        # Only request as many as we still need (capped at 200, the API max).
        remaining = target_count - len(all_reviews)
        batch_size = min(200, remaining)

        print(f"[INFO] Fetching batch {batch_num} (up to {batch_size} reviews)...")

        try:
            # `reviews()` returns a tuple: (list_of_review_dicts, next_continuation_token).
            # Sorting by NEWEST ensures we get the most recent reviews first.
            batch, continuation_token = reviews(
                app_id,
                lang="en",
                country="ca",
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
        except Exception as exc:
            # Network failures, rate-limiting, etc. – stop gracefully.
            print(f"[ERROR] Failed while fetching reviews: {exc}")
            break

        # An empty batch means Google Play has no more reviews to give us.
        if not batch:
            print("[INFO] No more reviews returned by Google Play.")
            break

        before_count = len(all_reviews)

        for raw in batch:
            rid = raw.get("reviewId")

            # --- De-duplication ---
            # Skip any review whose ID we've already recorded.
            if rid and rid in seen_review_ids:
                continue

            if rid:
                seen_review_ids.add(rid)

            # Normalise and append.
            normalized = normalize_review(raw, len(all_reviews) + 1)
            all_reviews.append(normalized)

        added = len(all_reviews) - before_count
        print(f"[INFO] Added {added} new reviews. Total so far: {len(all_reviews)}")

        # If the API didn't return a continuation token, there are no more pages.
        if continuation_token is None:
            print("[INFO] No continuation token returned. Stopping.")
            break

        batch_num += 1

    return all_reviews


# ---------------------------------------------------------------------------
# FILE-WRITING HELPERS
# ---------------------------------------------------------------------------

def write_jsonl(records: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Write a list of dictionaries to a JSONL file (one JSON object per line).

    JSONL is convenient for large datasets because each line is independently
    parseable – you can stream or sample without loading the entire file.
    """
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            # ensure_ascii=False keeps accented characters readable in the file.
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_metadata(
    app_info: Dict[str, Any],
    extracted_count: int,
    output_path: Path,
) -> None:
    """
    Save a JSON file that documents everything about this collection run:
    which app, how many reviews were requested vs. actually collected, the
    store-reported stats, and any caveats.

    This metadata file is useful both for reproducibility and for the next
    pipeline step (02_clean.py) to reference.
    """
    metadata = {
        "app_name": app_info.get("title", "Unknown"),
        "app_id": APP_ID,
        "app_url": APP_URL,
        "store": "Google Play Store",
        "collection_method": "Python google-play-scraper library",
        "collection_country": "ca",
        "collection_language": "en",
        "sort_order": "NEWEST",
        "requested_review_count": TARGET_REVIEW_COUNT,
        "extracted_review_count": extracted_count,
        # The next two fields come from the Play Store's own reported totals,
        # which may differ from what the scraper can actually retrieve.
        "google_play_reported_review_count": app_info.get("reviews"),
        "google_play_reported_rating_count": app_info.get("ratings"),
        "google_play_score": app_info.get("score"),
        "notes": [
            "Google Play may not expose every historical review through scraping APIs.",
            "If fewer than the requested number of reviews are returned, this may reflect store-side limits or app-side availability.",
            "Raw data is saved in data/reviews_raw.jsonl.",
            "Cleaning decisions will be completed by src/02_clean.py and can later update this metadata file if desired."
        ],
        # Placeholder list – the cleaning script can append its decisions here.
        "cleaning_decisions": [],
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orchestrates the full collection pipeline:
      1. Create the data/ directory if needed.
      2. Fetch app-level metadata from Google Play.
      3. Scrape up to TARGET_REVIEW_COUNT reviews.
      4. Write the raw reviews to a JSONL file.
      5. Write a metadata summary to a JSON file.
    """
    ensure_data_dir()

    # --- Step 1: App metadata ---
    print("[INFO] Fetching app metadata...")
    app_info = safe_get_app_info(APP_ID)
    print(f"[INFO] App title: {app_info.get('title')}")
    print(f"[INFO] Google Play reported reviews: {app_info.get('reviews')}")

    # --- Step 2: Reviews ---
    print("[INFO] Fetching reviews...")
    records = fetch_reviews(APP_ID, TARGET_REVIEW_COUNT)

    # --- Step 3: Persist to disk ---
    print(f"[INFO] Writing raw reviews to: {RAW_OUTPUT_PATH}")
    write_jsonl(records, RAW_OUTPUT_PATH)

    print(f"[INFO] Writing metadata to: {METADATA_PATH}")
    write_metadata(app_info, len(records), METADATA_PATH)

    # --- Done ---
    print("[DONE] Review collection complete.")
    print(f"[DONE] Extracted {len(records)} reviews.")


# Standard Python idiom: only run main() when executed directly, not when imported.
if __name__ == "__main__":
    main()
