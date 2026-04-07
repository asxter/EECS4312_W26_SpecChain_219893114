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

Design choices:
    Instead of sending all 15 requirements to the LLM at once, I send
    one requirement at a time.  This keeps each prompt small and focused,
    so the model produces higher-quality tests and we stay well within
    token limits.  It asks for 2 tests per requirement (30 total), which
    gives enough coverage without being excessive.  After each LLM call
    a normalization step checks that every test has a scenario, steps,
    and an expected result.  If the model returns bad or missing tests,
    a fallback function fills in generic tests based on the requirement's
    acceptance criteria so the final output always has exactly 2 tests
    per requirement.  We reuse the same Groq + Llama 4 Scout setup from
    the earlier scripts.
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

from groq import Groq      # Groq SDK – sends prompts to the Groq cloud inference API

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# LLM model (same across the whole pipeline).
MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"

# Low temperature for deterministic, well-formatted JSON.
TEMPERATURE = 0.2

# Max tokens the model may generate per call.
MAX_COMPLETION_TOKENS = 3000

# How many test scenarios to produce for each requirement.
TESTS_PER_REQUIREMENT = 2

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]                 # project root
SPEC_PATH = ROOT / "spec" / "spec_auto.md"                 # input – from step 06
TESTS_DIR = ROOT / "tests"
TESTS_PATH = TESTS_DIR / "tests_auto.json"                 # output – all generated tests
PROMPTS_DIR = ROOT / "prompts"
PROMPT_AUTO_PATH = PROMPTS_DIR / "prompt_auto.json"        # output – prompt log

# ---------------------------------------------------------------------------
# Prompt template
#
# Double braces {{ }} are literal JSON braces (escaped for str.format()).
# Single braces are filled at runtime with the actual values.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    """Create tests/ and prompts/ directories if they don't exist."""
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def make_groq_client() -> Groq:
    """Instantiate a Groq client, failing early if no API key is set."""
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        raise EnvironmentError(
            "Groq API key is missing. Paste it into GROQ_API_KEY at the top of src/07_tests_generate.py"
        )
    return Groq(api_key=GROQ_API_KEY)


