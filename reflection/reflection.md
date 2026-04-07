# Application: [MindDoc: Mental Health Support] 
# Reflection

## How the Three Pipelines Differed

The **manual pipeline** involved reading hundreds of reviews by hand, deciding on group themes, and writing personas from scratch. This was slow but gave me full control over what each group represented. I created 6 personas with names like "Cost-Sensitive Mental Health Seeker" and "Privacy-Conscious Sensitive-Data User" that reflected specific user situations I noticed repeatedly in the reviews. The downside was coverage - I could only code 78 out of 2,582 reviews (3%), so most of the dataset went unused.

The **automated pipeline** used Term Frequency-Inverse Document Frequency (TF-IDF), which converts review text into numbers by measuring how important each word is to a review relative to the whole dataset, and K-Means clustering, which groups reviews together based on how similar their word patterns are, to cluster all 2,582 reviews into micro-clusters, then asked an LLM to merge them into 5 groups and generate personas. This achieved 100% review coverage, but the personas were more generic - names like "Satisfied User" and "Self-Discovering User" lack the specificity of the manual ones. The LLM also introduced ambiguity: 20% of auto-generated requirements contained vague words like "seamless" or "intuitive" that are hard to test.

The **hybrid pipeline** combined manual grouping decisions with LLM-assisted spec generation. It kept the 100% coverage of the auto pipeline while eliminating ambiguity entirely (0% ambiguity ratio), making it the strongest overall.

## Clearest Personas

The manual personas were the clearest. Because I read the reviews myself, I could identify precise user situations - for example, distinguishing "Reminder-Dependent Routine Builder" from "Questionnaire-Fatigued User" required understanding subtle differences in what users were frustrated about. The auto personas tended to blur these distinctions.

## Most Useful Requirements

The hybrid pipeline produced the most useful requirements. It had 0% ambiguity compared to 20% for auto and 13% for manual, while maintaining full traceability and testability. The manual requirements were good but limited by the small number of reviews I could process.

## Strongest Traceability

The manual pipeline had the most traceability links (81 vs 65 for auto and hybrid) because I created 6 personas instead of 5 and wrote 45 tests instead of 30. All three pipelines achieved 1.0 traceability ratio and 1.0 testability rate, meaning every requirement traced to a persona and every requirement had tests.

## Problems in Automated Outputs

The main issues with the auto pipeline were: (1) vague language in requirements that slipped past the prompt instructions, (2) persona names that were too broad to be actionable, and (3) the LLM occasionally grouping unrelated reviews together because they shared surface-level vocabulary rather than actual user intent. The over-cluster-then-merge strategy helped reduce this last problem but did not eliminate it entirely.

## Key Takeaways

- **Most important difference between pipelines:** The automated pipeline produced broader personas, while the manual pipeline produced more focused personas grounded in specific review groups.
- **Most useful pipeline:** The hybrid pipeline produced the most balanced outputs because it preserved automation speed while improving clarity and traceability.
- **Most surprising finding:** Several automated requirements were grammatically correct but too vague to support reliable test generation.
- **Observed weakness in the automated pipeline:** Some personas included unsupported assumptions that were not clearly grounded in the reviews.
