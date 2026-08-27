# ShopMate controlled cold-start report

Date: 2026-08-27

Status: **PASS with one non-blocking legacy fixture warning**.

The authoritative notebook `Notebooks/Thesis_clean.ipynb` was restored in a genuinely fresh Jupyter kernel using the targeted dependency order (frozen/base runtime, N24L, N24M, N24M2, N24M3, N24N, resolver). The primary API was stopped only while DuckDB ownership was handed to the fresh kernel, then restored.

## Evidence

- Final engine: `n24`.
- Catalogue rows: 65,546.
- N24M2 trusted eligibility: loaded; contract tests passed.
- N24M3 visual protection: loaded; frozen ranker unchanged.
- N24N planner: loaded; deterministic planner tests passed.
- Resolver: completed and resolved N24N/M2/M3 bindings.
- Resolver idempotency: two consecutive live-kernel calls both returned `ok=true` with identical bindings.
- N23 golden harness: passed during the cold run.
- Live outfit matrix: four complete real-catalogue fixtures, two honest no-valid-outfit outcomes; no fabricated product IDs.
- Primary service restored afterward and `/openapi.json` plus authenticated persistence checks succeeded.

## Measured cold cell timings (seconds)

| Cell | Purpose | Seconds |
|---:|---|---:|
| 397 | Frozen artefact foundation | 1.320 |
| 398 | N19A | 13.311 |
| 399 | N19B | 0.744 |
| 400 | N19C | 0.018 |
| 396 | N14 | 0.006 |
| 394 | N18H | 0.033 |
| 395 | N18H1 | 0.005 |
| 401 | N20 | 8.646 |
| 403 | N24A | 54.719 |
| 404 | N24B | 56.495 |
| 405 | N24C | 333.672 |
| 406 | N24D | 197.101 |
| 407 | N24E | 136.349 |
| 408 | N24F | 123.633 |
| 409 | N24G | 54.264 |
| 410 | N24H | 0.015 |
| 411 | N24I | 0.003 |
| 412 | N24I auxiliary | 0.009 |
| 413 | N24I integration | 56.734 |
| 414 | N24I1 live regression | 450.473 |
| 415 | N24J price contract | 54.431 |
| 416 | N24K auth migration | 62.552 |
| 417 | N24L activation | 0.160 |
| 418 | N24M semantics | 47.926 |
| 419 | N24M2 truth index | 53.203 |
| 420 | N24M3 visual layer | 0.113 |
| 421 | Final resolver/reload | 69.340 |

Cell 414's fixed Nike anchor query returned no result set and therefore recorded `live_anchor=false`. The repaired guard converts this dataset-dependent empty fixture into a structured report instead of aborting startup. Independent application acceptance verifies real search, grounded comparisons, outfits, hard constraints, and persistence.

The dominant cold cost is embedded live regression work and repeated index/retrieval construction. It is not representative of warm API latency.
