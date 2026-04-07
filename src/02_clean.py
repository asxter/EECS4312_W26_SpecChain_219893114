#!/usr/bin/env python3
"""
Clean the raw Google Play reviews collected by 01_collect_or_import.py.

Pipeline summary:
    1. Load raw reviews from data/reviews_raw.jsonl
    2. For each review, apply text-cleaning steps (emoji removal, lowercasing,
       stopword removal, lemmatisation, etc.)
    3. Drop empty, too-short, and duplicate reviews
    4. Write surviving reviews to data/reviews_clean.jsonl
    5. Update data/dataset_metadata.json with cleaning stats and decisions

Run:
    python src/02_clean.py
"""

import json
import re
import unicodedata
from pathlib import Path

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# num2words converts integers to their English word form (e.g. 3 → "three").
# It's optional – if not installed, digits are simply stripped instead.
try:
    from num2words import num2words
except ImportError:
    num2words = None


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

RAW_PATH = DATA_DIR / "reviews_raw.jsonl"        # input  – produced by step 01
CLEAN_PATH = DATA_DIR / "reviews_clean.jsonl"     # output – one cleaned review per line
METADATA_PATH = DATA_DIR / "dataset_metadata.json"  # updated with cleaning summary

# Reviews with fewer than this many words (after cleaning) are discarded.
MIN_WORDS = 3


# ---------------------------------------------------------------------------
# NLTK SETUP
# ---------------------------------------------------------------------------

def ensure_nltk_resources() -> None:
    """Download the NLTK data files we need (no-op if already present)."""
    nltk.download("stopwords", quiet=True)   # English stopword list
    nltk.download("wordnet", quiet=True)     # WordNet lemmatiser dictionary
    nltk.download("omw-1.4", quiet=True)     # Open Multilingual WordNet (needed by lemmatiser)


