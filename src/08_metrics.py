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
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PERSONAS_DIR = ROOT / "personas"
SPEC_DIR = ROOT / "spec"
TESTS_DIR = ROOT / "tests"
METRICS_DIR = ROOT / "metrics"

REVIEWS_CLEAN_PATH = DATA_DIR / "reviews_clean.jsonl"

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


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def count_reviews_clean(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def parse_spec_markdown(spec_text: str) -> List[Dict[str, str]]:
    """
    Parses requirements of the form:

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


def strip_brackets(value: str) -> str:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1].strip()
    return value


def count_ambiguous_requirements(requirements: List[Dict[str, str]]) -> int:
    ambiguous_count = 0

    for req in requirements:
        text = f"{req['description']} {req['acceptance_criteria']}".lower()
        if any(term in text for term in AMBIGUOUS_TERMS):
            ambiguous_count += 1

    return ambiguous_count


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def get_paths_for_pipeline(pipeline: str) -> Dict[str, Path]:
    return {
        "review_groups": DATA_DIR / f"review_groups_{pipeline}.json",
        "personas": PERSONAS_DIR / f"personas_{pipeline}.json",
        "spec": SPEC_DIR / f"spec_{pipeline}.md",
        "tests": TESTS_DIR / f"tests_{pipeline}.json",
        "metrics": METRICS_DIR / f"metrics_{pipeline}.json",
    }


def compute_metrics_for_pipeline(pipeline: str) -> Dict[str, Any]:
    paths = get_paths_for_pipeline(pipeline)

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

    # Review coverage
    covered_review_ids: Set[str] = set()
    for group in groups:
        for rid in group.get("review_ids", []):
            covered_review_ids.add(rid)
    review_coverage_ratio = safe_ratio(len(covered_review_ids), dataset_size)

    # Traceability ratio:
    # proportion of requirements that explicitly reference a persona
    requirements_with_persona = 0
    requirements_with_group_trace = 0
    for req in requirements:
        if req["source_persona"].strip():
            requirements_with_persona += 1
        if "review group" in req["traceability"].lower():
            requirements_with_group_trace += 1

    traceability_ratio = safe_ratio(requirements_with_persona, requirements_count)

    # Testability rate:
    requirement_ids = {req["requirement_id"] for req in requirements}
    tested_requirement_ids = {
        test.get("requirement_id", "").strip()
        for test in tests
        if test.get("requirement_id", "").strip()
    }
    linked_tested_requirements = requirement_ids.intersection(tested_requirement_ids)
    testability_rate = safe_ratio(len(linked_tested_requirements), requirements_count)

    # Traceability links:
    # conservative count:
    # personas -> groups
    # requirements -> personas
    # requirements -> groups
    # tests -> requirements
    persona_to_group_links = sum(
        1 for p in personas if str(p.get("derived_from_group", "")).strip()
    )
    requirement_to_persona_links = requirements_with_persona
    requirement_to_group_links = requirements_with_group_trace
    test_to_requirement_links = sum(
        1 for test in tests if str(test.get("requirement_id", "")).strip()
    )

    traceability_links = (
        persona_to_group_links
        + requirement_to_persona_links
        + requirement_to_group_links
        + test_to_requirement_links
    )

    # Ambiguity ratio
    ambiguous_requirements = count_ambiguous_requirements(requirements)
    ambiguity_ratio = safe_ratio(ambiguous_requirements, requirements_count)

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
    summary = {}

    for pipeline in ["manual", "auto", "hybrid"]:
        metrics_path = METRICS_DIR / f"metrics_{pipeline}.json"
        if metrics_path.exists():
            summary[pipeline] = load_json(metrics_path)

    summary_path = METRICS_DIR / "metrics_summary.json"
    save_json(summary_path, summary)
    return summary


def main() -> None:
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

    pipeline = args.pipeline or "auto"
    metrics = compute_metrics_for_pipeline(pipeline)
    print(f"[DONE] metrics_{pipeline}.json written")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