def load_text(path: Path) -> str:
    """Read an entire file as a string."""
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def load_json(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write a dict to a pretty-printed JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_json_from_text(text: str) -> Any:
    """
    Extract JSON from LLM output.  Tries three strategies:
      1. Parse the whole string directly.
      2. Look for a ```json … ``` fenced code block.
      3. Find the outermost { … } substring.
    """
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: fenced code block
    code_block_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate = code_block_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 3: outermost braces
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
    """Send a system + user message to Groq and parse the response as JSON."""
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
    """Remove the outer [ ] brackets that the Markdown spec wraps field values in."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1].strip()
    return value


def parse_spec_markdown(spec_text: str) -> List[Dict[str, str]]:
    """
    Parse spec/spec_auto.md back into a list of requirement dicts.

    The Markdown file written by step 06 uses a predictable format:
        # Requirement ID: FR_auto_1
        - Description: [The system shall …]
        - Source Persona: [Persona Name]
        - Traceability: [Derived from review group A1]
        - Acceptance Criteria: [Given …, When …, Then …]

    This regex captures each field (including the square brackets) and
    strip_wrapping_brackets() removes the brackets afterward.
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
    """
    Generate a safe, generic test when the LLM fails to produce a valid one.

    Two variants are available:
      variant 1 – "Main Success Path": basic happy-path test.
      variant 2 – "Repeat Execution": checks the feature works consistently.

    The expected result is pulled directly from the requirement's acceptance
    criteria so the test still traces back meaningfully.
    """
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

    # Pick the variant that matches the current gap (cycles if more needed).
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
    """
    Validate and clean up the tests the LLM returned for one requirement.

    - Drops any test that is missing a scenario, steps, or expected result.
    - Keeps at most TESTS_PER_REQUIREMENT valid tests.
    - If the LLM returned fewer valid tests than needed, fills the gap
      with fallback tests.
    - Assigns sequential test IDs (T_auto_1, T_auto_2, …) globally.
    """
    requirement_id = requirement["requirement_id"]
    normalized: List[Dict[str, Any]] = []

    for raw in raw_tests:
        scenario = str(raw.get("scenario", "")).strip()
        steps = raw.get("steps", [])
        expected_result = str(raw.get("expected_result", "")).strip()

        # Skip incomplete tests.
        if not scenario:
            continue
        if not isinstance(steps, list) or len(steps) == 0:
            continue
        if not expected_result:
            continue

        normalized.append(
            {
                "test_id": "",                # filled below
                "requirement_id": requirement_id,
                "scenario": scenario,
                "steps": [str(step).strip() for step in steps if str(step).strip()],
                "expected_result": expected_result,
            }
        )

        # Stop once we have enough valid tests for this requirement.
        if len(normalized) >= TESTS_PER_REQUIREMENT:
            break

    # Pad with fallback tests if the LLM didn't return enough.
    while len(normalized) < TESTS_PER_REQUIREMENT:
        normalized.append(
            fallback_test(
                requirement=requirement,
                requirement_id=requirement_id,
                test_id="",                   # filled below
                variant=len(normalized) + 1,
            )
        )

    # Assign globally sequential test IDs.
    for i, test in enumerate(normalized, start=start_test_number):
        test["test_id"] = f"T_auto_{i}"

    return normalized


def update_prompt_log() -> None:
    """
    Append the test-generation prompt and settings to the shared prompt log
    so all prompts from every pipeline step are in one file.
    """
    payload: Dict[str, Any] = {}
    if PROMPT_AUTO_PATH.exists():
        payload = load_json(PROMPT_AUTO_PATH)

    payload["test_generation"] = {
        "model": MODEL_NAME,
        "tests_per_requirement": TESTS_PER_REQUIREMENT,
        "prompt": TEST_PROMPT.strip(),
    }

    save_json(PROMPT_AUTO_PATH, payload)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    End-to-end test generation:
      1. Load and parse the Markdown spec from step 06.
      2. For each requirement, ask the LLM to generate test scenarios.
      3. Normalize / validate; fill fallbacks for any gaps.
      4. Save all tests to tests/tests_auto.json.
      5. Log the prompt to prompts/prompt_auto.json.
    """
    ensure_dirs()

    # --- Load spec ---
    print("Loading automated specification...")
    spec_text = load_text(SPEC_PATH)

    print("Parsing requirements from spec/spec_auto.md...")
    requirements = parse_spec_markdown(spec_text)
    print(f"Parsed {len(requirements)} requirements from {SPEC_PATH}")

    # --- Connect to Groq ---
    print("Connecting to Groq...")
    client = make_groq_client()

    system_prompt = (
        "You are a precise software test generator. "
        "Return valid JSON only. Do not add markdown or explanation outside JSON."
    )

    # --- Generate tests one requirement at a time ---
    all_tests: List[Dict[str, Any]] = []
    next_test_number = 1      # global counter for T_auto_1, T_auto_2, …

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

        # Validate, pad with fallbacks if needed, assign IDs.
        normalized = normalize_tests_for_requirement(
            raw_tests=raw_tests,
            requirement=requirement,
            start_test_number=next_test_number,
        )
        all_tests.extend(normalized)
        next_test_number += len(normalized)

    # --- Save ---
    tests_payload = {"tests": all_tests}

    print(f"Saving {TESTS_PATH} ...")
    save_json(TESTS_PATH, tests_payload)

    print(f"Updating {PROMPT_AUTO_PATH} ...")
    update_prompt_log()

    # --- Summary ---
    print("Done.")
    print(f"- Tests saved to: {TESTS_PATH}")
    print(f"- Prompt log updated at: {PROMPT_AUTO_PATH}")
    print(f"- Total tests generated: {len(all_tests)}")


if __name__ == "__main__":
    main()
