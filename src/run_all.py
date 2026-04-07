"""runs the entire SpecChain pipeline from start to finish"""
#!/usr/bin/env python3
"""
src/run_all.py

Master pipeline runner for EECS 4312 SpecChain.

Installs required dependencies, then executes every src/ script in order.
At startup, asks whether to skip the data collection step so that
reviews_raw.jsonl stays unchanged — this is important if you have already
done manual or hybrid coding against that dataset, since re-scraping
could change review IDs and break your manual work.

Usage:
    python src/run_all.py

Design choices:
    Dependencies are installed automatically so the TA can run one
    command and see everything work.  Each step runs as a subprocess
    so failures are visible but don't crash the whole pipeline.  The
    validate_repo script runs first (to show what's missing) and last
    (to confirm everything was generated).

Execution order:
    Step 0:  Install dependencies
    Step 1:  src/00_validate_repo.py        → pre-run check
    Step 2:  src/01_collect_or_import.py     → data/reviews_raw.jsonl
    Step 3:  src/02_clean.py                → data/reviews_clean.jsonl
    Step 4:  src/03_manual_coding_template.py → verifies manual groups
    Step 5:  src/04_personas_manual.py       → verifies manual personas
    Step 6:  src/05_personas_auto.py         → data/review_groups_auto.json
                                               personas/personas_auto.json
                                               prompts/prompt_auto.json
    Step 7:  src/06_spec_generate.py         → spec/spec_auto.md
    Step 8:  src/07_tests_generate.py        → tests/tests_auto.json
    Step 9:  src/08_metrics.py --all         → metrics/metrics_auto.json
                                               metrics/metrics_summary.json
    Final:   src/00_validate_repo.py         → post-run validation
"""

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (one level above src/)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# ---------------------------------------------------------------------------
# Dependencies to install
# ---------------------------------------------------------------------------

DEPENDENCIES = [
    "groq",
    "google-play-scraper",
    "nltk",
    "num2words",
    "scikit-learn",
    "numpy",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_banner(step: str, description: str) -> None:
    """Print a visible banner between pipeline steps."""
    print()
    print("=" * 65)
    print(f"  STEP {step}: {description}")
    print("=" * 65)
    print()


def install_dependencies() -> None:
    """Install all required Python packages."""
    print_banner("0", "Installing dependencies")
    for pkg in DEPENDENCIES:
        print(f"  Installing {pkg} ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg,
             "--break-system-packages", "-q"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  [WARN] Failed to install {pkg}: {result.stderr.strip()}")
        else:
            print(f"  [OK]   {pkg}")
    print()


def run_script(script_name: str, extra_args: list = None) -> bool:
    """
    Run a Python script as a subprocess.
    Returns True if it succeeded, False otherwise.
    """
    script_path = SRC / script_name
    if not script_path.exists():
        print(f"  [ERROR] Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\n  [ERROR] {script_name} exited with code {result.returncode}")
        return False

    return True


def ask_skip_collection() -> bool:
    """
    Ask the user whether to skip the data collection step.
    Defaults to skipping (Y) so that manual/hybrid data stays consistent.
    If reviews_raw.jsonl doesn't exist, collection cannot be skipped.
    """
    raw_path = ROOT / "data" / "reviews_raw.jsonl"

    print()
    if raw_path.exists():
        print(f"  data/reviews_raw.jsonl already exists.")
    else:
        print(f"  data/reviews_raw.jsonl does NOT exist — collection is required.")
        return False

    print()
    print("  Re-running collection will re-scrape Google Play and may change")
    print("  review IDs, which would break manual and hybrid coding.")
    print()

    try:
        answer = input("  Skip data collection? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        answer = "y"

    return answer != "n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║           EECS 4312 — SpecChain Pipeline Runner               ║")
    print("╚═════════════════════════════════════════════════════════════════╝")

    # --- Step 0: Install dependencies ---
    install_dependencies()

    # --- Step 1: Pre-run repo validation ---
    print_banner("1", "Pre-run validation — src/00_validate_repo.py")
    run_script("00_validate_repo.py")

    # --- Step 2: Data collection (optional) ---
    skip_collection = ask_skip_collection()

    if skip_collection:
        print_banner("2", "SKIPPED — src/01_collect_or_import.py")
        print("  Using existing data/reviews_raw.jsonl")
    else:
        print_banner("2", "Data collection — src/01_collect_or_import.py")
        print("  Output: data/reviews_raw.jsonl, data/dataset_metadata.json")
        run_script("01_collect_or_import.py")

    # --- Step 3: Cleaning ---
    print_banner("3", "Data cleaning — src/02_clean.py")
    print("  Output: data/reviews_clean.jsonl")
    run_script("02_clean.py")

    # --- Step 4: Manual groups verification ---
    print_banner("4", "Manual groups verification — src/03_manual_coding_template.py")
    print("  Checks: data/review_groups_manual.json")
    run_script("03_manual_coding_template.py")

    # --- Step 5: Manual personas verification ---
    print_banner("5", "Manual personas verification — src/04_personas_manual.py")
    print("  Checks: personas/personas_manual.json")
    run_script("04_personas_manual.py")

    # --- Step 6: Automated grouping + personas ---
    print_banner("6", "Automated grouping + personas — src/05_personas_auto.py")
    print("  Output: data/review_groups_auto.json")
    print("          personas/personas_auto.json")
    print("          prompts/prompt_auto.json")
    run_script("05_personas_auto.py")

    # --- Step 7: Automated spec generation ---
    print_banner("7", "Automated spec generation — src/06_spec_generate.py")
    print("  Output: spec/spec_auto.md")
    run_script("06_spec_generate.py")

    # --- Step 8: Automated test generation ---
    print_banner("8", "Automated test generation — src/07_tests_generate.py")
    print("  Output: tests/tests_auto.json")
    run_script("07_tests_generate.py")

    # --- Step 9: Metrics ---
    print_banner("9", "Metrics computation — src/08_metrics.py --all")
    print("  Output: metrics/metrics_auto.json")
    print("          metrics/metrics_manual.json (if manual pipeline complete)")
    print("          metrics/metrics_hybrid.json (if hybrid pipeline complete)")
    print("          metrics/metrics_summary.json")
    run_script("08_metrics.py", ["--all"])

    # --- Final: Post-run repo validation ---
    print_banner("✓", "Post-run validation — src/00_validate_repo.py")
    run_script("00_validate_repo.py")

    # --- Done ---
    print()
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║                  Pipeline complete.                            ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
