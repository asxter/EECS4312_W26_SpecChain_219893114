#!/usr/bin/env python3
"""
src/05_personas_auto.py

Automated review grouping + persona generation for EECS 4312 Task 4.

High-level workflow:
    1. Load cleaned reviews from data/reviews_clean.jsonl
    2. Build a TF-IDF matrix from the cleaned review texts
    3. Over-cluster reviews into many small "micro-clusters" using KMeans
    4. Use an LLM (via Groq) to label each micro-cluster with a theme
    5. Use the LLM to merge micro-clusters into a smaller number of final groups
    6. Use the LLM to generate one user persona per final group
    7. Save everything to disk

Outputs:
    - data/review_groups_auto.json   – the final grouped reviews with themes
    - personas/personas_auto.json    – one persona per group
    - prompts/prompt_auto.json       – log of model settings and prompt templates used
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
from groq import Groq                                # Groq SDK – talks to the Groq cloud inference API
from sklearn.cluster import KMeans                    # K-Means clustering algorithm
from sklearn.feature_extraction.text import TfidfVectorizer  # converts text → numeric TF-IDF vectors

# -----------------------------
# Configuration
# -----------------------------

# Which LLM to call through Groq's API.
MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"

# Fixed random seed so clustering and sampling are reproducible.
RANDOM_SEED = 42

# Strategy: first create many small clusters (micro-clusters), then let the
# LLM merge them into fewer, more meaningful groups.  This two-stage approach
# produces cleaner themes than clustering directly into 5 groups.
N_MICRO_CLUSTERS = 18     # step 1: over-cluster into this many buckets
N_FINAL_GROUPS = 5        # step 2: LLM merges them down to this many

# How many example reviews to show the LLM when labelling / generating personas.
N_REPRESENTATIVES_PER_MICRO = 5      # per micro-cluster (for theme labelling)
N_EXAMPLE_REVIEWS_PER_FINAL = 5      # per final group (for persona generation)

# TF-IDF hyper-parameters — control how review text is vectorised.
MAX_FEATURES = 5000       # keep only the top 5 000 terms by TF-IDF score
NGRAM_RANGE = (1, 2)      # use both unigrams and bigrams
MIN_DF = 2                # ignore terms that appear in fewer than 2 reviews
MAX_DF = 0.90             # ignore terms that appear in more than 90 % of reviews

# Groq generation settings — low temperature for deterministic JSON output.
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 2500

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]       # project root (one level above src/)
DATA_DIR = ROOT / "data"
PERSONAS_DIR = ROOT / "personas"
PROMPTS_DIR = ROOT / "prompts"

REVIEWS_PATH = DATA_DIR / "reviews_clean.jsonl"                # input
REVIEW_GROUPS_AUTO_PATH = DATA_DIR / "review_groups_auto.json" # output – grouped reviews
PERSONAS_AUTO_PATH = PERSONAS_DIR / "personas_auto.json"       # output – personas
PROMPT_AUTO_PATH = PROMPTS_DIR / "prompt_auto.json"            # output – prompt log

# ---------------------------------------------------------------------------
# Prompt templates
#
# IMPORTANT: all literal JSON braces are DOUBLED ({{ }}) so that Python's
# str.format() treats them as literal braces rather than replacement fields.
# Only the {named_placeholders} are substituted at runtime.
# ---------------------------------------------------------------------------

# Prompt sent once per micro-cluster to get a short theme label + summary.
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

# Prompt sent once to merge all micro-clusters into N_FINAL_GROUPS final groups.
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

# Prompt sent once per final group to generate a persona grounded in the reviews.
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

# ---------------------------------------------------------------------------
# Data classes – lightweight containers for reviews and clusters
# ---------------------------------------------------------------------------


@dataclass
class Review:
    """A single review with its ID and both cleaned and raw text."""
    review_id: str
    review_text_clean: str        # after stopword removal, lemmatisation, etc.
    review_text_raw: str          # original user-written text


@dataclass
class MicroCluster:
    """
    One small cluster produced by KMeans.  Stores member review indices,
    representative reviews (closest to centroid), top TF-IDF terms, and
    the LLM-assigned theme/summary (filled in later).
    """
    micro_id: str                             # e.g. "M1", "M2", …
    member_indices: List[int]                 # indices into the reviews list
    review_ids: List[str]                     # review IDs of all members
    representative_indices: List[int]         # indices of reviews nearest to centroid
    representative_ids: List[str]             # review IDs of representatives
    representative_reviews_raw: List[str]     # raw text of representatives (sent to LLM)
    top_terms: List[str]                      # highest-weight TF-IDF terms from centroid
    theme: str = ""                           # filled by label_micro_clusters()
    summary: str = ""                         # filled by label_micro_clusters()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def ensure_output_dirs() -> None:
    """Create output directories if they don't exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def load_reviews(path: Path) -> List[Review]:
    """Load the cleaned JSONL file into a list of Review objects."""
    reviews: List[Review] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            reviews.append(
                Review(
                    review_id=obj["review_id"],
                    review_text_clean=obj["review_text_clean"],
                    # Fall back to cleaned text if the raw field is missing.
                    review_text_raw=obj.get("review_text_raw", obj["review_text_clean"]),
                )
            )
    if not reviews:
        raise ValueError(f"No reviews found in {path}")
    return reviews


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write a dict to a pretty-printed JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_json_from_text(text: str) -> Any:
    """
    Extract JSON from LLM output robustly.

    LLMs sometimes wrap their JSON in markdown code fences or add prose
    before/after it.  This function tries three strategies in order:
      1. Parse the whole response as JSON directly.
      2. Look for a ```json ... ``` fenced block and parse its contents.
      3. Find the first '{' and last '}' and try to parse that substring.
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

    raise ValueError(f"Could not parse JSON from model output:\n{text[:1200]}")


def sanitize_group_theme(theme: str) -> str:
    """Collapse whitespace and cap length for a group theme string."""
    theme = re.sub(r"\s+", " ", theme.strip())
    return theme[:120] if theme else "Unlabeled review group"


# ---------------------------------------------------------------------------
# Groq helpers
# ---------------------------------------------------------------------------


def make_groq_client() -> Groq:
    """Instantiate a Groq client, failing early if no API key is set."""
    if not GROQ_API_KEY or GROQ_API_KEY == "PASTE_YOUR_GROQ_KEY_HERE":
        raise EnvironmentError(
            "Groq API key is missing. Paste it into GROQ_API_KEY at the top of src/05_personas_auto.py"
        )
    return Groq(api_key=GROQ_API_KEY)


def groq_json_completion(client: Groq, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """
    Send a system + user message to Groq and parse the response as JSON.

    The system prompt tells the model to behave as a strict JSON generator;
    the user prompt contains the actual task and data.
    """
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


# ---------------------------------------------------------------------------
# Clustering helpers
# ---------------------------------------------------------------------------


def build_tfidf_matrix(reviews: List[Review]) -> Tuple[TfidfVectorizer, Any]:
    """
    Vectorise all cleaned review texts into a TF-IDF sparse matrix.

    Returns both the fitted vectorizer (needed later to inspect feature names)
    and the matrix X of shape (n_reviews, MAX_FEATURES).
    """
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
    """
    Run KMeans on the TF-IDF matrix to produce many small micro-clusters.

    For each cluster we also compute:
      - representative reviews: the ones whose TF-IDF vectors are closest
        to the cluster centroid (i.e. most "typical" of the cluster).
      - top terms: the highest-weighted features in the centroid vector,
        giving a quick keyword summary of the cluster's topic.
    """
    # Safety: can't have more clusters than reviews.
    n_micro_clusters = min(n_micro_clusters, len(reviews))

    km = KMeans(
        n_clusters=n_micro_clusters,
        random_state=RANDOM_SEED,
        n_init=10,               # run KMeans 10 times with different seeds, keep best
    )
    labels = km.fit_predict(X)   # assign each review to a cluster
    centers = km.cluster_centers_ # centroid vectors, shape (n_clusters, n_features)
    feature_names = np.array(vectorizer.get_feature_names_out())

    # Group review indices by their assigned cluster label.
    members_by_cluster: Dict[int, List[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        members_by_cluster[int(label)].append(idx)

    micro_clusters: List[MicroCluster] = []

    for cluster_idx in sorted(members_by_cluster.keys()):
        member_indices = members_by_cluster[cluster_idx]
        member_matrix = X[member_indices]      # TF-IDF rows for this cluster's members
        center = centers[cluster_idx]          # centroid vector for this cluster

        # --- Find representative reviews (nearest to centroid) ---
        # Compute Euclidean distance from each member to the centroid.
        distances = []
        for local_row, review_idx in enumerate(member_indices):
            row = member_matrix[local_row].toarray().ravel()  # sparse → dense
            dist = float(np.linalg.norm(row - center))
            distances.append((dist, review_idx))
        distances.sort(key=lambda x: x[0])   # ascending: closest first

        representative_indices = [
            review_idx for _, review_idx in distances[:N_REPRESENTATIVES_PER_MICRO]
        ]

        # --- Extract top terms from the centroid ---
        # The centroid's highest-weight dimensions correspond to the most
        # characteristic terms for this cluster.
        top_term_indices = np.argsort(center)[::-1][:10]
        top_terms = [term for term in feature_names[top_term_indices] if term.strip()]

        micro_id = f"M{cluster_idx + 1}"    # human-readable ID: M1, M2, …
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


# ---------------------------------------------------------------------------
# LLM labelling + merging
# ---------------------------------------------------------------------------


def label_micro_clusters(client: Groq, micro_clusters: List[MicroCluster]) -> None:
    """
    For each micro-cluster, ask the LLM to infer a short theme label and
    a 1-2 sentence summary.  Results are written directly into the
    MicroCluster objects (mutated in place).
    """
    system_prompt = (
        "You are a precise review-theme labeling assistant. "
        "Return valid JSON only. Do not add markdown or explanation outside JSON."
    )

    for cluster in micro_clusters:
        # Build a metadata dict that gives the LLM enough context to label
        # this cluster: its size, top TF-IDF terms, and a few example reviews.
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

        # Store the LLM's label and summary back on the cluster object.
        cluster.theme = sanitize_group_theme(result.get("theme", "").strip())
        cluster.summary = result.get("summary", "").strip()


def merge_micro_clusters_into_final_groups(
    client: Groq,
    micro_clusters: List[MicroCluster],
    n_final_groups: int = N_FINAL_GROUPS,
) -> List[Dict[str, Any]]:
    """
    Ask the LLM to consolidate all micro-clusters into exactly
    n_final_groups coherent groups.

    The LLM sees each micro-cluster's theme, summary, size, top terms,
    and a few example reviews, then decides which micro-clusters belong
    together.

    Post-processing ensures:
      - Exactly n_final_groups groups are returned.
      - Every micro-cluster is assigned to exactly one group (no duplicates,
        no orphans).  Any micro-clusters the LLM forgot are assigned to the
        smallest group.
    """
    system_prompt = (
        "You are a precise review-group consolidation assistant. "
        "Return valid JSON only. Use every micro-cluster exactly once."
    )

    # Build a compact summary of each micro-cluster for the prompt.
    compact_micro_clusters = []
    for c in micro_clusters:
        compact_micro_clusters.append(
            {
                "micro_id": c.micro_id,
                "theme": c.theme,
                "summary": c.summary,
                "cluster_size": len(c.review_ids),
                "top_terms": c.top_terms[:6],                     # trim to save tokens
                "representative_review_ids": c.representative_ids,
                "representative_reviews": c.representative_reviews_raw[:3],  # only 3 examples
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

    # --- Guard: pad or trim to exactly n_final_groups ---
    while len(groups) < n_final_groups:
        groups.append(
            {
                "group_id": f"A{len(groups)+1}",
                "theme": f"Auto Group {len(groups)+1}",
                "micro_cluster_ids": [],
            }
        )
    groups = groups[:n_final_groups]

    # --- Validate and repair micro-cluster assignments ---

    expected_ids = [c.micro_id for c in micro_clusters]  # e.g. ["M1", "M2", …]
    expected_set = set(expected_ids)

    # Step 1: remove duplicate or invalid micro-cluster IDs from each group.
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

    # Step 2: find any micro-clusters the LLM forgot to assign.
    missing = [mid for mid in expected_ids if mid not in used]

    # Step 3: assign orphaned micro-clusters to the currently smallest group
    # so every micro-cluster ends up in exactly one group.
    for mid in missing:
        smallest_group = min(cleaned_groups, key=lambda g: len(g["micro_cluster_ids"]))
        smallest_group["micro_cluster_ids"].append(mid)

    return cleaned_groups


def assemble_final_review_groups(
    reviews: List[Review],
    micro_clusters: List[MicroCluster],
    merge_groups: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Expand the merge plan (which maps group → micro-cluster IDs) into the
    full final output: for each group, list every individual review ID and
    include the raw review texts as examples.
    """
    micro_by_id = {c.micro_id: c for c in micro_clusters}   # quick lookup
    review_by_id = {r.review_id: r for r in reviews}

    groups_out: List[Dict[str, Any]] = []

    for idx, merged in enumerate(merge_groups, start=1):
        group_id = merged.get("group_id", f"A{idx}")
        theme = sanitize_group_theme(merged.get("theme", f"Auto Group {idx}"))
        micro_ids = merged["micro_cluster_ids"]

        # Collect all review IDs from the micro-clusters belonging to this group.
        review_ids: List[str] = []
        for micro_id in micro_ids:
            c = micro_by_id[micro_id]
            review_ids.extend(c.review_ids)

        # Deduplicate review IDs while preserving insertion order.
        seen_ids = set()
        dedup_review_ids = []
        for rid in review_ids:
            if rid not in seen_ids:
                seen_ids.add(rid)
                dedup_review_ids.append(rid)

        # Attach the full raw review text for every review in this group.
        example_reviews = [
            review_by_id[rid].review_text_raw
            for rid in dedup_review_ids
            if rid in review_by_id
        ]

        groups_out.append(
            {
                "group_id": group_id,
                "theme": theme,
                "review_ids": dedup_review_ids,
                "example_reviews": example_reviews,
            }
        )

    return {"groups": groups_out}


