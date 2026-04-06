"""creates/updates coding table template + instructions"""
#!/usr/bin/env python3
"""Creates/updates coding table template + instructions"""
# src/03_manual_coding_template.py
#
# Task 3.1 — Manual Coding Support
#
# Generates a coding table template (data/coding_table.json) pre-populated
# with all review IDs from reviews_clean.jsonl. Each row has blank fields
# for you to fill in manually: assigned group, theme label, and notes.
# Also prints step-by-step instructions for how to complete the coding.
#
# Usage:
#     python3 src/03_manual_coding_template.py

import json
from pathlib import Path

ROOT               = Path(__file__).resolve().parents[1]
DATA_DIR           = ROOT / "data"
REVIEWS_CLEAN_PATH = DATA_DIR / "reviews_clean.jsonl"
CODING_TABLE_PATH  = DATA_DIR / "coding_table.json"
GROUPS_PATH        = DATA_DIR / "review_groups_manual.json"


INSTRUCTIONS = """
=============================================================
  MANUAL CODING INSTRUCTIONS — Task 3.1
=============================================================

GOAL:
  Read through the cleaned reviews and assign each one to a
  group that represents a distinct type of user or user situation.
  You must create at least 5 groups, each with at least 10 reviews.

STEPS:
  1. Open data/coding_table.json (just generated/updated).
  2. For each entry, fill in:
       - "group_id"  : e.g. "G1", "G2", ... "G5"
       - "theme"     : short label for the group (e.g. "Pricing Complaints")
       - "notes"     : optional — why you assigned this review to this group
  3. Leave "group_id" as "" for reviews you do not want to include
     in any group (they will be excluded from coverage metrics).
  4. Once coded, run this script again to generate a draft
     review_groups_manual.json from your coding table.

TIPS:
  - Read at least 50–100 reviews before deciding on group themes.
  - Group by user situation or goal, not just sentiment.
  - Each group should be meaningfully different from the others.
  - A review can only belong to one group.

OUTPUT FILES:
  - data/coding_table.json         ← fill this in manually
  - data/review_groups_manual.json ← auto-generated from your coding
=============================================================
"""


def load_reviews() -> dict:
    reviews = {}
    with REVIEWS_CLEAN_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                review = json.loads(line)
                rid = str(review.get("review_id") or review.get("id", ""))
                if rid:
                    reviews[rid] = review
    return reviews


def create_or_update_coding_table(reviews: dict) -> list:
    """
    If coding_table.json already exists, preserve existing coding decisions
    and only add rows for new review IDs.
    """
    existing = {}
    if CODING_TABLE_PATH.exists():
        with CODING_TABLE_PATH.open("r", encoding="utf-8") as fh:
            for row in json.load(fh):
                existing[row["review_id"]] = row

    table = []
    new_count = 0
    for rid, review in reviews.items():
        if rid in existing:
            table.append(existing[rid])
        else:
            text = review.get("text") or review.get("content") or review.get("review", "")
            table.append({
                "review_id": rid,
                "text_preview": str(text)[:200],
                "group_id": "",
                "theme": "",
                "notes": ""
            })
            new_count += 1

    with CODING_TABLE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(table, fh, indent=2, ensure_ascii=False)

    return table, new_count


def generate_review_groups(table: list) -> None:
    """
    Reads the filled-in coding table and builds review_groups_manual.json.
    Only runs if at least one review has been assigned a group_id.
    """
    groups: dict = {}
    for row in table:
        gid   = row.get("group_id", "").strip()
        theme = row.get("theme", "").strip()
        rid   = row.get("review_id", "").strip()
        if not gid or not rid:
            continue
        if gid not in groups:
            groups[gid] = {"group_id": gid, "theme": theme, "review_ids": []}
        if theme and not groups[gid]["theme"]:
            groups[gid]["theme"] = theme
        groups[gid]["review_ids"].append(rid)

    if not groups:
        print("\n[INFO] No reviews have been coded yet.")
        print("       Fill in data/coding_table.json and re-run this script")
        print("       to auto-generate data/review_groups_manual.json.")
        return

    payload = {"groups": list(groups.values())}
    with GROUPS_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"\n[DONE] review_groups_manual.json written — {len(groups)} group(s):")
    for gid, g in sorted(groups.items()):
        print(f"  {gid}: '{g['theme']}' — {len(g['review_ids'])} reviews")


def main() -> None:
    print(INSTRUCTIONS)

    if not REVIEWS_CLEAN_PATH.exists():
        print(f"[ERROR] Missing: {REVIEWS_CLEAN_PATH}")
        print("        Run src/02_clean.py first.")
        return

    reviews = load_reviews()
    print(f"[OK] Loaded {len(reviews)} reviews from reviews_clean.jsonl")

    table, new_count = create_or_update_coding_table(reviews)

    if new_count > 0:
        print(f"[OK] coding_table.json updated — {new_count} new row(s) added")
    else:
        print(f"[OK] coding_table.json already up to date — {len(table)} rows")

    coded = sum(1 for row in table if row.get("group_id", "").strip())
    print(f"[INFO] {coded}/{len(table)} reviews have been assigned a group so far")

    # Generate review_groups_manual.json from whatever is coded so far
    generate_review_groups(table)


if __name__ == "__main__":
    main()
