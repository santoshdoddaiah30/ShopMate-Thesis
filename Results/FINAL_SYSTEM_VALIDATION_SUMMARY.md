# ShopMate Final System Validation Summary

## Validation Date

2026-08-28

## Frozen Recommendation Configuration

- Content weight: 0.2
- Collaborative weight: 0.1
- Popularity weight: 0.7
- Weighted RRF k: 60
- Candidate depth per source: 500
- Latent dimensions: 16
- Catalogue / product-index rows: 65,546

This configuration was not changed, retrained, or retuned at any point during the
semantic-consolidation work verified below.

## Batch 1 — Conversational State and Follow-Up Handling

Verified against the live `/api/messages` backend:

- PendingOffer creation, persistence, and chat-reload/switch survival
- Exact stored-candidate-ID replay on acceptance (no re-ranking, sub-second)
- Consumed-offer / double-acceptance handling (graceful clarification, no new
  offer, no new ResultSet)
- Normal ResultSet creation and persisted ordering
- Empty "show more" preservation of the prior immutable ResultSet
- Ambiguous-comparison clarification ("compare", "compare these") instead of
  a raw HTTP 400
- Out-of-range comparison-reference hardening (e.g. requesting a position
  beyond the active ResultSet's size) resolved as a graceful clarification
- "cheaper" and "higher rated" refinements resolving against the correct
  source ResultSet with correct parent/child lineage
- "why this" / "why these" grounded, evidence-based explanations with no
  fabricated product claims
- ResultSet lineage audit (parent/child chain correctness, immutability of
  historical snapshots)
- No DataFrame / missing-column HTTP 400 regressions for compare, cheaper, or
  higher-rated follow-ups

**Result: PASS**

## Batch 2 — Canonical Product Semantics and Outfit Parity

Verified using independent raw-catalogue evidence (not production output) as
the expected-answer oracle:

- Razor-as-shirt contamination (B0743MHZX2) correctly rejected via
  independent title/brand evidence overriding a contaminated category
  hierarchy
- Macebell-as-shirt contamination (B099PFXRWB) correctly rejected via the
  same independent-evidence mechanism
- Red-dress and red-shirt requests preserve product-family boundaries; no
  colour relaxation was ever offered without independent verification, and
  no unrelated merchandise (e.g. phone cases, electronics) was returned
- WHITE MOUNTAIN / Timberland "White Ledge" colour-token contamination
  prevented — brand/model text containing "White" does not establish
  canonical colour; affected products remain colour-UNKNOWN and ineligible
  for white-colour requests
- MEN and WOMEN audience requests returned no cross-contaminated products;
  the one UNISEX_ADULT result observed is a declared-compatible audience
  under the existing contract, not a contamination
- No dedicated kids-contamination fixture exists in the codebase; kids/
  toddler/boys/girls exclusion from adult audience requests was confirmed
  both structurally (declared compatibility sets) and empirically (zero such
  products across audience test samples)
- Women's outfit and men's budget outfit (under $150) scenarios: all outfit
  products independently re-verified via the same canonical evaluator used
  for ordinary recommendations (no separate, weaker outfit-only truth path)
- Strict all-black women's outfit: zero complete looks returned rather than
  padding with unverified merchandise — the correct outcome per the
  project's precision-first design
- UNKNOWN attribute evidence never promoted to EXACT in any sampled case;
  Match 100 only observed where independent structured evidence supported
  every hard constraint

**Result: PASS**

## Batch 3 — Final Independent and Adversarial Validation

- Final API route and health check: exactly one `POST /api/messages` route,
  correct endpoint identity, backend healthy, database connected
- Realistic multi-turn scenario (search → refine → explain → compare → show
  more) produced coherent ResultSet lineage throughout, with no fabricated
  claims and no unintended re-ranking on referential follow-ups
- Full PendingOffer lifecycle re-verified end-to-end, including exact
  stored-ID equality between offer creation and acceptance
- Independent DuckDB raw-field spot checks cross-validated against canonical
  and production eligibility for a representative product sample
- UNKNOWN-evidence sample: 0 of 4 observed UNKNOWN-evidence cases were
  promoted to EXACT
- CLEAR_BUDGET relaxation isolation directly verified from the persisted
  offer's own stored constraints: only the budget dimension changed;
  category and colour constraints were preserved byte-for-byte
- No invalid padding observed in any zero-result or zero-look scenario
- PendingOffer and ResultSet persistence structures inspected directly and
  found intact (offer_id, constraints, candidate IDs, evidence, consumed
  state; ResultSet id, ordering, lineage)
- Final N23 golden regression: 5/5 scenarios passed against the existing,
  unmodified golden harness
- Contamination regression (razor, macebell, colour-token fixtures)
  re-confirmed unchanged from Batch 2
- Runtime contract: all N24 layer source files compile cleanly; current
  bindings correctly resolve to their intended layer files; no wrapper
  multiplication observed
- HTTP error handling: ambiguous compare, out-of-range compare reference,
  and repeated PendingOffer acceptance all return HTTP 200 with a
  conversational clarification — no raw Python exception text or internal
  error codes (e.g. `ORDINAL_OUT_OF_RANGE`) are exposed to the client
- Historical-price truth contract: every card observed across this
  validation consistently labels prices as historical dataset values, with
  no claim of current price, live availability, current delivery, current
  inventory, or current coupons/discounts
- Git/artifact integrity: no unexpected source or notebook changes; frozen
  N23 artifacts unchanged

**Result: PASS**

## Final Frozen N23 Regression

5 of 5 established golden scenarios (A–E) passed against the unmodified N23
golden harness, with the frozen configuration values, latent-factor shape
`(65546, 16)`, and product-index row count (65,546) all confirmed exactly as
specified above.

The semantic and conversational layers built during this consolidation
(N24A through N24N, including the L→M→M2→M3→N canonical-semantics chain) did
not modify the frozen N23 ranking configuration, model artifacts, or
candidate-generation logic at any point.

This document does not claim that the hybrid N23 configuration universally
outperforms every baseline; it records only that the frozen configuration's
established golden-scenario behavior is unchanged.

## Known Limitations

1. Semantic recommendation latency remains relatively high for some
   operations (ordinary recommendation searches, and no-match/relaxation-
   offer creation in particular) — a performance characteristic, not a
   correctness defect. Representative observed values: ordinary
   recommendation ~43–49s; no-match with relaxation-offer creation ~111.8s;
   PendingOffer stored-ID acceptance ~0.56s; outfit generation ~24–55s.
2. The explicit N24 runtime bootstrap is functionally idempotent on repeated
   invocation (verified: no wrapper multiplication, no compose cycles, no
   stale captured-base references, frozen N23 identity unchanged) but each
   invocation remains computationally expensive (a full catalogue-attribute
   audit rebuild), not currently optimized for cheap repeated calls.
3. A genuine `RELAX_COLOUR` PendingOffer could not be triggered through live
   testing despite multiple attempts across varied colour/category
   combinations; only `CLEAR_BUDGET` relaxation isolation has been directly
   verified against a live, persisted offer. `RELAX_COLOUR` isolation logic
   exists in the codebase but is not independently confirmed by a live
   triggered example in this validation.
4. All displayed prices are historical values drawn from the Amazon Reviews
   2023 dataset snapshot, not current or live prices.
5. Current inventory, delivery estimates, coupons, and discounts are not
   verified or claimed by the system at any point.
6. This evaluation is bounded by the available Amazon Reviews 2023 subset
   (All Beauty, Amazon Fashion, Clothing/Shoes/Jewelry categories) and by the
   specific scenarios exercised across Batches 1–3; it is not an exhaustive
   catalogue-wide audit.

None of the above are failed acceptance tests — each corresponds to a
scenario that either passed with a recorded caveat or was not exercised live
during this validation.

## Final Status

BATCH 1: PASS
BATCH 2: PASS
BATCH 3: PASS
N23 GOLDEN: 5/5 PASS
FINAL SYSTEM VALIDATION: READY TO FREEZE
