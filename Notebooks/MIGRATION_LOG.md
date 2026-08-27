# ShopMate Architecture Consolidation — Migration Log

Started: 2026-08-27, following an independent read-only architecture audit.
Baseline backup: `Notebooks/migration_baseline_20260827_105021/` (5 N24 layer
files + `Thesis_clean.ipynb.baseline`, an exact copy of the notebook before
any consolidation edits).

Takeover snapshot: `Notebooks/takeover_snapshot_20260827_122900/` preserves
the exact partial-consolidation files found when Codex resumed the migration,
before the subsequent coherent consolidation changes.

## N23 frozen baseline (verified, must remain unchanged)

From `final_hybrid_configuration` (DuckDB), queried 2026-08-27:

- content_weight = 0.2, collaborative_weight = 0.1, popularity_weight = 0.7
- rrf_constant = 60, candidates_per_model = 500
- validation_ndcg_at_10 = 0.011416, validation_hit_rate_at_10 = 0.019058
- N24I_N23_GOLDEN_REPORT at baseline: {A: true, B: true, C: true, D: true, E: true}

## Known defects at start of migration

1. **Pending offer never persisted.** `n24l_save_persistent_state` payload has
   no field for the N24M3/N24N pending-relaxation offer; it lives only in the
   in-memory `N24M_CHAT_CONSTRAINTS[chat_id]["pending_relaxation"]`. Lost on
   chat reload / kernel restart before the user even answers.
2. **Pending-offer grammar is a closed phrase whitelist.** Both
   `_N24M3_AFFIRMATIVE` and today's `_N24N_AFFIRMATIVE` use `.fullmatch()`
   against fixed alternatives. `"yes, show me those"` matches neither (comma
   breaks fullmatch) and falls through to ordinary interpretation, silently
   discarding the offer.
3. **N24N's compose override shadows N24M3's broader relaxation offers.**
   N24M3's `_n24m3_offer_from_orchestration` supports CLEAR_BUDGET,
   CLEAR_BRAND, BROADEN_CATEGORY in addition to colour, but N24N's
   `_n24l_compose` intercepts `status == "no_exact_match"` before ever
   reaching N24M3's version, so only colour relaxation is reachable today.
4. **No canonical product semantics.** `N24ProductEligibilityEvidence` (N24M)
   and `N24TrustedEligibilityResult` (N24M2) are two incompatible per-product
   evidence shapes; N24M2's shadows N24M's at runtime but N24M's class/
   registry/`_N24M_CATEGORY_ALIASES` are still live, unused-but-present code.
5. **No canonical taxonomy.** At least 4 independent category implementations
   (N24L text-guess, N24M alias table, N24M2 family/listing decision, outfit
   `OUTFIT_SLOT_CATALOGUE_MAP`/`N13_SLOT_ALLOWED_TERMS`) that disagree on the
   same word (e.g. "jacket").
6. **Outfit pipeline fully disconnected from N24M2.** Zero references either
   direction between the outfit bundle (notebook cell 394) and
   `evaluate_n24_trusted_eligibility`/canonical semantics.
7. **Test oracle circularity.** `shopmate_n24m2_oracle.py` calls
   `evaluate_n24_trusted_eligibility` (production) as its own ground truth in
   15+ places.
8. **Raw category contamination confirmed.** B0743MHZX2 ("Razor for Men",
   brand Gillette, main_category "All Beauty") carries a raw category path
   ending in `Shirts > T-Shirts`. Independent heuristic found 207 similar
   rows in the raw 1,527,054-row `products_clean` table.

## Stage status

- [x] Stage 0 — Baseline/backup, defect log, N23 snapshot (this document)
- [x] Stage 1 — Canonical semantics + declarative taxonomy implemented; live cold-start verification pending
- [x] Stage 2 — Unified ConstraintEvaluation entry point shared by eligibility/cards/outfit filtering
- [x] Stage 3 — Canonical request state directly persisted; legacy sidecar payload is read-only migration input
- [x] Stage 4 — PendingOffer persisted with concrete IDs/evidence and exact replay; persistence is fail-closed
- [x] Stage 5 — Outfit slot candidates pass through the shared canonical constraint evaluator
- [x] Stage 6 — Stable pre-layer base registry prevents warm-reload self-capture recursion
- [x] Stage 7 — Independent source/raw-catalogue/generated-language suite: 15/15 groups pass
- [ ] Stage 8 — Real /api/messages end-to-end acceptance
- [ ] Stage 9 — Freeze artifacts (deferred until all prior stages verified)

## Takeover findings and recovery

- The partial migration was **substantial**, but a live `black shirt` request
  failed after 47.30 seconds with `maximum recursion depth exceeded`.
- Inspection proved `n24m_pre_build_request` had captured an older N24M
  wrapper instead of the frozen N24C request compiler. The same reload-order
  risk affected other pre-layer application bases.
- `N24_APPLICATION_BASES` now records genuine pre-N24M entry points on first
  cold load and restores them deterministically on every layer reload.
- The corrupted legacy kernel was stopped only after source, notebook, and
  both rollback snapshots were safely on disk. A reviewed load-only cold
  start (runtime cells 394 and 396–421) is in progress for live acceptance.
- `shopmate_semantic_consolidation_tests.py` independently verifies frozen
  parameters, the raw Gillette razor contradiction, taxonomy structure,
  absence of ASIN-specific production exceptions, durable pending snapshots,
  canonical persistence, outfit integration, and generated pending intent
  language. It does not call production eligibility to establish expected
  catalogue truth.
