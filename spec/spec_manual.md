# Requirement ID: FR1

- Description: The system shall provide every user with at least one viewable summary report after completion of the initial assessment period without requiring a subscription purchase.
- Source Persona: P1 — Cost-Sensitive Mental Health Seeker
- Traceability: Derived from review group G1
- Acceptance Criteria: Given a user has completed the initial assessment period, when the assessment completes, then the system shall display at least one summary report without requiring payment.

# Requirement ID: FR2

- Description: Before a user begins the initial assessment or any premium trial, the system shall disclose which features are free, which require payment, the subscription price, the billing period, and whether billing renews automatically.
- Source Persona: P1 — Cost-Sensitive Mental Health Seeker
- Traceability: Derived from review group G1
- Acceptance Criteria: Given a new user is about to begin the assessment or start a premium trial, when the pricing screen is shown, then the screen shall list free features, paid features, price, billing period, and renewal status before the user proceeds.

# Requirement ID: FR3

- Description: The system shall preserve user access to previously generated reports, history, and journal entries after subscription cancellation or expiry.
- Source Persona: P1 — Cost-Sensitive Mental Health Seeker
- Traceability: Derived from review group G1
- Acceptance Criteria: Given a user has previously generated reports and entries, when the user’s subscription expires or is cancelled, then the user shall still be able to view their existing reports, history, and journal entries.

# Requirement ID: FR4

- Description: The system shall display an interactive dashboard or questionnaire screen on launch without a blank screen or application crash on a supported device with working connectivity.
- Source Persona: P2 — Reliability-Dependent Daily User
- Traceability: Derived from review group G2
- Acceptance Criteria: Given the app is launched on a supported device with working internet connectivity, when startup completes, then the user shall see an interactive dashboard or questionnaire screen and the app shall not crash.

# Requirement ID: FR5

- Description: The system shall authenticate users with valid credentials and load their saved history after sign-in.
- Source Persona: P2 — Reliability-Dependent Daily User
- Traceability: Derived from review group G2
- Acceptance Criteria: Given a user enters valid account credentials, when sign-in is submitted, then the system shall sign the user in and display the user’s saved history.

# Requirement ID: FR6

- Description: The system shall preserve existing user entries and generated reports after an application update.
- Source Persona: P2 — Reliability-Dependent Daily User
- Traceability: Derived from review group G2
- Acceptance Criteria: Given a user has saved entries and reports before an app update, when the app is updated and reopened, then the previously saved entries and reports shall still be accessible.

# Requirement ID: FR7

- Description: Before collecting account, health, or device-sharing data beyond what is required for core check-ins, the system shall present a disclosure and request explicit consent for each optional data category.
- Source Persona: P3 — Privacy-Conscious Sensitive-Data User
- Traceability: Derived from review group G3
- Acceptance Criteria: Given a user is asked to provide account, health, or device-sharing data, when the request is shown, then the system shall list each optional data category, its purpose, and require the user to actively consent before collection.

# Requirement ID: FR8

- Description: The system shall allow a user to create an account using valid required fields and link subsequent entries to that account.
- Source Persona: P3 — Privacy-Conscious Sensitive-Data User
- Traceability: Derived from review group G3
- Acceptance Criteria: Given a user enters valid account information in all required fields, when account creation is submitted, then the account shall be created and subsequent entries shall be stored under that account.

# Requirement ID: FR9

- Description: The system shall allow a signed-in user to restore previously synchronized data after reinstalling the application or changing devices.
- Source Persona: P3 — Privacy-Conscious Sensitive-Data User
- Traceability: Derived from review group G3
- Acceptance Criteria: Given a signed-in user has previously synchronized data, when the user reinstalls the app or signs in on another supported device, then the user’s synchronized entries and reports shall be restored.

# Requirement ID: FR10

- Description: The system shall allow users to configure reminder enablement, daily reminder frequency, and preferred reminder time windows.
- Source Persona: P4 — Reminder-Dependent Routine Builder
- Traceability: Derived from review group G4
- Acceptance Criteria: Given a user opens reminder settings, when the user saves reminder preferences, then the system shall store the selected enablement state, frequency, and preferred time windows.

# Requirement ID: FR11

- Description: If reminders are enabled, the system shall continue issuing reminders according to the user’s saved schedule even after missed entries until the user disables reminders.
- Source Persona: P4 — Reminder-Dependent Routine Builder
- Traceability: Derived from review group G4
- Acceptance Criteria: Given reminders are enabled and the user misses one or more check-ins, when the next scheduled reminder time occurs, then the system shall still issue the reminder unless the user has disabled reminders.

# Requirement ID: FR12

- Description: The system shall allow users to declare contextual factors that affect question relevance, including employment status, disability or chronic illness status, and atypical work schedule, and shall exclude clearly inapplicable questions based on those declarations.
- Source Persona: P5 — Questionnaire-Fatigued User Seeking Relevant Insights
- Traceability: Derived from review group G5
- Acceptance Criteria: Given a user has declared relevant context factors, when the next questionnaire is generated, then the questionnaire shall exclude questions that conflict with those declared factors.

# Requirement ID: FR13

- Description: The system shall limit repetitive question reuse by not presenting the same question text more than twice within any rolling 7-day period unless that question is explicitly required for a declared longitudinal assessment.
- Source Persona: P5 — Questionnaire-Fatigued User Seeking Relevant Insights
- Traceability: Derived from review group G5
- Acceptance Criteria: Given a user completes multiple check-ins within a 7-day period, when question sets are generated, then the same question text shall not appear more than twice unless it is marked as required for longitudinal assessment.

# Requirement ID: FR14

- Description: The system shall generate a viewable report that summarizes recent user-entered patterns and identifies the date range covered by the report.
- Source Persona: P6 — Engaged Self-Reflection User
- Traceability: Derived from review group G6
- Acceptance Criteria: Given a user has enough completed entries for report generation, when a report is produced, then the report shall display at least one summary of recent patterns and the date range it covers.

# Requirement ID: FR15

- Description: The system shall allow users to export a generated report for sharing with a healthcare professional.
- Source Persona: P6 — Engaged Self-Reflection User
- Traceability: Derived from review group G6
- Acceptance Criteria: Given a user has a generated report, when the user selects the export action, then the system shall produce an exportable report file containing the report content and date range.
