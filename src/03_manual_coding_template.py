"""creates/updates manual review groups file"""
#!/usr/bin/env python3
"""
src/03_manual_coding_template.py

Task 3.1 — Manual Coding Support

Creates data/review_groups_manual.json with a starter template if the file
doesn't exist yet.  If it does exist, prints a summary of what's in it.

This script never blocks or fails — it just reports status and moves on,
so a "run all" pipeline won't get stuck waiting for manual work.

Usage:
    python3 src/03_manual_coding_template.py

Design choices:
    The manual pipeline work was done by hand — reading reviews and
    assigning them to groups myself.  Since this file has no
    automated logic to explain, I turned it into a simple verification
    module.  It creates a template if the file doesn't exist yet, and
    if it does, it checks whether we have at least 5 groups with at
    least 50 reviews assigned.  It prints the status and moves on
    without blocking, so the auto pipeline is never affected.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
GROUPS_PATH = DATA_DIR / "review_groups_manual.json"

# ---------------------------------------------------------------------------
# Minimum requirements (just for the status message)
# ---------------------------------------------------------------------------

MIN_GROUPS = 5
MIN_TOTAL_REVIEWS = 50

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

TEMPLATE = {
    "groups": [
        {
            "group_id": "G1",
            "theme": "App crashes during activity logging — THIS IS AN EXAMPLE, PLEASE REMOVE",
            "review_ids": ["rev_12", "rev_33", "rev_45", "rev_89"],
            "example_reviews": [
                "The app crashes every time I log my run.",
                "Logging workouts causes the app to freeze."
            ]
        }
    ]
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # --- If file doesn't exist, create the template ---
    if not GROUPS_PATH.exists():
        with GROUPS_PATH.open("w", encoding="utf-8") as f:
            json.dump(TEMPLATE, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Created starter template at {GROUPS_PATH}")
        print(f"[INFO] Open it, remove the example, and add your own groups.")
        print(f"[INFO] You need at least {MIN_GROUPS} groups with at least {MIN_TOTAL_REVIEWS} total reviews.")
        return

    # --- File exists — load and print status ---
    try:
        with GROUPS_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, Exception):
        print(f"[WARN] {GROUPS_PATH} exists but could not be parsed. Skipping.")
        return

    groups = payload.get("groups", [])
    group_count = len(groups)
    total_reviews = sum(len(g.get("review_ids", [])) for g in groups)

    if group_count >= MIN_GROUPS and total_reviews >= MIN_TOTAL_REVIEWS:
        print(f"[OK] review_groups_manual.json — {group_count} group(s), {total_reviews} total reviews:")
        for g in groups:
            gid = g.get("group_id", "?")
            theme = g.get("theme", "No theme")
            count = len(g.get("review_ids", []))
            print(f"     {gid}: '{theme}' — {count} reviews")
    else:
        print(f"[INFO] review_groups_manual.json has {group_count} group(s) and {total_reviews} reviews.")
        print(f"[INFO] Needs at least {MIN_GROUPS} groups and {MIN_TOTAL_REVIEWS} reviews to be complete.")
        print(f"[INFO] Skipping — this does not affect the auto pipeline.")


if __name__ == "__main__":
    main()
