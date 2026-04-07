# Requirement ID: FR_hybrid_1
- Description: [The system shall display at least 3 selectable emotion options during a check-in.]
- Source Persona: [P_hybrid_1 - Self-Discovering User]
- Traceability: [Derived from review group H1]
- Acceptance Criteria: [If the user opens a check-in and reaches the emotion-selection step, the system must display at least 3 selectable emotion options and allow the user to select 1 option.]
- Notes: [Rewritten from FR_auto_1 to remove the unsupported requirement for 20 emotions and to update traceability from A1 to H1.]

# Requirement ID: FR_hybrid_2
- Description: [The system shall display previously completed check-ins in chronological order.]
- Source Persona: [P_hybrid_2 - Satisfied User]
- Traceability: [Derived from review group H2]
- Acceptance Criteria: [If the user has completed at least 2 check-ins and opens the history page, the system must display those check-ins ordered by date and time.]
- Notes: [Rewritten from FR_auto_2 to remove the unsupported graph format and to update traceability from A2 to H2.]

# Requirement ID: FR_hybrid_3
- Description: [The system shall display at least 1 generated summary based on completed check-ins.]
- Source Persona: [P_hybrid_2 - Satisfied User]
- Traceability: [Derived from review group H2]
- Acceptance Criteria: [If the user has completed at least 3 check-ins and opens the insights page, the system must display at least 1 summary generated from stored check-in data.]
- Notes: [Rewritten from FR_auto_3 to remove the vague terms “helpful,” “guidance,” and “actionable.”]

# Requirement ID: FR_hybrid_4
- Description: [The system shall generate a date-range summary report from completed check-ins.]
- Source Persona: [P_hybrid_3 - Mindful Tracker]
- Traceability: [Derived from review group H3]
- Acceptance Criteria: [If the user selects a date range containing at least 2 completed check-ins, the system must display a report that includes the selected start date, the selected end date, and the number of check-ins in that range.]
- Notes: [FR_auto_4 was replaced because subscription management was not supported by the Mindful Tracker persona in the hybrid version.]

# Requirement ID: FR_hybrid_5
- Description: [The system shall complete a check-in submission within 2 seconds after the user presses the submit button.]
- Source Persona: [P_hybrid_3 - Mindful Tracker]
- Traceability: [Derived from review group H3]
- Acceptance Criteria: [If the user presses the submit button on a completed check-in, the system must confirm submission within 2 seconds.]
- Notes: [Rewritten from FR_auto_5 to remove the vague phrase “user-friendly interface” while keeping the measurable response-time condition.]

# Requirement ID: FR_hybrid_6
- Description: [The system shall allow a user without an active paid subscription to complete a check-in, open check-in history, and view 1 summary page.]
- Source Persona: [P_hybrid_4 - Frugal Mental Health Enthusiast]
- Traceability: [Derived from review group H4]
- Acceptance Criteria: [If a user without an active paid subscription signs in, the system must allow that user to complete 1 check-in, open saved check-in history, and open 1 summary page without requiring payment.]
- Notes: [Rewritten from FR_auto_6 to replace the vague phrase “valuable features and content” with specific free-tier functions.]

# Requirement ID: FR_hybrid_7
- Description: [The system shall display premium plan price, billing period, and locked-feature list on the pricing page.]
- Source Persona: [P_hybrid_4 - Frugal Mental Health Enthusiast]
- Traceability: [Derived from review group H4]
- Acceptance Criteria: [If the user opens the pricing page, the system must display the price, billing period, and at least 1 locked feature for each premium plan shown on that page.]
- Notes: [FR_auto_7 required only wording and traceability refinement; the requirement intent was retained and the acceptance criteria were made more specific.]

