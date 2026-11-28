# Integration handoff — 28 November 2026

Based on GitHub main commit b30519d6bf42e7b335c8aa174604ccf7664ebe5f.
Prepared in a separate clone; Jordi's original clone and teammates' source files
were not overwritten. No model retraining was performed.

Changed: app.py, README.md.
Added: real_data.py, test_real_data.py, requirements.txt, .gitignore, transport.db.
The transport database was generated using the team's existing pipeline and
transport.opendata.ch. The tariff input CSV was not modified or independently
verified against the current official tariff page. Its validity dates are checked.

AI log entry to add to the shared tracker:
2026-11-28 | Jordi Martinez | ChatGPT | Implemented real SQLite listing and
saved-model integration; gross rent-per-m² conversion; tariff/route joins;
missing-data handling; Streamlit filters/ranking and integration tests.
Generated code used: Yes. Code acknowledgement: Yes.
Jordi should review and run the app before claiming human verification.

Limitations: listing availability is not refreshed automatically; the route CSV
covers only 19 municipalities; no invented mapping for uncovered places; vehicle
costs and absent vehicle routes need user input. Some predictions are on training
rows. The original CSV is required to reconstruct missing model metadata.
