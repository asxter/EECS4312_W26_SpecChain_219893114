#!/usr/bin/env python3
"""Creates/updates persona template + instructions"""
# src/04_personas_manual.py
#
# Task 3.2 — Manual Persona Construction Support
#
# Reads data/review_groups_manual.json and generates a persona template
# in personas/personas_manual.json pre-populated with one blank persona
# per review group. If personas_manual.json already exists, existing
# personas are preserved and only missing ones are added.
# Also prints step-by-step instructions for completing the personas.
#
# Usage:
#     python3 src/04_personas_manual.py

import json
from pathlib import Path

ROOT         = Path(__file__).resolve().parents[1]
DATA_DIR     = ROOT / "data"
PERSONAS_DIR = ROOT / "personas"

GROUPS_PATH   = DATA_DIR     / "review_groups_manual.json"
PERSONAS_PATH = PERSONAS_DIR / "personas_manual.json"


INSTRUCTIONS = """
=============================================================
  MANUAL PERSONA CONSTRUCTION INSTRUCTIONS — Task 3.2
=============================================================

GOAL:
  For each review group in review_groups_manual.json, write one
  persona that summarizes the common goals, pain points, and
  context of users in that group.

STEPS:
  1. Open personas/personas_manual.json (just generated/updated).
  2. For each persona, fill in:
       - "name"              : a descriptive persona name
                               e.g. "Cost-Sensitive Mental Health Seeker"
       - "description"       : 1–2 sentences describing who this user is
       - "goals"             : list of what this user wants from the app
       - "pain_points"       : list of frustrations or unmet needs
       - "context"           : situational details (device, frequency, etc.)
       - "derived_from_group": already filled in — do not change
  3. Every persona must be grounded in the reviews of its group.
     Do not invent details not supported by the reviews.

TIPS:
  - Re-read the reviews in the group before writing the persona.
  - Goals and pain points should come directly from review language.
  - Keep each persona distinct — they should represent different
    types of users, not just different sentiments.

OUTPUT FILE:
  - personas/personas_manual.json ← fill this in manually
=============================================================
"""


PERSONA_TEMPLATE = {
    "name": "",
    "description": "",
    "goals": [],
    "pain_points": [],
    "context": "",
}


def load_groups() -> list:
    with GROUPS_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("groups", [])


def create_or_update_personas(groups: list) -> tuple:
    """
    Preserve existing personas and add blank slots for any group
    that does not yet have a persona.
    """
    existing_by_group = {}
    existing_personas = []

    if PERSONAS_PATH.exists():
        with PERSONAS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        existing_personas = data.get("personas", [])
        for p in existing_personas:
            gid = str(p.get("derived_from_group", "")).strip()
            if gid:
                existing_by_group[gid] = p

    personas = list(existing_personas)
    new_count = 0

    for i, group in enumerate(groups, start=1):
        gid   = str(group.get("group_id") or group.get("id", "")).strip()
        theme = group.get("theme", "")
        if gid in existing_by_group:
            continue  # already have a persona for this group
        blank = {
            "id": f"P{i}",
            "derived_from_group": gid,
            **PERSONA_TEMPLATE,
            "name": f"[Persona for group {gid} — {theme}]",
        }
        personas.append(blank)
        new_count += 1

    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    with PERSONAS_PATH.open("w", encoding="utf-8") as fh:
        json.dump({"personas": personas}, fh, indent=2, ensure_ascii=False)

    return personas, new_count


def validate_personas(personas: list, group_ids: set) -> None:
    print("\nValidating personas:")
    all_valid = True
    for p in personas:
        pid          = p.get("id", "?")
        name         = p.get("name", "")
        derived_from = str(p.get("derived_from_group", "")).strip()
        description  = p.get("description", "")
        goals        = p.get("goals", [])
        pain_points  = p.get("pain_points", [])

        issues = []
        if not name or name.startswith("[Persona for group"):
            issues.append("name not filled in yet")
        if not description:
            issues.append("description is empty")
        if not goals:
            issues.append("no goals listed")
        if not pain_points:
            issues.append("no pain_points listed")
        if derived_from not in group_ids:
            issues.append(f"derived_from_group '{derived_from}' not found in review_groups_manual.json")

        if issues:
            all_valid = False
            print(f"  [WARN] Persona {pid} — '{name}'")
            for issue in issues:
                print(f"         ✗ {issue}")
        else:
            print(f"  [OK]   Persona {pid} — '{name}' (group {derived_from})")
            print(f"         Goals: {len(goals)} | Pain points: {len(pain_points)}")

    print()
    if all_valid:
        print("[PASS] All personas are complete and correctly linked to review groups.")
    else:
        print("[INFO] Fill in the remaining fields in personas/personas_manual.json and re-run.")


def main() -> None:
    print(INSTRUCTIONS)

    if not GROUPS_PATH.exists():
        print(f"[ERROR] Missing: {GROUPS_PATH}")
        print("        Run src/03_manual_coding_template.py first and complete your review groups.")
        return

    groups    = load_groups()
    group_ids = {str(g.get("group_id") or g.get("id", "")).strip() for g in groups}
    print(f"[OK] review_groups_manual.json loaded — {len(groups)} group(s): {sorted(group_ids)}")

    personas, new_count = create_or_update_personas(groups)

    if new_count > 0:
        print(f"[OK] personas_manual.json updated — {new_count} new blank persona(s) added")
    else:
        print(f"[OK] personas_manual.json already has a persona for every group")

    print(f"[INFO] {len(personas)} total persona(s) in file")

    validate_personas(personas, group_ids)


if __name__ == "__main__":
    main()
