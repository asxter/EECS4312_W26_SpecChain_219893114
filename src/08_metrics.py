"""computes metrics: coverage/traceability/ambiguity/testability"""
#!/usr/bin/env python3
"""
src/08_metrics.py

Compute pipeline metrics for EECS 4312 SpecChain.

Supports:
    - manual
    - auto
    - hybrid

Examples:
    python3 src/08_metrics.py --pipeline auto
    python3 src/08_metrics.py --pipeline manual
    python3 src/08_metrics.py --pipeline hybrid
    python3 src/08_metrics.py --all

Design choices:
    This script does not call any LLM — it just reads the files produced
    by earlier steps and counts things.  We measure four metrics that show
    how well the pipeline did:  (1) review coverage — what fraction of
    cleaned reviews ended up in a group, (2) traceability — whether every
    requirement links back to a persona and group, (3) testability — what
    fraction of requirements have at least one test, and (4) ambiguity —
    how many requirements contain vague words like "easy" or "fast".
    We use a simple keyword list for ambiguity because it is transparent,
    easy to explain, and good enough for a course project.  The script
    can run for one pipeline at a time or all three at once with --all,
    which also produces a summary file for easy comparison.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]     # project root
DATA_DIR = ROOT / "data"
PERSONAS_DIR = ROOT / "personas"
SPEC_DIR = ROOT / "spec"
TESTS_DIR = ROOT / "tests"
METRICS_DIR = ROOT / "metrics"

REVIEWS_CLEAN_PATH = DATA_DIR / "reviews_clean.jsonl"   # shared input across all pipelines

# ---------------------------------------------------------------------------
# Ambiguous-term list
#
# If any of these words appear in a requirement's description or acceptance
# criteria, that requirement is flagged as ambiguous.  These are common
# vague adjectives that make a requirement hard to test or verify.
# ---------------------------------------------------------------------------

AMBIGUOUS_TERMS = {
    "fast",
    "easy",
    "better",
    "user-friendly",
    "user friendly",
    "simple",
    "quick",
    "efficient",
    "effective",
    "reliable",
    "intuitive",
    "seamless",
    "appropriate",
    "useful",
    "meaningful",
    "helpful",
    "clearly",
    "sufficient",
    "enough",
    "relevant",
    "secure",
    "smooth",
}


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write a dict to a pretty-printed JSON file, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def count_reviews_clean(path: Path) -> int:
    """Count the number of non-blank lines in the cleaned reviews JSONL file."""
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Spec parsing helpers
# ---------------------------------------------------------------------------

def strip_brackets(value: str) -> str:
    """Remove outer [ ] brackets from a field value parsed out of the Markdown spec."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1].strip()
    return value


def parse_spec_markdown(spec_text: str) -> List[Dict[str, str]]:
    """
    Parse a spec Markdown file back into a list of requirement dicts.

    Expected format per requirement:

        # Requirement ID: FR_auto_1
        - Description: [The system shall ...]
        - Source Persona: [P_auto_1 or Persona Name]
        - Traceability: [Derived from review group A1]
        - Acceptance Criteria: [Given ..., When ..., Then ...]
    """
    pattern = re.compile(
        r"# Requirement ID:\s*(?P<requirement_id>[^\n]+)\n"
        r"\s*"
        r"-\s*Description:\s*(?P<description>\[[\s\S]*?\])\n"
        r"-\s*Source Persona:\s*(?P<source_persona>\[[\s\S]*?\])\n"
        r"-\s*Traceability:\s*(?P<traceability>\[[\s\S]*?\])\n"
        r"-\s*Acceptance Criteria:\s*(?P<acceptance_criteria>\[[\s\S]*?\])",
        flags=re.MULTILINE,
    )

    requirements: List[Dict[str, str]] = []

    for match in pattern.finditer(spec_text):
        requirements.append(
            {
                "requirement_id": match.group("requirement_id").strip(),
                "description": strip_brackets(match.group("description")),
                "source_persona": strip_brackets(match.group("source_persona")),
                "traceability": strip_brackets(match.group("traceability")),
                "acceptance_criteria": strip_brackets(match.group("acceptance_criteria")),
            }
        )

    return requirements


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def count_ambiguous_requirements(requirements: List[Dict[str, str]]) -> int:
    """
    Count how many requirements contain at least one word from AMBIGUOUS_TERMS
    in their description or acceptance criteria.
    """
    ambiguous_count = 0

    for req in requirements:
        # Combine both text fields and check against the term list.
        text = f"{req['description']} {req['acceptance_criteria']}".lower()
        if any(term in text for term in AMBIGUOUS_TERMS):
            ambiguous_count += 1

    return ambiguous_count


