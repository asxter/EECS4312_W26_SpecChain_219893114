"""imports or reads your raw dataset; if you scraped, include scraper here"""
#!/usr/bin/env python3
"""
Collect Google Play reviews for the assigned app and save them to data/reviews_raw.jsonl.

App used here:
    MindDoc / Moodpath
    https://play.google.com/store/apps/details?id=de.moodpath.android&hl=en_CA

Output:
    data/reviews_raw.jsonl
    data/dataset_metadata.json

Install first:
    pip install google-play-scraper

Run:
    python src/01_collect_or_import.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from google_play_scraper import Sort, reviews, app


APP_ID = "de.moodpath.android"
APP_URL = "https://play.google.com/store/apps/details?id=de.moodpath.android&hl=en_CA"

# Adjust this if needed. The project asks for about 1,000 to 5,000 reviews.
TARGET_REVIEW_COUNT = 3000

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_OUTPUT_PATH = DATA_DIR / "reviews_raw.jsonl"
METADATA_PATH = DATA_DIR / "dataset_metadata.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def safe_get_app_info(app_id: str) -> Dict[str, Any]:
    """
    Try to fetch app metadata from Google Play.
    If some fields are missing, return sensible defaults.
    """
    try:
        info = app(app_id, lang="en", country="ca")
        return info
    except Exception as exc:
        print(f"[WARN] Could not fetch app metadata: {exc}")
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
    Convert library output into a stable JSONL record format.
    """
    user_name = raw_review.get("userName")
    review_text = raw_review.get("content")
    review_id = raw_review.get("reviewId")

    return {
        "review_id": review_id if review_id else f"generated_{index:06d}",
        "app_id": APP_ID,
        "app_url": APP_URL,
        "user_name": user_name,
        "score": raw_review.get("score"),
        "thumbs_up_count": raw_review.get("thumbsUpCount"),
        "review_created_version": raw_review.get("reviewCreatedVersion"),
        "at": raw_review.get("at").isoformat() if raw_review.get("at") else None,
        "reply_content": raw_review.get("replyContent"),
        "replied_at": raw_review.get("repliedAt").isoformat() if raw_review.get("repliedAt") else None,
        "content": review_text,
    }


def fetch_reviews(app_id: str, target_count: int) -> List[Dict[str, Any]]:
    """
    Fetch reviews in batches until target_count is reached or no more reviews are available.
    """
    all_reviews: List[Dict[str, Any]] = []
    seen_review_ids = set()
    continuation_token: Optional[str] = None
    batch_num = 1

    while len(all_reviews) < target_count:
        remaining = target_count - len(all_reviews)
        batch_size = min(200, remaining)

        print(f"[INFO] Fetching batch {batch_num} (up to {batch_size} reviews)...")

        try:
            batch, continuation_token = reviews(
                app_id,
                lang="en",
                country="ca",
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
        except Exception as exc:
            print(f"[ERROR] Failed while fetching reviews: {exc}")
            break

        if not batch:
            print("[INFO] No more reviews returned by Google Play.")
            break

        before_count = len(all_reviews)

        for raw in batch:
            rid = raw.get("reviewId")
            if rid and rid in seen_review_ids:
                continue

            if rid:
                seen_review_ids.add(rid)

            normalized = normalize_review(raw, len(all_reviews) + 1)
            all_reviews.append(normalized)

        added = len(all_reviews) - before_count
        print(f"[INFO] Added {added} new reviews. Total so far: {len(all_reviews)}")

        if continuation_token is None:
            print("[INFO] No continuation token returned. Stopping.")
            break

        batch_num += 1

    return all_reviews


def write_jsonl(records: List[Dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_metadata(
    app_info: Dict[str, Any],
    extracted_count: int,
    output_path: Path,
) -> None:
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
        "google_play_reported_review_count": app_info.get("reviews"),
        "google_play_reported_rating_count": app_info.get("ratings"),
        "google_play_score": app_info.get("score"),
        "notes": [
            "Google Play may not expose every historical review through scraping APIs.",
            "If fewer than the requested number of reviews are returned, this may reflect store-side limits or app-side availability.",
            "Raw data is saved in data/reviews_raw.jsonl.",
            "Cleaning decisions will be completed by src/02_clean.py and can later update this metadata file if desired."
        ],
        "cleaning_decisions": [],
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def main() -> None:
    ensure_data_dir()

    print("[INFO] Fetching app metadata...")
    app_info = safe_get_app_info(APP_ID)
    print(f"[INFO] App title: {app_info.get('title')}")
    print(f"[INFO] Google Play reported reviews: {app_info.get('reviews')}")

    print("[INFO] Fetching reviews...")
    records = fetch_reviews(APP_ID, TARGET_REVIEW_COUNT)

    print(f"[INFO] Writing raw reviews to: {RAW_OUTPUT_PATH}")
    write_jsonl(records, RAW_OUTPUT_PATH)

    print(f"[INFO] Writing metadata to: {METADATA_PATH}")
    write_metadata(app_info, len(records), METADATA_PATH)

    print("[DONE] Review collection complete.")
    print(f"[DONE] Extracted {len(records)} reviews.")


if __name__ == "__main__":
    main()