# ---------------------------------------------------------------------------
# FILE I/O HELPERS
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return a list of dicts (one per line)."""
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:                        # skip blank lines
                records.append(json.loads(line))
    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    """Write a list of dicts to a JSONL file (one JSON object per line)."""
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# TEXT-CLEANING FUNCTIONS
# ---------------------------------------------------------------------------

def remove_emojis_and_symbols(text: str) -> str:
    """
    Strip emoji and miscellaneous symbol characters by checking each
    character's Unicode category:
      - "So" = Symbol, Other   (most emoji live here)
      - "Sk" = Symbol, Modifier (combining accents on symbols, etc.)
    Everything else (letters, digits, punctuation, whitespace) is kept.
    """
    cleaned_chars = []
    for ch in text:
        category = unicodedata.category(ch)
        if category.startswith("So") or category.startswith("Sk"):
            continue          # drop this character
        cleaned_chars.append(ch)
    return "".join(cleaned_chars)


def convert_numbers_to_text(text: str) -> str:
    """
    Replace digit sequences with their English word equivalents
    (e.g. "5" → "five").  If num2words isn't installed, digits are simply
    replaced with a space so they don't pollute the cleaned text.
    """
    if num2words is None:
        # Fallback: just remove all digit sequences.
        return re.sub(r"\d+", " ", text)

    def replace_number(match: re.Match) -> str:
        number_str = match.group()
        try:
            return " " + num2words(int(number_str)) + " "
        except Exception:
            return " "       # if conversion fails, drop the number

    return re.sub(r"\d+", replace_number, text)


def clean_text(text: str, stop_words: set[str], lemmatizer: WordNetLemmatizer) -> str:
    """
    Full cleaning pipeline for a single review string:

      1. Remove emojis / symbols
      2. Convert numbers to words (or strip them)
      3. Lowercase everything
      4. Strip URLs
      5. Remove any remaining non-letter characters (punctuation, etc.)
      6. Collapse multiple spaces
      7. Remove English stopwords
      8. Lemmatise each remaining token (e.g. "running" → "run")

    Returns the cleaned string, or "" if nothing useful remains.
    """
    if not text or not text.strip():
        return ""

    # Step 1 – emojis / symbols
    text = remove_emojis_and_symbols(text)

    # Step 2 – numbers → words
    text = convert_numbers_to_text(text)

    # Step 3 – lowercase
    text = text.lower()

    # Step 4 – strip URLs (http://… or www.…)
    text = re.sub(r"http\S+|www\.\S+", " ", text)

    # Step 5 – keep only lowercase letters and whitespace
    text = re.sub(r"[^a-z\s]", " ", text)

    # Step 6 – normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Step 7 – tokenise and remove stopwords
    tokens = text.split()
    tokens = [token for token in tokens if token not in stop_words]

    # Step 8 – lemmatise (reduce words to base/dictionary form)
    tokens = [lemmatizer.lemmatize(token) for token in tokens]

    return " ".join(tokens).strip()


# ---------------------------------------------------------------------------
# METADATA HELPERS
# ---------------------------------------------------------------------------

def load_existing_metadata() -> dict:
    """Load the metadata JSON written by step 01, if it exists."""
    if METADATA_PATH.exists():
        with METADATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def update_metadata(
    raw_count: int,
    cleaned_count: int,
    duplicates_removed: int,
    empty_removed: int,
    short_removed: int,
) -> None:
    """
    Merge cleaning-specific information into the existing metadata file.
    Preserves fields written by step 01 (app_name, collection_method, etc.)
    and adds/overwrites the cleaning-related keys.
    """
    metadata = load_existing_metadata()

    # Preserve app name from step 01; fall back to a default if missing.
    metadata["app_name"] = metadata.get("app_name", "MindDoc: Mental Health Support")
    metadata["dataset_size"] = cleaned_count
    metadata["raw_dataset_size"] = raw_count
    metadata["collection_method"] = metadata.get(
        "collection_method",
        "Collected from Google Play Store using google-play-scraper",
    )

    # Human-readable list of every cleaning transformation applied.
    metadata["cleaning_decisions"] = [
        "Removed duplicate reviews based on cleaned review text",
        "Removed empty entries",
        f"Removed extremely short reviews with fewer than {MIN_WORDS} cleaned words",
        "Removed punctuation",
        "Removed special characters and emojis",
        "Converted numbers to text when possible",
        "Removed extra whitespace",
        "Converted all words to lowercase",
        "Removed stop words",
        "Lemmatized review text",
    ]

    # Numeric breakdown of what was dropped.
    metadata["cleaning_summary"] = {
        "duplicates_removed": duplicates_removed,
        "empty_removed": empty_removed,
        "short_removed": short_removed,
        "cleaned_reviews_kept": cleaned_count,
    }

    with METADATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orchestrates the cleaning pipeline:
      1. Load raw reviews
      2. Clean each review's text
      3. Drop empty, short, and duplicate reviews
      4. Write the cleaned dataset and update metadata
    """
    # Fail early if step 01 hasn't been run yet.
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing raw dataset: {RAW_PATH}")

    ensure_nltk_resources()

    # Prepare NLP tools.
    stop_words = set(stopwords.words("english"))   # e.g. {"the", "is", "at", …}
    lemmatizer = WordNetLemmatizer()

    raw_records = load_jsonl(RAW_PATH)
    cleaned_records = []
    seen_cleaned_texts = set()     # used for duplicate detection on the *cleaned* text

    # Counters for the metadata summary.
    duplicates_removed = 0
    empty_removed = 0
    short_removed = 0

    for record in raw_records:
        raw_text = record.get("content", "")
        cleaned_text = clean_text(raw_text, stop_words, lemmatizer)

        # --- Filter 1: empty after cleaning ---
        if not cleaned_text:
            empty_removed += 1
            continue

        # --- Filter 2: too short (fewer than MIN_WORDS words) ---
        if len(cleaned_text.split()) < MIN_WORDS:
            short_removed += 1
            continue

        # --- Filter 3: duplicate (same cleaned text already seen) ---
        if cleaned_text in seen_cleaned_texts:
            duplicates_removed += 1
            continue

        seen_cleaned_texts.add(cleaned_text)

        # Build a slimmed-down record keeping only the fields we need
        # going forward.  Both the raw and cleaned text are preserved so
        # later analysis can reference the original wording if needed.
        cleaned_record = {
            "review_id": record.get("review_id"),
            "app_id": record.get("app_id"),
            "app_url": record.get("app_url"),
            "score": record.get("score"),
            "at": record.get("at"),
            "review_text_raw": raw_text,
            "review_text_clean": cleaned_text,
        }
        cleaned_records.append(cleaned_record)

    # --- Persist results ---
    write_jsonl(cleaned_records, CLEAN_PATH)
    update_metadata(
        raw_count=len(raw_records),
        cleaned_count=len(cleaned_records),
        duplicates_removed=duplicates_removed,
        empty_removed=empty_removed,
        short_removed=short_removed,
    )

    # --- Console summary ---
    print("[DONE] Cleaning complete.")
    print(f"[INFO] Raw reviews: {len(raw_records)}")
    print(f"[INFO] Cleaned reviews kept: {len(cleaned_records)}")
    print(f"[INFO] Duplicates removed: {duplicates_removed}")
    print(f"[INFO] Empty removed: {empty_removed}")
    print(f"[INFO] Short removed: {short_removed}")
    print(f"[INFO] Cleaned file written to: {CLEAN_PATH}")
    print(f"[INFO] Metadata file written to: {METADATA_PATH}")


if __name__ == "__main__":
    main()
