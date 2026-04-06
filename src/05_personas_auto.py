#!/usr/bin/env python3
"""
src/05_personas_auto.py

Automated review grouping + persona generation for EECS 4312 Task 4.

Outputs:
- data/review_groups_auto.json
- personas/personas_auto.json
- prompts/prompt_auto.json
"""

from __future__ import annotations

# =========================================================
# HARD-CODED GROQ API KEY
# Paste your key locally between the quotes below.
# Do not commit this version to GitHub.
# =========================================================
GROQ_API_KEY = "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"

import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from groq import Groq
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

# -----------------------------
# Configuration
# -----------------------------

MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
RANDOM_SEED = 42

# Over-cluster first, then merge down using Groq
N_MICRO_CLUSTERS = 18
N_FINAL_GROUPS = 6

# Number of representative reviews to show the LLM per cluster
N_REPRESENTATIVES_PER_MICRO = 5
N_EXAMPLE_REVIEWS_PER_FINAL = 5

# TF-IDF settings
MAX_FEATURES = 5000
NGRAM_RANGE = (1, 2)
MIN_DF = 2
MAX_DF = 0.90

# Groq generation settings
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 2500

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PERSONAS_DIR = ROOT / "personas"
PROMPTS_DIR = ROOT / "prompts"

REVIEWS_PATH = DATA_DIR / "reviews_clean.jsonl"
REVIEW_GROUPS_AUTO_PATH = DATA_DIR / "review_groups_auto.json"
PERSONAS_AUTO_PATH = PERSONAS_DIR / "personas_auto.json"
PROMPT_AUTO_PATH = PROMPTS_DIR / "prompt_auto.json"

# -----------------------------
# Prompt templates
# IMPORTANT: all literal JSON braces are escaped as {{ }}
# so Python .format(...) will not crash.
# -----------------------------

MICRO_CLUSTER_THEME_PROMPT = """
You are labeling a cluster of app reviews.

Your job:
- infer ONE clear theme for the cluster
- keep the theme short and specific
- do not use vague themes like "general issues"
- do not mention the clustering process
- base your answer only on the provided evidence

Return STRICT JSON only with this schema:
{{
  "theme": "short theme label",
  "summary": "1-2 sentence explanation of the pattern in the reviews"
}}

Cluster metadata:
{cluster_metadata}
"""

MERGE_MICRO_CLUSTERS_PROMPT = """
You are given automatically generated micro-clusters of app reviews.

Your job:
- merge these micro-clusters into exactly {n_final_groups} final groups
- each final group must represent a coherent, user-meaningful theme
- groups should be similar to a manual requirements-engineering grouping, not random ML buckets
- use all micro-clusters exactly once
- do not leave any micro-cluster unassigned
- do not assign any micro-cluster to more than one final group

Return STRICT JSON only with this schema:
{{
  "groups": [
    {{
      "group_id": "A1",
      "theme": "clear final theme",
      "micro_cluster_ids": ["M1", "M4"]
    }}
  ]
}}

Micro-clusters:
{micro_clusters_json}
"""

PERSONA_PROMPT = """
You are generating a persona from an automatically grouped set of app reviews.

Rules:
- Base the persona only on the provided evidence
- Do not invent unsupported details
- Make the persona specific, realistic, and requirements-oriented
- Keep goals, pain points, context, and constraints grounded in the evidence
- evidence_reviews must contain review IDs only, not full review text

Return STRICT JSON only with this schema:
{{
  "id": "{persona_id}",
  "name": "persona name",
  "description": "1-2 sentence description",
  "derived_from_group": "{group_id}",
  "goals": ["..."],
  "pain_points": ["..."],
  "context": ["..."],
  "constraints": ["..."],
  "evidence_reviews": ["review_id_1", "review_id_2", "review_id_3"]
}}

Group theme:
{group_theme}

Representative evidence:
{group_examples_json}
"""

# -----------------------------
# Data classes
# -----------------------------


@dataclass
class Review:
    review_id: str
    review_text_clean: str
    review_text_raw: str


@dataclass
class MicroCluster:
    micro_id: str
    member_indices: List[int]
    review_ids: List[str]
    representative_indices: List[int]
    representative_ids: List[str]
    representative_reviews_raw: List[str]
    top_terms: List[str]
    theme: str = ""
    summary: str = ""


# -----------------------------
# Utility helpers
# -----------------------------


