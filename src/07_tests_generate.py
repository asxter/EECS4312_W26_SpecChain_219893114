"""generates tests from specs"""
#!/usr/bin/env python3
"""
src/07_tests_generate.py

Automated validation test generation for EECS 4312 Task 4.4.

Reads:
- spec/spec_auto.md

Writes:
- tests/tests_auto.json

Optional:
- updates prompts/prompt_auto.json with the test-generation prompt
"""

# =========================================================
# HARD-CODED GROQ API KEY
# Paste your key locally between the quotes below.
# Do not commit this version to GitHub.
# =========================================================
GROQ_API_KEY = "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"

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from groq import Groq

# -----------------------------
# Configuration
# -----------------------------

MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 3000
TESTS_PER_REQUIREMENT = 2

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "spec" / "spec_auto.md"
TESTS_DIR = ROOT / "tests"
TESTS_PATH = TESTS_DIR / "tests_auto.json"
PROMPTS_DIR = ROOT / "prompts"
PROMPT_AUTO_PATH = PROMPTS_DIR / "prompt_auto.json"

TEST_PROMPT = """
You are generating validation tests for a software requirement.

Your job:
- Generate exactly {tests_per_requirement} test scenarios for the requirement
- Every test must validate the requirement directly
- Tests must be clear, realistic, and executable
- Steps must be concrete and ordered
- expected_result must directly reflect the requirement's acceptance criteria
- Do not invent unrelated system behavior

Return STRICT JSON only with this schema:
{{
  "tests": [
    {{
      "test_id": "TEMP_1",
      "requirement_id": "{requirement_id}",
      "scenario": "short scenario title",
      "steps": [
        "step 1",
        "step 2",
        "step 3"
      ],
      "expected_result": "clear expected outcome"
    }}
  ]
}}

Requirement:
{requirement_json}
"""


def ensure_dirs() -> None:
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def make_groq_client() -> Groq:
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        raise EnvironmentError(
            "Groq API key is missing. Paste it into GROQ_API_KEY at the top of src/07_tests_generate.py"
        )
    return Groq(api_key=GROQ_API_KEY)


def load_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_json_from_text(text: str) -> Any:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate = code_block_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    first_obj = text.find("{")
    last_obj = text.rfind("}")
    if first_obj != -1 and last_obj != -1 and last_obj > first_obj:
        candidate = text[first_obj:last_obj + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from model output:\n{text[:1500]}")


def groq_json_completion(client: Groq, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    return parse_json_from_text(content)


def strip_wrapping_brackets(value: str) -> str:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1].strip()
    return value


def parse_spec_markdown(spec_text: str) -> List[Dict[str, str]]:
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
                "description": strip_wrapping_brackets(match.group("description")),
                "source_persona": strip_wrapping_brackets(match.group("source_persona")),
                "traceability": strip_wrapping_brackets(match.group("traceability")),
                "acceptance_criteria": strip_wrapping_brackets(match.group("acceptance_criteria")),
            }
        )

    if not requirements:
        raise ValueError(
            f"No requirements were parsed from {SPEC_PATH}. "
            "Check that spec/spec_auto.md follows the expected markdown format."
        )

    return requirements


def fallback_test(requirement: Dict[str, str], requirement_id: str, test_id: str, variant: int) -> Dict[str, Any]:
    description = requirement["description"]
    acceptance = requirement["acceptance_criteria"]

    fallback_scenarios = [
        {
            "scenario": f"{requirement_id} Main Success Path",
            "steps": [
                "Open the application and navigate to the feature related to the requirement",
                "Provide the required input or perform the relevant user action",
                "Submit the action and observe the system response",
            ],
            "expected_result": acceptance,
        },
        {
            "scenario": f"{requirement_id} Repeat Execution",
            "steps": [
                "Open the application and navigate to the same feature again",
                "Repeat the requirement-related action using valid input",
                "Observe whether the requirement is still satisfied consistently",
            ],
            "expected_result": f"The system continues to satisfy the requirement: {description}",
        },
    ]

    chosen = fallback_scenarios[(variant - 1) % len(fallback_scenarios)]
    return {
        "test_id": test_id,
        "requirement_id": requirement_id,
        "scenario": chosen["scenario"],
        "steps": chosen["steps"],
        "expected_result": chosen["expected_result"],
    }


