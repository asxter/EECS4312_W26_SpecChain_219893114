"""creates/updates persona template + instructions"""
#!/usr/bin/env python3
"""
src/04_personas_manual.py

Task 3.2 — Manual Persona Construction Support

Creates personas/personas_manual.json with a starter template if the file
doesn't exist yet.  If it does exist, prints a summary of what's in it.

This script never blocks or fails — it just reports status and moves on,
so the auto pipeline is never affected.

Usage:
    python3 src/04_personas_manual.py

Design choices:
    The manual personas were written by hand based on our review groups.
    Since there is no automated logic to explain here, we turned this
    script into a simple verification module.  It creates a template if
    the file is missing, and if it exists, it checks that each persona
    has a name, description, goals, and pain points filled in.  It
    prints what's done and what's missing, then exits without blocking.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
PERSONAS_DIR = ROOT / "personas"
PERSONAS_PATH = PERSONAS_DIR / "personas_manual.json"

# ---------------------------------------------------------------------------
# Template written when the file is missing
# ---------------------------------------------------------------------------

TEMPLATE = {
    "personas": [
        {
            "id": "P1",
            "name": "Cost-Sensitive Mental Health Seeker — THIS IS AN EXAMPLE, PLEASE REMOVE",
            "description": "A user who wants free access to mood tracking features.",
            "derived_from_group": "G1",
            "goals": ["Track mood daily without paying"],
            "pain_points": ["Paywall blocks core features"],
            "context": ["Uses the app on Android, checks in once a day"],
            "constraints": ["Limited budget"],
            "evidence_reviews": ["rev_12", "rev_33"]
        }
    ]
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)

    # --- If file doesn't exist, create the template ---
    if not PERSONAS_PATH.exists():
        with PERSONAS_PATH.open("w", encoding="utf-8") as f:
            json.dump(TEMPLATE, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Created starter template at {PERSONAS_PATH}")
        print(f"[INFO] Open it, remove the example, and add your own personas.")
        print(f"[INFO] You need one persona per manual review group.")
        return

    # --- File exists — load and print status ---
    try:
        with PERSONAS_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, Exception):
        print(f"[WARN] {PERSONAS_PATH} exists but could not be parsed. Skipping.")
        return

    personas = payload.get("personas", [])

    if not personas:
        print(f"[INFO] personas_manual.json exists but has no personas.")
        print(f"[INFO] Skipping — this does not affect the auto pipeline.")
        return

    # --- Check each persona for completeness ---
    complete = 0
    incomplete = 0

    for p in personas:
        pid = p.get("id", "?")
        name = p.get("name", "")
        has_name = bool(name) and "EXAMPLE" not in name.upper()
        has_desc = bool(p.get("description", ""))
        has_goals = bool(p.get("goals", []))
        has_pains = bool(p.get("pain_points", []))

        if has_name and has_desc and has_goals and has_pains:
            group = p.get("derived_from_group", "?")
            print(f"  [OK]   {pid}: '{name}' (group {group})")
            complete += 1
        else:
            missing = []
            if not has_name: missing.append("name")
            if not has_desc: missing.append("description")
            if not has_goals: missing.append("goals")
            if not has_pains: missing.append("pain_points")
            print(f"  [WARN] {pid}: missing {', '.join(missing)}")
            incomplete += 1

    print()
    if incomplete == 0:
        print(f"[OK] All {complete} persona(s) are complete.")
    else:
        print(f"[INFO] {complete} complete, {incomplete} incomplete.")
        print(f"[INFO] Skipping — this does not affect the auto pipeline.")


if __name__ == "__main__":
    main()