def ensure_output_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def load_reviews(path: Path) -> List[Review]:
    reviews: List[Review] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            reviews.append(
                Review(
                    review_id=obj["review_id"],
                    review_text_clean=obj["review_text_clean"],
                    review_text_raw=obj.get("review_text_raw", obj["review_text_clean"]),
                )
            )
    if not reviews:
        raise ValueError(f"No reviews found in {path}")
    return reviews


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_json_from_text(text: str) -> Any:
    """
    Extract JSON from LLM output robustly.
    Supports plain JSON or JSON inside code fences.
    """
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Remove fenced code block if present
    code_block_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate = code_block_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Fallback: try substring from first { to last }
    first_obj = text.find("{")
    last_obj = text.rfind("}")
    if first_obj != -1 and last_obj != -1 and last_obj > first_obj:
        candidate = text[first_obj:last_obj + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from model output:\n{text[:1200]}")


def sanitize_group_theme(theme: str) -> str:
    theme = re.sub(r"\s+", " ", theme.strip())
    return theme[:120] if theme else "Unlabeled review group"


# -----------------------------
# Groq helpers
# -----------------------------


def make_groq_client() -> Groq:
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        raise EnvironmentError(
            "Groq API key is missing. Paste it into GROQ_API_KEY at the top of src/05_personas_auto.py"
        )
    return Groq(api_key=GROQ_API_KEY)


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


# -----------------------------
# Clustering helpers
# -----------------------------


def build_tfidf_matrix(reviews: List[Review]) -> Tuple[TfidfVectorizer, Any]:
    vectorizer = TfidfVectorizer(
        max_features=MAX_FEATURES,
        ngram_range=NGRAM_RANGE,
        min_df=MIN_DF,
        max_df=MAX_DF,
        strip_accents="unicode",
    )
    X = vectorizer.fit_transform([r.review_text_clean for r in reviews])
    return vectorizer, X


def create_micro_clusters(
    reviews: List[Review],
    vectorizer: TfidfVectorizer,
    X: Any,
    n_micro_clusters: int = N_MICRO_CLUSTERS,
) -> List[MicroCluster]:
    n_micro_clusters = min(n_micro_clusters, len(reviews))
    km = KMeans(
        n_clusters=n_micro_clusters,
        random_state=RANDOM_SEED,
        n_init=10,
    )
    labels = km.fit_predict(X)
    centers = km.cluster_centers_
    feature_names = np.array(vectorizer.get_feature_names_out())

    members_by_cluster: Dict[int, List[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        members_by_cluster[int(label)].append(idx)

    micro_clusters: List[MicroCluster] = []

    for cluster_idx in sorted(members_by_cluster.keys()):
        member_indices = members_by_cluster[cluster_idx]
        member_matrix = X[member_indices]
        center = centers[cluster_idx]

        # Representative review indices: nearest to centroid
        distances = []
        for local_row, review_idx in enumerate(member_indices):
            row = member_matrix[local_row].toarray().ravel()
            dist = float(np.linalg.norm(row - center))
            distances.append((dist, review_idx))
        distances.sort(key=lambda x: x[0])

        representative_indices = [
            review_idx for _, review_idx in distances[:N_REPRESENTATIVES_PER_MICRO]
        ]

        # Top terms from centroid weights
        top_term_indices = np.argsort(center)[::-1][:10]
        top_terms = [term for term in feature_names[top_term_indices] if term.strip()]

        micro_id = f"M{cluster_idx + 1}"
        micro_clusters.append(
            MicroCluster(
                micro_id=micro_id,
                member_indices=member_indices,
                review_ids=[reviews[i].review_id for i in member_indices],
                representative_indices=representative_indices,
                representative_ids=[reviews[i].review_id for i in representative_indices],
                representative_reviews_raw=[reviews[i].review_text_raw for i in representative_indices],
                top_terms=top_terms,
            )
        )

    return micro_clusters


# -----------------------------
# LLM labeling + merging
# -----------------------------


def label_micro_clusters(client: Groq, micro_clusters: List[MicroCluster]) -> None:
    system_prompt = (
        "You are a precise review-theme labeling assistant. "
        "Return valid JSON only. Do not add markdown or explanation outside JSON."
    )

    for cluster in micro_clusters:
        cluster_metadata = {
            "micro_id": cluster.micro_id,
            "cluster_size": len(cluster.review_ids),
            "top_terms": cluster.top_terms,
            "representative_review_ids": cluster.representative_ids,
            "representative_reviews": cluster.representative_reviews_raw,
        }

        result = groq_json_completion(
            client=client,
            system_prompt=system_prompt,
            user_prompt=MICRO_CLUSTER_THEME_PROMPT.format(
                cluster_metadata=json.dumps(cluster_metadata, indent=2, ensure_ascii=False)
            ),
        )

        cluster.theme = sanitize_group_theme(result.get("theme", "").strip())
        cluster.summary = result.get("summary", "").strip()


def merge_micro_clusters_into_final_groups(
    client: Groq,
    micro_clusters: List[MicroCluster],
    n_final_groups: int = N_FINAL_GROUPS,
) -> List[Dict[str, Any]]:
    system_prompt = (
        "You are a precise review-group consolidation assistant. "
        "Return valid JSON only. Use every micro-cluster exactly once."
    )

    compact_micro_clusters = []
    for c in micro_clusters:
        compact_micro_clusters.append(
            {
                "micro_id": c.micro_id,
                "theme": c.theme,
                "summary": c.summary,
                "cluster_size": len(c.review_ids),
                "top_terms": c.top_terms[:6],
                "representative_review_ids": c.representative_ids,
                "representative_reviews": c.representative_reviews_raw[:3],
            }
        )

    result = groq_json_completion(
        client=client,
        system_prompt=system_prompt,
        user_prompt=MERGE_MICRO_CLUSTERS_PROMPT.format(
            n_final_groups=n_final_groups,
            micro_clusters_json=json.dumps(compact_micro_clusters, indent=2, ensure_ascii=False),
        ),
    )

    groups = result.get("groups", [])

    # If model returns wrong number of groups, create/trim to expected count
    while len(groups) < n_final_groups:
        groups.append(
            {
                "group_id": f"A{len(groups)+1}",
                "theme": f"Auto Group {len(groups)+1}",
                "micro_cluster_ids": [],
            }
        )
    groups = groups[:n_final_groups]

    expected_ids = [c.micro_id for c in micro_clusters]
    expected_set = set(expected_ids)

    # Step 1: remove duplicates and invalid IDs while preserving order
    used = set()
    cleaned_groups = []
    for i, g in enumerate(groups, start=1):
        raw_ids = g.get("micro_cluster_ids", [])
        cleaned_ids = []
        for mid in raw_ids:
            if mid in expected_set and mid not in used:
                cleaned_ids.append(mid)
                used.add(mid)

        cleaned_groups.append(
            {
                "group_id": g.get("group_id", f"A{i}"),
                "theme": g.get("theme", f"Auto Group {i}"),
                "micro_cluster_ids": cleaned_ids,
            }
        )

    # Step 2: find missing micro-clusters
    missing = [mid for mid in expected_ids if mid not in used]

    # Step 3: assign missing IDs to the currently smallest groups
    for mid in missing:
        smallest_group = min(cleaned_groups, key=lambda g: len(g["micro_cluster_ids"]))
        smallest_group["micro_cluster_ids"].append(mid)

    return cleaned_groups
def assemble_final_review_groups(
    reviews: List[Review],
    micro_clusters: List[MicroCluster],
    merge_groups: List[Dict[str, Any]],
) -> Dict[str, Any]:
    micro_by_id = {c.micro_id: c for c in micro_clusters}
    groups_out: List[Dict[str, Any]] = []

    for idx, merged in enumerate(merge_groups, start=1):
        group_id = merged.get("group_id", f"A{idx}")
        theme = sanitize_group_theme(merged.get("theme", f"Auto Group {idx}"))
        micro_ids = merged["micro_cluster_ids"]

        review_ids: List[str] = []
        representative_bundle: List[Tuple[str, str]] = []

        for micro_id in micro_ids:
            c = micro_by_id[micro_id]
            review_ids.extend(c.review_ids)
            representative_bundle.extend(
                list(zip(c.representative_ids, c.representative_reviews_raw))
            )

        seen_ids = set()
        dedup_review_ids = []
        for rid in review_ids:
            if rid not in seen_ids:
                seen_ids.add(rid)
                dedup_review_ids.append(rid)

        seen_example_texts = set()
        example_reviews = []
        for _, review_text in representative_bundle:
            if review_text not in seen_example_texts:
                seen_example_texts.add(review_text)
                example_reviews.append(review_text)
            if len(example_reviews) >= N_EXAMPLE_REVIEWS_PER_FINAL:
                break

        groups_out.append(
            {
                "group_id": group_id,
                "theme": theme,
                "review_ids": dedup_review_ids,
                "example_reviews": example_reviews,
            }
        )

    return {"groups": groups_out}


# -----------------------------
# Persona generation
# -----------------------------


def generate_personas_auto(
    client: Groq,
    review_groups_auto: Dict[str, Any],
    reviews: List[Review],
) -> Dict[str, Any]:
    review_lookup = {r.review_id: r for r in reviews}
    personas: List[Dict[str, Any]] = []

    system_prompt = (
        "You are a strict JSON persona generator for software requirements engineering. "
        "Return valid JSON only. Keep persona details grounded in the provided evidence."
    )

    for idx, group in enumerate(review_groups_auto["groups"], start=1):
        group_id = group["group_id"]
        persona_id = f"P_auto_{idx}"

        representative_examples = []
        for rid in group["review_ids"][:8]:
            review = review_lookup[rid]
            representative_examples.append(
                {
                    "review_id": rid,
                    "review_text_raw": review.review_text_raw,
                }
            )

        persona = groq_json_completion(
            client=client,
            system_prompt=system_prompt,
            user_prompt=PERSONA_PROMPT.format(
                persona_id=persona_id,
                group_id=group_id,
                group_theme=group["theme"],
                group_examples_json=json.dumps(representative_examples, indent=2, ensure_ascii=False),
            ),
        )

        persona["id"] = persona_id
        persona["derived_from_group"] = group_id

        if not isinstance(persona.get("goals", []), list):
            persona["goals"] = []
        if not isinstance(persona.get("pain_points", []), list):
            persona["pain_points"] = []
        if not isinstance(persona.get("context", []), list):
            persona["context"] = []
        if not isinstance(persona.get("constraints", []), list):
            persona["constraints"] = []
        if not isinstance(persona.get("evidence_reviews", []), list):
            persona["evidence_reviews"] = []

        valid_group_ids = set(group["review_ids"])
        filtered_ids = []
        for rid in persona["evidence_reviews"]:
            if rid in valid_group_ids and rid not in filtered_ids:
                filtered_ids.append(rid)

        if len(filtered_ids) < 3:
            for rid in group["review_ids"]:
                if rid not in filtered_ids:
                    filtered_ids.append(rid)
                if len(filtered_ids) >= 3:
                    break

        persona["evidence_reviews"] = filtered_ids
        personas.append(persona)

    return {"personas": personas}


# -----------------------------
# Prompt logging
# -----------------------------


def build_prompt_log() -> Dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "clustering": {
            "method": "TF-IDF + KMeans over-clustering + LLM merge",
            "n_micro_clusters": N_MICRO_CLUSTERS,
            "n_final_groups": N_FINAL_GROUPS,
            "tfidf": {
                "max_features": MAX_FEATURES,
                "ngram_range": list(NGRAM_RANGE),
                "min_df": MIN_DF,
                "max_df": MAX_DF,
            },
            "random_seed": RANDOM_SEED,
        },
        "prompts": {
            "micro_cluster_theme_prompt": MICRO_CLUSTER_THEME_PROMPT.strip(),
            "merge_micro_clusters_prompt": MERGE_MICRO_CLUSTERS_PROMPT.strip(),
            "persona_prompt": PERSONA_PROMPT.strip(),
        },
    }


# -----------------------------
# Main
# -----------------------------


def main() -> None:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    ensure_output_dirs()

    print("Loading cleaned reviews...")
    reviews = load_reviews(REVIEWS_PATH)
    print(f"Loaded {len(reviews)} cleaned reviews from {REVIEWS_PATH}")

    print("Creating TF-IDF matrix...")
    vectorizer, X = build_tfidf_matrix(reviews)

    print(f"Building {N_MICRO_CLUSTERS} micro-clusters...")
    micro_clusters = create_micro_clusters(reviews, vectorizer, X, N_MICRO_CLUSTERS)

    print("Connecting to Groq...")
    client = make_groq_client()

    print("Labeling micro-clusters with Groq...")
    label_micro_clusters(client, micro_clusters)

    print(f"Merging micro-clusters into {N_FINAL_GROUPS} final groups...")
    merge_groups = merge_micro_clusters_into_final_groups(
        client=client,
        micro_clusters=micro_clusters,
        n_final_groups=N_FINAL_GROUPS,
    )

    print("Assembling final automated review groups...")
    review_groups_auto = assemble_final_review_groups(
        reviews=reviews,
        micro_clusters=micro_clusters,
        merge_groups=merge_groups,
    )

    print(f"Saving {REVIEW_GROUPS_AUTO_PATH} ...")
    save_json(REVIEW_GROUPS_AUTO_PATH, review_groups_auto)

    print("Generating automated personas...")
    personas_auto = generate_personas_auto(
        client=client,
        review_groups_auto=review_groups_auto,
        reviews=reviews,
    )

    print(f"Saving {PERSONAS_AUTO_PATH} ...")
    save_json(PERSONAS_AUTO_PATH, personas_auto)

    print(f"Saving {PROMPT_AUTO_PATH} ...")
    save_json(PROMPT_AUTO_PATH, build_prompt_log())

    print("Done.")
    print(f"- Review groups saved to: {REVIEW_GROUPS_AUTO_PATH}")
    print(f"- Personas saved to: {PERSONAS_AUTO_PATH}")
    print(f"- Prompt log saved to: {PROMPT_AUTO_PATH}")


if __name__ == "__main__":
    main()