def normalize_tests_for_requirement(
    raw_tests: List[Dict[str, Any]],
    requirement: Dict[str, str],
    start_test_number: int,
) -> List[Dict[str, Any]]:
    requirement_id = requirement["requirement_id"]
    normalized: List[Dict[str, Any]] = []

    for raw in raw_tests:
        scenario = str(raw.get("scenario", "")).strip()
        steps = raw.get("steps", [])
        expected_result = str(raw.get("expected_result", "")).strip()

        if not scenario:
            continue
        if not isinstance(steps, list) or len(steps) == 0:
            continue
        if not expected_result:
            continue

        normalized.append(
            {
                "test_id": "",
                "requirement_id": requirement_id,
                "scenario": scenario,
                "steps": [str(step).strip() for step in steps if str(step).strip()],
                "expected_result": expected_result,
            }
        )

        if len(normalized) >= TESTS_PER_REQUIREMENT:
            break

    while len(normalized) < TESTS_PER_REQUIREMENT:
        normalized.append(
            fallback_test(
                requirement=requirement,
                requirement_id=requirement_id,
                test_id="",
                variant=len(normalized) + 1,
            )
        )

    for i, test in enumerate(normalized, start=start_test_number):
        test["test_id"] = f"T_auto_{i}"

    return normalized


def update_prompt_log() -> None:
    payload: Dict[str, Any] = {}
    if PROMPT_AUTO_PATH.exists():
        payload = load_json(PROMPT_AUTO_PATH)

    payload["test_generation"] = {
        "model": MODEL_NAME,
        "tests_per_requirement": TESTS_PER_REQUIREMENT,
        "prompt": TEST_PROMPT.strip(),
    }

    save_json(PROMPT_AUTO_PATH, payload)


def main() -> None:
    ensure_dirs()

    print("Loading automated specification...")
    spec_text = load_text(SPEC_PATH)

    print("Parsing requirements from spec/spec_auto.md...")
    requirements = parse_spec_markdown(spec_text)
    print(f"Parsed {len(requirements)} requirements from {SPEC_PATH}")

    print("Connecting to Groq...")
    client = make_groq_client()

    system_prompt = (
        "You are a precise software test generator. "
        "Return valid JSON only. Do not add markdown or explanation outside JSON."
    )

    all_tests: List[Dict[str, Any]] = []
    next_test_number = 1

    for requirement in requirements:
        requirement_id = requirement["requirement_id"]
        print(f"Generating tests for {requirement_id} ...")

        result = groq_json_completion(
            client=client,
            system_prompt=system_prompt,
            user_prompt=TEST_PROMPT.format(
                tests_per_requirement=TESTS_PER_REQUIREMENT,
                requirement_id=requirement_id,
                requirement_json=json.dumps(requirement, indent=2, ensure_ascii=False),
            ),
        )

        raw_tests = result.get("tests", [])
        normalized = normalize_tests_for_requirement(
            raw_tests=raw_tests,
            requirement=requirement,
            start_test_number=next_test_number,
        )
        all_tests.extend(normalized)
        next_test_number += len(normalized)

    tests_payload = {"tests": all_tests}

    print(f"Saving {TESTS_PATH} ...")
    save_json(TESTS_PATH, tests_payload)

    print(f"Updating {PROMPT_AUTO_PATH} ...")
    update_prompt_log()

    print("Done.")
    print(f"- Tests saved to: {TESTS_PATH}")
    print(f"- Prompt log updated at: {PROMPT_AUTO_PATH}")
    print(f"- Total tests generated: {len(all_tests)}")


if __name__ == "__main__":
    main()
