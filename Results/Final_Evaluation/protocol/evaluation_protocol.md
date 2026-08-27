# Final N23 application evaluation protocol

## Scope and freeze rule

This is an evaluation-only protocol for the frozen ShopMate implementation at `SECTION 153E7N23 — FINAL APPLICATION FREEZE`. The tested startup sequence is:

`397 → 398 → 399 → 400 → 396 → 394 → 395 → 401`

No recommender model, artefact, configuration, threshold, ranking rule, filtering rule, parser, application wrapper, database schema, or scenario may be changed after this protocol is saved. Failures are recorded exactly as observed.

Frozen hybrid configuration: content 0.2, collaborative 0.1, popularity 0.7, RRF k=60, and 500 candidates per model. The source data are the Amazon Reviews 2023 Clothing, Shoes and Jewelry catalogue; the frozen runtime catalogue artefact is `Datasets/Processed/cf_content_documents.parquet` (65,546 rows).

## Protocol contents

The fixed manifest defines 22 single-turn application scenarios, 9 conversational-memory scenarios, 7 outfit scenarios, and 5 repeated-run performance scenarios. It was saved before execution at `protocol/application_scenario_manifest.json`.

Each application scenario uses a fresh chat. Conversational and outfit scenarios use the same chat only where their ordered turns require retained state. The cross-chat scenario uses explicitly separate chats. Every response is checked against the predeclared expected constraints, not criteria derived from its observed output.

No-exact-match scenarios pass only when ShopMate clearly reports no exact match, returns no fabricated product, and does not silently relax an explicit brand, category, colour, or budget requirement.

## Application metrics

`constraint_satisfaction_rate = satisfied explicit constraints / evaluated explicit constraints`

Report category, brand, colour, budget, recipient, and objectively testable occasion rates separately. Also report exact-match integrity, no-fabrication, and scenario pass rates. Use numeric historical price fields and real product identifiers; formatted price strings are display-only.

## Conversational metrics

For each turn, compare the persisted active state with the state declared in the manifest before execution. Report turn-level state accuracy, scenario success rate, retention accuracy, replacement/removal accuracy, new-goal reset accuracy, chat-isolation success, and reload-memory success.

## Outfit metrics

Each outfit scenario begins without recipient information and must first request `outfit_recipient`. After recipient resolution, evaluate recipient compatibility, clarification accuracy, three-look availability, all five slots (`top`, `bottom`, `footwear`, `outerwear`, `accessory`), within-look uniqueness, catalogue validity, numeric budget and remaining-budget correctness, 15-row persistence, 3×5 grouped reload, and pending-state clearing. If the frozen catalogue cannot produce a complete outfit, record that limitation rather than altering the scenario.

## Performance protocol

P1–P5 use one warm-up plus five measured runs per scenario. Each measured run creates a fresh chat and fresh generation; no cached or existing response counts. Record the first valid request after a fresh N23 kernel/API startup separately as cold-start evidence.

For every measured scenario, report backend generation time from `performance.total_seconds` separately from client-measured API end-to-end wall time. Report count, mean, median, standard deviation, minimum, maximum, p90, and p95. For two-turn flows, preserve individual turn timing and sequence timing.

## Offline metrics provenance

Do not rerun any model. The primary offline comparison is the frozen positive-test table at `Results/Tables/positive_test_model_comparison.csv`; the authoritative full metric source is `Datasets/Processed/final_test_model_metrics.parquet`. No Precision@K, Recall@K, or MAP@K values are to be invented. Any later derived metric must come only from `final_test_user_ranks.parquet` and be labelled post-hoc.

## Output locations

Save only evaluation outputs under `Results/Final_Evaluation/`:

- `application/` for scenario and constraint results;
- `outfit/` for outfit and grouped-reload results;
- `performance/` for raw runs and summaries;
- `offline/` for references or copied final metric tables with provenance;
- `figures/` for final evaluation figures;
- `protocol/` for this immutable protocol and manifest.
