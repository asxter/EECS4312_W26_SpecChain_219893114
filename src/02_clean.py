#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

try:
    from num2words import num2words
except ImportError:
    num2words = None


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

RAW_PATH = DATA_DIR / "reviews_raw.jsonl"
CLEAN_PATH = DATA_DIR / "reviews_clean.jsonl"
METADATA_PATH = DATA_DIR / "dataset_metadata.json"

MIN_WORDS = 3


def ensure_nltk_resources() -> None:
    nltk.download("stopwords", quiet=True)
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def remove_emojis_and_symbols(text: str) -> str:
    cleaned_chars = []
    for ch in text:
        category = unicodedata.category(ch)
        if category.startswith("So") or category.startswith("Sk"):
            continue
        cleaned_chars.append(ch)
    return "".join(cleaned_chars)


def convert_numbers_to_text(text: str) -> str:
    if num2words is None:
        return re.sub(r"\d+", " ", text)

    def replace_number(match: re.Match) -> str:
        number_str = match.group()
        try:
            return " " + num2words(int(number_str)) + " "
        except Exception:
            return " "

    return re.sub(r"\d+", replace_number, text)


def clean_text(text: str, stop_words: set[str], lemmatizer: WordNetLemmatizer) -> str:
    if not text or not text.strip():
        return ""

    text = remove_emojis_and_symbols(text)
    text = convert_numbers_to_text(text)
    text = text.lower()

    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()
    tokens = [token for token in tokens if token not in stop_words]
    tokens = [lemmatizer.lemmatize(token) for token in tokens]

    return " ".join(tokens).strip()


def load_existing_metadata() -> dict:
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
    metadata = load_existing_metadata()

    metadata["app_name"] = metadata.get("app_name", "MindDoc: Mental Health Support")
    metadata["dataset_size"] = cleaned_count
    metadata["raw_dataset_size"] = raw_count
    metadata["collection_method"] = metadata.get(
        "collection_method",
        "Collected from Google Play Store using google-play-scraper",
    )
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
    metadata["cleaning_summary"] = {
        "duplicates_removed": duplicates_removed,
        "empty_removed": empty_removed,
        "short_removed": short_removed,
        "cleaned_reviews_kept": cleaned_count,
    }

    with METADATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing raw dataset: {RAW_PATH}")

    ensure_nltk_resources()

    stop_words = set(stopwords.words("english"))
    lemmatizer = WordNetLemmatizer()

    raw_records = load_jsonl(RAW_PATH)
    cleaned_records = []
    seen_cleaned_texts = set()

    duplicates_removed = 0
    empty_removed = 0
    short_removed = 0

    for record in raw_records:
        raw_text = record.get("content", "")
        cleaned_text = clean_text(raw_text, stop_words, lemmatizer)

        if not cleaned_text:
            empty_removed += 1
            continue

        if len(cleaned_text.split()) < MIN_WORDS:
            short_removed += 1
            continue

        if cleaned_text in seen_cleaned_texts:
            duplicates_removed += 1
            continue

        seen_cleaned_texts.add(cleaned_text)

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

    write_jsonl(cleaned_records, CLEAN_PATH)
    update_metadata(
        raw_count=len(raw_records),
        cleaned_count=len(cleaned_records),
        duplicates_removed=duplicates_removed,
        empty_removed=empty_removed,
        short_removed=short_removed,
    )

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