# ---------------------------------------------------------------------------
# Persona generation
# ---------------------------------------------------------------------------


def generate_personas_auto(
    client: Groq,
    review_groups_auto: Dict[str, Any],
    reviews: List[Review],
) -> Dict[str, Any]:
    """
    For each final review group, call the LLM to produce a user persona
    grounded in the group's representative reviews.

    Post-processing ensures:
      - All fields (goals, pain_points, etc.) are lists.
      - evidence_reviews contains only IDs that actually belong to the group.
      - At least 3 evidence review IDs are present (padded from the group
        if the LLM didn't supply enough).
    """
    review_lookup = {r.review_id: r for r in reviews}
    personas: List[Dict[str, Any]] = []

    system_prompt = (
        "You are a strict JSON persona generator for software requirements engineering. "
        "Return valid JSON only. Keep persona details grounded in the provided evidence."
    )

    for idx, group in enumerate(review_groups_auto["groups"], start=1):
        group_id = group["group_id"]
        persona_id = f"P_auto_{idx}"     # e.g. P_auto_1, P_auto_2, …

        # Pick up to 8 reviews from the group as evidence for the LLM.
        representative_examples = []
        for rid in group["review_ids"][:8]:
            review = review_lookup[rid]
            representative_examples.append(
                {
                    "review_id": rid,
                    "review_text_raw": review.review_text_raw,
                }
            )

        # Ask the LLM to generate the persona.
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

        # --- Post-processing: enforce correct ID and types ---

        # Force the persona ID and group linkage regardless of what the LLM returned.
        persona["id"] = persona_id
        persona["derived_from_group"] = group_id

        # Ensure every expected field is a list (the LLM might return a string or None).
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

        # Keep only evidence review IDs that actually belong to this group,
        # and deduplicate.
        valid_group_ids = set(group["review_ids"])
        filtered_ids = []
        for rid in persona["evidence_reviews"]:
            if rid in valid_group_ids and rid not in filtered_ids:
                filtered_ids.append(rid)

        # Guarantee at least 3 evidence IDs by borrowing from the group.
        if len(filtered_ids) < 3:
            for rid in group["review_ids"]:
                if rid not in filtered_ids:
                    filtered_ids.append(rid)
                if len(filtered_ids) >= 3:
                    break

        persona["evidence_reviews"] = filtered_ids
        personas.append(persona)

    return {"personas": personas}


