# EECS 4312 - SpecChain: Requirements Engineering Pipeline

## Application Studied

**MindDoc (formerly Moodpath)** - a mental health and mood tracking app on Google Play.

- App ID: `de.moodpath.android`
- Store URL: https://play.google.com/store/apps/details?id=de.moodpath.android&hl=en_CA
- Category: Health and Fitness / Mental Health

MindDoc helps users track their mood, complete psychological questionnaires, and access mental health resources. It was chosen because it has a large number of English-language reviews covering a wide range of user experiences, from pricing frustrations to positive therapeutic outcomes.

## Dataset

- **Collection tool:** [google-play-scraper](https://github.com/JoMingyu/google-play-scraper) by JoMingyu - a Python library that wraps the unofficial Google Play Store API to fetch app metadata and user reviews programmatically.
- **Collection settings:** Language `en`, country `ca`, sorted by `NEWEST`, fetched in batches of 200 using continuation tokens.
- `data/reviews_raw.jsonl` contains the 3,000 extracted reviews (one JSON object per line).
- `data/reviews_clean.jsonl` contains the cleaned dataset after removing duplicates, empty reviews, and reviews shorter than 3 words.
- **Final cleaned dataset size: 2,582 reviews.**
- Cleaning steps included: emoji/symbol removal, lowercase conversion, URL removal, punctuation removal, number-to-word conversion, stopword removal, and lemmatization.

**Limitation note:** The Google Play Store does not expose all historical reviews through its API. MindDoc has approximately 40,000 reviews on the store, but we were only able to extract 3,000. This is a known limitation of the google-play-scraper library - it can only access what the Google Play internal API returns, which caps the number of retrievable reviews regardless of how many exist on the store page.

## Repository Structure

```
data/           - datasets, review groups (manual, auto, hybrid)
personas/       - persona files (manual, auto, hybrid)
spec/           - requirement specifications (manual, auto, hybrid)
tests/          - validation test files (manual, auto, hybrid)
prompts/        - LLM prompt logs for the auto pipeline
metrics/        - metric results and summary comparison
reflection/     - final project reflection
src/            - all executable Python scripts
```

## How to Run

```bash
cd <project-root>
python3 src/run_all.py
```

This single command will:
1. Install all dependencies (groq, google-play-scraper, nltk, scikit-learn, etc.)
2. Run `00_validate_repo.py` to check all files and folders
3. Ask whether to skip data collection - type `Y` to keep existing data, or `n` to scrape new data from Google Play
4. Run `02_clean.py` to clean the raw reviews
5. Run `03_manual_coding_template.py` to verify manual groups
6. Run `04_personas_manual.py` to verify manual personas
7. Run `05_personas_auto.py` to generate automated groups and personas
8. Run `06_spec_generate.py` to generate automated requirements
9. Run `07_tests_generate.py` to generate automated tests
10. Run `08_metrics.py --all` to compute metrics for all pipelines
11. Run `00_validate_repo.py` again to confirm all outputs exist

To run individual steps:
```bash
python3 src/00_validate_repo.py          # check repo structure
python3 src/08_metrics.py --pipeline auto # compute auto metrics only
python3 src/08_metrics.py --all          # compute all metrics + summary
```

Open `metrics/metrics_summary.json` for side-by-side comparison of all three pipelines.

## What Was Done Manually

### Manual Review Groups (Task 3.1)

We read through hundreds of cleaned reviews by hand and identified 6 recurring themes. Each review was assigned to exactly one group based on the user's core concern or situation. The 6 groups are:

1. **G1** - Budget-constrained users frustrated by paywalls and high subscription costs (13 reviews)
2. **G2** - Users experiencing crashes, bugs, and connection errors (13 reviews)
3. **G3** - Accounts, privacy, and data-sharing concerns (11 reviews)
4. **G4** - Notification issues - too many reminders or missing reminders altogether (13 reviews)
5. **G5** - Overwhelming or irrelevant questionnaires and repetitive questions (13 reviews)
6. **G6** - Positive and supportive feedback praising the app's impact (13 reviews)

These groups are stored in `data/review_groups_manual.json`. A total of 76 reviews were manually coded. The remaining reviews were not assigned because manual coding of all 2,582 reviews was not feasible within the project timeline.

### Manual Personas (Task 3.2)

For each of the 6 manual groups, we wrote one persona by re-reading the reviews in that group and summarizing the common goals, frustrations, and context. The 6 personas are:

1. **Cost-Sensitive Mental Health Seeker** (G1) - wants free access to core mood tracking features
2. **Reliability-Dependent Daily User** (G2) - depends on the app daily and gets frustrated by crashes
3. **Privacy-Conscious Sensitive-Data User** (G3) - concerned about how personal health data is stored and shared
4. **Reminder-Dependent Routine Builder** (G4) - relies on notifications to maintain a daily check-in habit
5. **Questionnaire-Fatigued User Seeking Relevant Insights** (G5) - finds the questionnaires repetitive and wants more personalized content
6. **Engaged Self-Reflection User** (G6) - actively uses the app for self-awareness and values the experience

These personas are stored in `personas/personas_manual.json`. Each persona includes goals, pain points, context, and evidence review IDs linking back to the reviews that informed it.

## Pipelines

| Pipeline | Grouping | Personas | Specs | Tests |
|----------|----------|----------|-------|-------|
| Manual | Done by hand | Written by hand | Written by hand | Written by hand |
| Auto | TF-IDF + KMeans + LLM | LLM generated | LLM generated | LLM generated |
| Hybrid | LLM generated, manually refined | LLM generated, manually refined | LLM generated, manually refined | LLM generated, manually refined |

## About src/03 and src/04 (Manual Verification Scripts)

The project instructions for manual coding and manual personas did not specify any automated logic - the work was done entirely by hand (reading reviews, assigning groups, writing personas). Because of this, `src/03_manual_coding_template.py` and `src/04_personas_manual.py` were written as verification modules rather than generators.

**`src/03_manual_coding_template.py`** checks whether `data/review_groups_manual.json` exists and meets the minimum requirements (at least 5 groups with at least 50 total reviews). If the file is missing, it creates a starter template showing the expected JSON format. If the file exists, it prints a summary of how many groups and reviews are present. It never blocks the pipeline.

**`src/04_personas_manual.py`** does the same for `personas/personas_manual.json`. It checks whether each persona has a name, description, goals, and pain points filled in, and reports which ones are complete or incomplete. If the file is missing, it creates a template with the expected format.

Both scripts were designed this way because the manual work was already completed before the pipeline was assembled. Their purpose is to let the TA (or any reviewer) quickly verify that the manual deliverables are present and properly structured, without interfering with the automated pipeline.

## Key Metrics

| Metric | Manual | Auto | Hybrid |
|--------|--------|------|--------|
| Review coverage | 3.0% | 100% | 100% |
| Traceability ratio | 1.0 | 1.0 | 1.0 |
| Testability rate | 1.0 | 1.0 | 1.0 |
| Ambiguity ratio | 13.3% | 20.0% | 0.0% |

## Where to Find Everything
 
| File | What it contains |
|------|-----------------|
| `data/reviews_raw.jsonl` | Original scraped reviews (3,000 reviews) |
| `data/reviews_clean.jsonl` | Cleaned reviews after filtering (2,582 reviews) |
| `prompts/prompt_auto.json` | All LLM prompts and settings used in the auto pipeline |
| `metrics/metrics_summary.json` | Side-by-side comparison of all three pipelines |
| `reflection/reflection.md` | Final project reflection |
 
