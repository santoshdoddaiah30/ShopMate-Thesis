# ShopMate application performance report

Date: 2026-08-27

## Before and after

| Measurement | Before | Final measured |
|---|---:|---:|
| Cold unique search | 35–60 s (one observed ~79 s) | cold path can still exceed 30 s |
| N24M2 index reconstruction | ~51 s | 43.648–69.804 s |
| Warm deterministic request | ~0.508–0.600 s | median 0.609 s |
| Acceptance-suite mean | not established | 2.246 s |
| Outfit initial request | not established | 33.635 s |
| Outfit follow-up | not established | 0.866 s |

Final acceptance comprised 31 real HTTP turns. The higher 2.246-second mean is driven by cold/outfit work; the median reflects the deterministic fast path.

## Stage findings

The runtime exposes interpretation and follow-up timings for outfit turns, but a complete nine-stage telemetry contract is not uniformly emitted by every legacy path. Evidence supports these conclusions without inventing unavailable stage numbers:

1. Language interpretation: deterministic N24N paths avoid unnecessary response-only Qwen calls.
2. State transition: deterministic and sub-second within warm end-to-end requests.
3. Candidate generation: dominant on cold unique searches and outfit construction.
4. Trusted eligibility: cached index makes warm filtering fast; reconstruction costs about 52–69 s.
5. Visual verification: local deterministic PIL/NumPy cache; no per-product LLM calls.
6. Frozen ranking: retained unchanged and participates after eligibility.
7. Response composition: deterministic grounded fast path used where possible.
8. Persistence: authenticated reload succeeded; included in HTTP timings.
9. API serialization: included in HTTP timings, not independently emitted.

Safe optimizations implemented or retained: deterministic intent/composition fast paths, reusable trusted lookup structures, visual evidence caching, no Qwen filtering, no per-product Qwen calls, and no alteration of frozen ranking parameters.
