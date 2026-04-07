"""validates that all required folders and files exist"""
#!/usr/bin/env python3
"""
src/00_validate_repo.py

Repository structure validator for EECS 4312 SpecChain.

Checks whether all required folders and files exist and prints a clear
report.  Every file is required — nothing is optional.

Usage:
    python src/00_validate_repo.py

Design choices:
    This script simply lists every file the repo should contain and
    checks if each one exists.  The list was built from the actual
    repo contents so nothing is missed.  It prints a clear FOUND or
    MISSING for each file so the TA can see at a glance whether the
    repo is complete.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Required folders
# ---------------------------------------------------------------------------

REQUIRED_DIRS = [
    "src",
    "data",
    "personas",
    "spec",
    "tests",
    "prompts",
    "metrics",
    "reflection",
]

# ---------------------------------------------------------------------------
# Required files — every file that must be in the repo
# ---------------------------------------------------------------------------

REQUIRED_FILES = [
    # Source scripts
    "src/00_validate_repo.py",
    "src/01_collect_or_import.py",
    "src/02_clean.py",
    "src/03_manual_coding_template.py",
    "src/04_personas_manual.py",
    "src/05_personas_auto.py",
    "src/06_spec_generate.py",
    "src/07_tests_generate.py",
    "src/08_metrics.py",
    "src/run_all.py",
    # Data
    "data/reviews_raw.jsonl",
    "data/reviews_clean.jsonl",
    "data/dataset_metadata.json",
    "data/review_groups_auto.json",
    "data/review_groups_manual.json",
    "data/review_groups_hybrid.json",
    # Personas
    "personas/personas_auto.json",
    "personas/personas_manual.json",
    "personas/personas_hybrid.json",
    # Specs
    "spec/spec_auto.md",
    "spec/spec_manual.md",
    "spec/spec_hybrid.md",
    # Tests
    "tests/tests_auto.json",
    "tests/tests_manual.json",
    "tests/tests_hybrid.json",
    # Prompts
    "prompts/prompt_auto.json",
    # Metrics
    "metrics/metrics_auto.json",
    "metrics/metrics_manual.json",
    "metrics/metrics_hybrid.json",
    "metrics/metrics_summary.json",
    # Reflection
    "reflection/reflection.md",
    # README
    "README.md",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("Checking repository structure...")
    print()

    missing_count = 0

    # --- Check directories ---
    for d in REQUIRED_DIRS:
        path = ROOT / d
        if path.is_dir():
            print(f"  {d}/ found")
        else:
            print(f"  {d}/ MISSING")
            missing_count += 1

    print()

    # --- Check files ---
    for f in REQUIRED_FILES:
        path = ROOT / f
        if path.exists():
            print(f"  {f} found")
        else:
            print(f"  {f} MISSING")
            missing_count += 1

    # --- Summary ---
    print()
    if missing_count == 0:
        print("Repository validation complete.")
        print("All required files and folders are present.")
    else:
        print(f"Repository validation complete — {missing_count} item(s) MISSING.")
        print("Run 'python src/run_all.py' to generate missing files.")
    print()


if __name__ == "__main__":
    main()
