# ShopMate N24 implementation documentation

## Data and frozen recommender

ShopMate uses a processed 65,546-row historical Amazon 2023 catalogue stored and queried with DuckDB. Preprocessing normalizes identifiers, titles, categories, brands, historical price, rating, review count, URLs, and available attribute evidence. Catalogue construction preserves source provenance and distinguishes missing/unknown evidence from verified values.

The frozen hybrid recommender has three components: content similarity, collaborative filtering for profiles with historical factors, and popularity. Their fixed weights are 0.2, 0.1, and 0.7. Reciprocal-rank fusion uses k=60, 500 candidates per source, and 16 latent dimensions. N23 remains the frozen offline comparison baseline; the application work does not claim universal dominance over baselines.

## Conversational architecture

The final application chain is N24L → N24M → N24M2 → N24M3 → N24N. N24A–N24K established typed state, grounded orchestration, outfit integration, historical-price messaging, and authentication. N24L activates the real FastAPI path. N24M adds complete product semantics and eligibility, N24M2 adds trusted evidence/provenance, N24M3 adds cached local visual-colour protection and contextual relaxation, and N24N supplies the final deterministic conversation/pending-action planner.

Qwen3:8b runs locally through Ollama and is used for ambiguous language interpretation where needed. It is not an eligibility oracle, not called per product, and not used for filtering. Deterministic state transitions and grounded composition fast paths cover unambiguous turns.

Hard constraints (category, exact brand, evidenced colour, audience, historical price and rating thresholds) are enforced before presentation and override soft preferences. Soft saved preferences influence ranking only when compatible. Collaborative filtering participates only where historical user factors are available. Search reformulation clears stale constraints when the utterance signals replacement; refinement retains relevant state. Result-set memory supports pagination, ordinal references, questions, and comparisons without mutating hard search state.

N24M2 records evidence source types and prevents brand/model tokens—such as WHITE MOUNTAIN or White Ledge—from becoming colour evidence. UNKNOWN is excluded from strict exact matching. N24M3 can use deterministic image-derived colour evidence, caches it locally, excludes visual conflicts from strict results, and offers only catalogue-backed relaxations. N24N represents colour intent explicitly as STRICT, MIXED_ALLOWED, or MONOCHROME and consumes chat-scoped pending actions at most once.

Outfits reuse the frozen retrieval/scoring/construction pipeline to assemble real catalogue tops, bottoms, and footwear under audience and budget constraints. Occasion and destination are contextual signals, not invented product facts. Follow-up replacement, comparison, information, and alternative-outfit turns operate on persisted outfit state.

## Application stack and persistence

FastAPI exposes authentication, session, chat, and message endpoints. The React frontend consumes these endpoints at localhost:3000. DuckDB persists accounts, profile linkage, chats, messages, result cards, active request state, pending actions, and outfit state. Signup/login use the N24K email/display-name contract. Reload tests verify existing conversations can be selected and reconstructed.

## Evaluation and performance

The application evaluation is independent of the frozen offline evaluation. A reproducible real-HTTP suite records scenario/turn identifiers, expected behavior, status, hard state, returned IDs, independent constraint checks, latency, verdict, and notes. It covers basic search, combined constraints, refinement, reformulation, pagination, questions, comparison, pending actions, unsupported requests, outfits, personalization, and persistence.

Final results are 20/20 scenarios and 31 turns passed, with zero known hard-constraint violations. Mean latency is 2.246 s and median latency 0.609 s. Initial outfit construction measured 33.635 s, while its follow-up measured 0.866 s. Trusted-index reconstruction measured about 52–69 s. The warm improvement comes from deterministic fast paths, reused indexes, and caches; frozen ranking parameters were not changed.

## Limitations and reproducibility

Only 4,049 catalogue rows (6.18%) have structured trusted colour evidence, so strict colour requests often return no results. Historical data cannot establish live stock, current delivery, coupons, live prices, or exact size availability. Visual evidence is conservative and unknown evidence is never promoted to exact. Cold startup remains slow because notebook load cells run substantial regression workloads.

To reproduce: use `Notebooks/Thesis_clean.ipynb`; restore the frozen/base runtime, then N24L, N24M, N24M2, N24M3, N24N, and cell 421; run `Notebooks/shopmate_final_acceptance.py`; inspect artifacts in `Results/Final_Application_Acceptance` and `Results/Final_Application_Evaluation`. The app should remain available at `http://localhost:3000` with the API at `http://127.0.0.1:8000`.
