
"""generates structured specs from personas"""
#!/usr/bin/env python3
from __future__ import annotations
"""
src/06_spec_generate.py

Automated specification generation for EECS 4312 Task 4.3.

Reads:
- personas/personas_auto.json

Writes:
- spec/spec_auto.md

Optional:
- updates prompts/prompt_auto.json with the spec-generation prompt
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
MAX_COMPLETION_TOKENS = 4000
N_REQUIREMENTS = 15

ROOT = Path(__file__).resolve().parents[1]
PERSONAS_PATH = ROOT / "personas" / "personas_auto.json"
SPEC_DIR = ROOT / "spec"
SPEC_PATH = SPEC_DIR / "spec_auto.md"
PROMPTS_DIR = ROOT / "prompts"
PROMPT_AUTO_PATH = PROMPTS_DIR / "prompt_auto.json"

SPEC_PROMPT = """
You are generating software requirements from personas for a requirements engineering course project.

Your job:
- Generate exactly {n_requirements} functional requirements
- Base every requirement only on the provided personas
- Do not invent unsupported capabilities
- Requirements must be specific, testable, and written as system behavior
- Avoid vague language such as "easy", "better", "fast", "user-friendly", "seamless", unless you define it measurably
- Each requirement must be traceable to exactly one persona and exactly one review group
- Acceptance criteria must be written in Given / When / Then form

Return STRICT JSON only with this schema:
{{
  "requirements": [
    {{
      "requirement_id": "FR_auto_1",
      "description": "The system shall ...",
      "source_persona_id": "P_auto_1",
      "source_persona_name": "Persona Name",
      "traceability": "Derived from review group A1",
      "acceptance_criteria": "Given ..., When ..., Then ..."
    }}
  ]
}}

Personas:
{personas_json}
"""


# -----------------------------
# Helpers
# -----------------------------

def ensure_dirs() -> None:
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def make_groq_client() -> Groq:
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        raise EnvironmentError(
            "Groq API key is missing. Paste it into GROQ_API_KEY at the top of src/06_spec_generate.py"
        )
    return Groq(api_key=GROQ_API_KEY)


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


def normalize_requirements(raw_requirements: List[Dict[str, Any]], personas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    persona_lookup = {p["id"]: p for p in personas}
    normalized: List[Dict[str, Any]] = []

    for idx, req in enumerate(raw_requirements, start=1):
        rid = f"FR_auto_{idx}"

        source_persona_id = req.get("source_persona_id", "")
        if source_persona_id not in persona_lookup:
            # fallback in case model misses or invents persona IDs
            fallback_persona = personas[(idx - 1) % len(personas)]
            source_persona_id = fallback_persona["id"]

        source_persona = persona_lookup[source_persona_id]
        source_persona_name = source_persona.get("name", req.get("source_persona_name", source_persona_id))
        derived_group = source_persona.get("derived_from_group", "UNKNOWN_GROUP")

        description = str(req.get("description", "")).strip()
        acceptance_criteria = str(req.get("acceptance_criteria", "")).strip()

        if not description:
            description = f"The system shall support behavior required by {source_persona_name}."
        if not description.lower().startswith("the system shall"):
            description = "The system shall " + description[0].lower() + description[1:] if description else "The system shall support the required behavior."

        if not acceptance_criteria:
            acceptance_criteria = "Given the required preconditions are met, when the user performs the relevant action, then the system shall satisfy the requirement."

        normalized.append(
            {
                "requirement_id": rid,
                "description": description,
                "source_persona_id": source_persona_id,
                "source_persona_name": source_persona_name,
                "traceability": f"Derived from review group {derived_group}",
                "acceptance_criteria": acceptance_criteria,
            }
        )

    return normalized


def render_spec_md(requirements: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []

    for req in requirements:
        block = [
            f"# Requirement ID: {req['requirement_id']}",
            "",
            f"- Description: [{req['description']}]",
            f"- Source Persona: [{req['source_persona_name']}]",
            f"- Traceability: [{req['traceability']}]",
            f"- Acceptance Criteria: [{req['acceptance_criteria']}]",
            "",
        ]
        blocks.append("\n".join(block))

    return "\n".join(blocks).rstrip() + "\n"


def update_prompt_log() -> None:
    payload: Dict[str, Any] = {}
    if PROMPT_AUTO_PATH.exists():
        payload = load_json(PROMPT_AUTO_PATH)

    payload["spec_generation"] = {
        "model": MODEL_NAME,
        "n_requirements": N_REQUIREMENTS,
        "prompt": SPEC_PROMPT.strip(),
    }

    save_json(PROMPT_AUTO_PATH, payload)


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    ensure_dirs()

    print("Loading automated personas...")
    personas_payload = load_json(PERSONAS_PATH)
    personas = personas_payload.get("personas", [])
    if not personas:
        raise ValueError(f"No personas found in {PERSONAS_PATH}")

    print(f"Loaded {len(personas)} automated personas from {PERSONAS_PATH}")

    print("Connecting to Groq...")
    client = make_groq_client()

    system_prompt = (
        "You are a precise software requirements generator. "
        "Return valid JSON only. Do not add markdown or explanation outside JSON."
    )

    print(f"Generating {N_REQUIREMENTS} automated requirements with Groq...")
    result = groq_json_completion(
        client=client,
        system_prompt=system_prompt,
        user_prompt=SPEC_PROMPT.format(
            n_requirements=N_REQUIREMENTS,
            personas_json=json.dumps(personas, indent=2, ensure_ascii=False),
        ),
    )

    raw_requirements = result.get("requirements", [])
    if not raw_requirements:
        raise ValueError("Model returned no requirements.")

    # Force exactly N_REQUIREMENTS
    raw_requirements = raw_requirements[:N_REQUIREMENTS]
    while len(raw_requirements) < N_REQUIREMENTS:
        raw_requirements.append({})

    requirements = normalize_requirements(raw_requirements, personas)

    spec_md = render_spec_md(requirements)

    print(f"Saving {SPEC_PATH} ...")
    with SPEC_PATH.open("w", encoding="utf-8") as f:
        f.write(spec_md)

    print(f"Updating {PROMPT_AUTO_PATH} ...")
    update_prompt_log()

    print("Done.")
    print(f"- Specification saved to: {SPEC_PATH}")
    print(f"- Prompt log updated at: {PROMPT_AUTO_PATH}")


if __name__ == "__main__":
    main()