# ---------------------------------------------------------------------------
# Prompt logging
# ---------------------------------------------------------------------------


def build_prompt_log() -> Dict[str, Any]:
    """
    Build a JSON-serialisable dict that records every model setting and
    prompt template used in this run.  Useful for reproducibility and
    for the project report.
    """
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """
    End-to-end pipeline:
      1. Seed RNGs for reproducibility
      2. Load cleaned reviews
      3. Build TF-IDF matrix
      4. KMeans → micro-clusters
      5. LLM labels each micro-cluster
      6. LLM merges micro-clusters into final groups
      7. Assemble full review groups with all review IDs
      8. LLM generates one persona per group
      9. Save all outputs to disk
    """
    # Fix random seeds so every run produces the same clusters.
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    ensure_output_dirs()

    # --- Load data ---
    print("Loading cleaned reviews...")
    reviews = load_reviews(REVIEWS_PATH)
    print(f"Loaded {len(reviews)} cleaned reviews from {REVIEWS_PATH}")

    # --- Vectorise ---
    print("Creating TF-IDF matrix...")
    vectorizer, X = build_tfidf_matrix(reviews)

    # --- Micro-clustering ---
    print(f"Building {N_MICRO_CLUSTERS} micro-clusters...")
    micro_clusters = create_micro_clusters(reviews, vectorizer, X, N_MICRO_CLUSTERS)

    # --- LLM phase ---
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

    # --- Assemble final groups ---
    print("Assembling final automated review groups...")
    review_groups_auto = assemble_final_review_groups(
        reviews=reviews,
        micro_clusters=micro_clusters,
        merge_groups=merge_groups,
    )

    print(f"Saving {REVIEW_GROUPS_AUTO_PATH} ...")
    save_json(REVIEW_GROUPS_AUTO_PATH, review_groups_auto)

    # --- Persona generation ---
    print("Generating automated personas...")
    personas_auto = generate_personas_auto(
        client=client,
        review_groups_auto=review_groups_auto,
        reviews=reviews,
    )

    print(f"Saving {PERSONAS_AUTO_PATH} ...")
    save_json(PERSONAS_AUTO_PATH, personas_auto)

    # --- Prompt log ---
    print(f"Saving {PROMPT_AUTO_PATH} ...")
    save_json(PROMPT_AUTO_PATH, build_prompt_log())

    # --- Summary ---
    print("Done.")
    print(f"- Review groups saved to: {REVIEW_GROUPS_AUTO_PATH}")
    print(f"- Personas saved to: {PERSONAS_AUTO_PATH}")
    print(f"- Prompt log saved to: {PROMPT_AUTO_PATH}")


if __name__ == "__main__":
    main()
