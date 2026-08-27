# ShopMate final application evaluation — corrected category oracle

> Supersedes the invalidated 20-scenario evaluation. The v2 suite adds real-API browser-regression cases and independent raw-metadata cross-category adversaries.

Date: 2026-08-27  
Suite: `Notebooks/shopmate_final_acceptance.py`

This evaluation is separate from the frozen offline recommender comparison.

| Metric | Result |
|---|---:|
| Scenarios | 35 |
| Recorded turns/checks | 48 |
| Scenario pass | 35/35 (100%) |
| Partial | 0 |
| Fail | 0 |
| Known hard-constraint violations | 0 |
| Hard-constraint satisfaction | 100% in covered returned-product turns |
| Pending-action failures | 0 in covered cases |
| State-transition failures | 0 in covered cases |
| Unsupported-request honesty | 4/4 covered scenarios |
| Outfit scenarios | 2/2 |
| Personalization scenarios | 2/2 |
| Cross-category adversaries | 13/13 persisted; 15/15 diagnostic |
| Mean measured HTTP latency | 3.983 s |
| Median measured HTTP latency | 0.859 s |
| Zero-result/check rows | 25/48 |

Product oracles use raw title/main-category evidence plus trusted evidence rather than displayed Match/Trust labels. Zero results are accepted when evidence cannot establish all hard constraints; results are not padded.

Authentication was independently exercised with a new test account: signup and login succeeded, a new chat was created, a request produced two persisted messages, and the selected chat reloaded with those messages.

Artifacts: `acceptance_turn_results.csv`, `acceptance_scenario_summary.csv`, `acceptance_summary.json`, and `acceptance_report.md` under `Results/Final_Application_Acceptance`.