def safe_ratio(numerator: int, denominator: int) -> float:
    """Compute a ratio safely, returning 0.0 if the denominator is zero."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


# ---------------------------------------------------------------------------
# Pipeline-aware path resolution
# ---------------------------------------------------------------------------

def get_paths_for_pipeline(pipeline: str) -> Dict[str, Path]:
    """
    Return a dict of file paths for a given pipeline variant.

    Each pipeline ("manual", "auto", "hybrid") uses the same directory
    structure but with a suffix on each filename, e.g.:
        review_groups_auto.json, personas_auto.json, spec_auto.md, etc.
    """
    return {
        "review_groups": DATA_DIR / f"review_groups_{pipeline}.json",
        "personas": PERSONAS_DIR / f"personas_{pipeline}.json",
        "spec": SPEC_DIR / f"spec_{pipeline}.md",
        "tests": TESTS_DIR / f"tests_{pipeline}.json",
        "metrics": METRICS_DIR / f"metrics_{pipeline}.json",
    }


# ---------------------------------------------------------------------------
# Core metric computation
# ---------------------------------------------------------------------------

def compute_metrics_for_pipeline(pipeline: str) -> Dict[str, Any]:
    """
    Load all artefacts for a given pipeline and compute four metrics:

    1. review_coverage_ratio  – fraction of cleaned reviews that appear in
       at least one review group.  Higher is better.

    2. traceability_ratio     – fraction of requirements that reference a
       source persona.  Ideally 1.0 (every requirement traces to a persona).

    3. testability_rate       – fraction of requirements that have at least
       one matching test (by requirement_id).  Ideally 1.0.

    4. ambiguity_ratio        – fraction of requirements containing vague
       terms.  Lower is better.

    Also counts total traceability links across the chain:
       persona→group + requirement→persona + requirement→group + test→requirement.
    """
    paths = get_paths_for_pipeline(pipeline)

    # --- Verify all required files exist ---
    if not REVIEWS_CLEAN_PATH.exists():
        raise FileNotFoundError(f"Missing cleaned dataset: {REVIEWS_CLEAN_PATH}")
    if not paths["review_groups"].exists():
        raise FileNotFoundError(f"Missing review groups file: {paths['review_groups']}")
    if not paths["personas"].exists():
        raise FileNotFoundError(f"Missing personas file: {paths['personas']}")
    if not paths["spec"].exists():
        raise FileNotFoundError(f"Missing spec file: {paths['spec']}")
    if not paths["tests"].exists():
        raise FileNotFoundError(f"Missing tests file: {paths['tests']}")

    # --- Load everything ---
    dataset_size = count_reviews_clean(REVIEWS_CLEAN_PATH)

    review_groups_payload = load_json(paths["review_groups"])
    personas_payload = load_json(paths["personas"])
    tests_payload = load_json(paths["tests"])
    spec_text = paths["spec"].read_text(encoding="utf-8")

    groups = review_groups_payload.get("groups", [])
    personas = personas_payload.get("personas", [])
    tests = tests_payload.get("tests", [])
    requirements = parse_spec_markdown(spec_text)

    persona_count = len(personas)
    requirements_count = len(requirements)
    tests_count = len(tests)

    # ------------------------------------------------------------------
    # METRIC 1: Review coverage
    # What fraction of the cleaned reviews ended up in at least one group?
    # ------------------------------------------------------------------
    covered_review_ids: Set[str] = set()
    for group in groups:
        for rid in group.get("review_ids", []):
            covered_review_ids.add(rid)
    review_coverage_ratio = safe_ratio(len(covered_review_ids), dataset_size)

    # ------------------------------------------------------------------
    # METRIC 2: Traceability ratio
    # What fraction of requirements explicitly name a source persona?
    # ------------------------------------------------------------------
    requirements_with_persona = 0
    requirements_with_group_trace = 0
    for req in requirements:
        if req["source_persona"].strip():
            requirements_with_persona += 1
        if "review group" in req["traceability"].lower():
            requirements_with_group_trace += 1

    traceability_ratio = safe_ratio(requirements_with_persona, requirements_count)

    # ------------------------------------------------------------------
    # METRIC 3: Testability rate
    # What fraction of requirements have at least one test linked to them?
    # ------------------------------------------------------------------
    requirement_ids = {req["requirement_id"] for req in requirements}
    tested_requirement_ids = {
        test.get("requirement_id", "").strip()
        for test in tests
        if test.get("requirement_id", "").strip()
    }
    linked_tested_requirements = requirement_ids.intersection(tested_requirement_ids)
    testability_rate = safe_ratio(len(linked_tested_requirements), requirements_count)

    # ------------------------------------------------------------------
    # Traceability link count (total chain links across all artefacts)
    # ------------------------------------------------------------------
    # persona → group  (each persona that names a derived_from_group)
    persona_to_group_links = sum(
        1 for p in personas if str(p.get("derived_from_group", "")).strip()
    )
    # requirement → persona
    requirement_to_persona_links = requirements_with_persona
    # requirement → group
    requirement_to_group_links = requirements_with_group_trace
    # test → requirement
    test_to_requirement_links = sum(
        1 for test in tests if str(test.get("requirement_id", "")).strip()
    )

    traceability_links = (
        persona_to_group_links
        + requirement_to_persona_links
        + requirement_to_group_links
        + test_to_requirement_links
    )

    # ------------------------------------------------------------------
    # METRIC 4: Ambiguity ratio
    # What fraction of requirements contain vague / untestable language?
    # ------------------------------------------------------------------
    ambiguous_requirements = count_ambiguous_requirements(requirements)
    ambiguity_ratio = safe_ratio(ambiguous_requirements, requirements_count)

    # --- Assemble and save ---
    metrics = {
        "pipeline": pipeline,
        "dataset_size": dataset_size,
        "persona_count": persona_count,
        "requirements_count": requirements_count,
        "tests_count": tests_count,
        "traceability_links": traceability_links,
        "review_coverage_ratio": review_coverage_ratio,
        "traceability_ratio": traceability_ratio,
        "testability_rate": testability_rate,
        "ambiguity_ratio": ambiguity_ratio,
    }

    save_json(paths["metrics"], metrics)
    return metrics


def compute_metrics_summary() -> Dict[str, Any]:
    """
    Collect the individual metrics files for all three pipelines (if they
    exist) into a single summary JSON for easy side-by-side comparison.
    """
    summary = {}

    for pipeline in ["manual", "auto", "hybrid"]:
        metrics_path = METRICS_DIR / f"metrics_{pipeline}.json"
        if metrics_path.exists():
            summary[pipeline] = load_json(metrics_path)

    summary_path = METRICS_DIR / "metrics_summary.json"
    save_json(summary_path, summary)
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    CLI entry point.  Accepts either:
      --pipeline <name>   to compute metrics for one pipeline, or
      --all               to compute all three and produce a summary.
    """
    parser = argparse.ArgumentParser(description="Compute SpecChain pipeline metrics.")
    parser.add_argument(
        "--pipeline",
        choices=["manual", "auto", "hybrid"],
        help="Which pipeline metrics to compute",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compute metrics for manual, auto, and hybrid, then create metrics_summary.json",
    )

    args = parser.parse_args()

    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        # Run all three pipelines; skip any whose files are missing.
        for pipeline in ["manual", "auto", "hybrid"]:
            try:
                metrics = compute_metrics_for_pipeline(pipeline)
                print(f"[DONE] metrics_{pipeline}.json written")
                print(json.dumps(metrics, indent=2))
            except FileNotFoundError as exc:
                print(f"[SKIP] {pipeline}: {exc}")

        summary = compute_metrics_summary()
        print("[DONE] metrics_summary.json written")
        print(json.dumps(summary, indent=2))
        return

    # Default to "auto" if no pipeline is specified.
    pipeline = args.pipeline or "auto"
    metrics = compute_metrics_for_pipeline(pipeline)
    print(f"[DONE] metrics_{pipeline}.json written")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