# Requirement ID: FR_hybrid_8
- Description: [The system shall block access to locked premium insight content for users without an active paid subscription.]
- Source Persona: [P_hybrid_5 - Frustrated Mental Health Tracker]
- Traceability: [Derived from review group H5]
- Acceptance Criteria: [If a user without an active paid subscription selects locked premium insight content, the system must display a lock message and must not display the locked insight content.]
- Notes: [Rewritten from FR_auto_8 to remove the vague phrase “without incurring significant costs” and to make the locked-content behavior testable.]

# Requirement ID: FR_hybrid_9
- Description: [The system shall display 1 instruction block before first use of each tracking feature.]
- Source Persona: [P_hybrid_5 - Frustrated Mental Health Tracker]
- Traceability: [Derived from review group H5]
- Acceptance Criteria: [If the user opens a tracking feature for the first time, the system must display 1 instruction block before the user submits data for that feature.]
- Notes: [Rewritten from FR_auto_9 to remove the vague phrase “comprehensive support” and replace it with a measurable instruction-display requirement.]

# Requirement ID: FR_hybrid_10
- Description: [The system shall preserve each submitted check-in after the app is closed and reopened.]
- Source Persona: [P_hybrid_5 - Frustrated Mental Health Tracker]
- Traceability: [Derived from review group H5]
- Acceptance Criteria: [If the user submits a check-in, closes the app, and reopens the app, the submitted check-in must still appear in check-in history.]
- Notes: [FR_auto_10 was replaced because app-store rating is not a valid acceptance criterion for system reliability.]

# Requirement ID: FR_hybrid_11
- Description: [The system shall display at least 3 predefined discussion prompts on the therapy-preparation page.]
- Source Persona: [P_hybrid_1 - Self-Discovering User]
- Traceability: [Derived from review group H1]
- Acceptance Criteria: [If the user opens the therapy-preparation page, the system must display at least 3 predefined discussion prompts.]
- Notes: [FR_auto_11 was kept with only wording and traceability refinement because therapy preparation is still supported by the automated persona intent.]

# Requirement ID: FR_hybrid_12
- Description: [The system shall display at least 1 resource item for each selected support topic.]
- Source Persona: [P_hybrid_1 - Self-Discovering User]
- Traceability: [Derived from review group H1]
- Acceptance Criteria: [If the user selects a support topic on the resources page, the system must display at least 1 resource item associated with that topic.]
- Notes: [Rewritten from FR_auto_12 to remove the vague phrase “help manage mental health struggles” and replace it with a measurable topic-to-resource behavior.]

# Requirement ID: FR_hybrid_13
- Description: [The system shall display recorded mood entries from the previous 30 days.]
- Source Persona: [P_hybrid_3 - Mindful Tracker]
- Traceability: [Derived from review group H3]
- Acceptance Criteria: [If the user has recorded at least 1 mood entry in the previous 30 days and opens the mood-history page, the system must display all recorded mood entries from that 30-day period.]
- Notes: [Rewritten from FR_auto_13 to remove the unsupported requirement for a graph while preserving the original tracking-over-time intent.]

# Requirement ID: FR_hybrid_14
- Description: [The system shall allow the user to create, edit, and disable at least 1 daily reminder.]
- Source Persona: [P_hybrid_3 - Mindful Tracker]
- Traceability: [Derived from review group H3]
- Acceptance Criteria: [If the user opens reminder settings, the system must allow the user to create 1 daily reminder, edit its time, and disable it.]
- Notes: [Rewritten from FR_auto_14 to remove the vague phrase “daily life tracking feature” and keep only the measurable reminder behavior.]

# Requirement ID: FR_hybrid_15
- Description: [The system shall display the most frequently selected mood option for a user-selected date range.]
- Source Persona: [P_hybrid_3 - Mindful Tracker]
- Traceability: [Derived from review group H3]
- Acceptance Criteria: [If the selected date range contains at least 7 completed check-ins, the system must display the mood option with the highest selection count in that range.]
- Notes: [Rewritten from FR_auto_15 to replace the vague phrase “identify patterns” with a measurable pattern calculation.]
