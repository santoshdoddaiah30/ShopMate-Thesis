# ShopMate final implementation freeze

Frozen on 2026-08-20 (Europe/Berlin) after a fresh-kernel regression proof.

## Startup

From a fresh notebook kernel, execute only these saved cells in order:

`397 → 398 → 399 → 400 → 396 → 394 → 395 → 401`

This restores the saved application foundation, conversational wrappers, outfit runtime, persistent storage/reload layers, N20 instrumentation, N21 request-scoped reuse, and N22 frozen metadata index. Start the FastAPI application from the restored `shopmate_api` object; the React application remains the existing `Frontend/ShopMate` project.

## Frozen configuration

The saved `final_hybrid_configuration.json` remains the sole configuration source:

| Setting | Frozen value |
| --- | ---: |
| Content weight | 0.2 |
| Collaborative weight | 0.1 |
| Popularity weight | 0.7 |
| RRF k | 60 |
| Candidates per model | 500 |

No train/test split, model artefact, model weight, ranking rule, or offline metric was changed during stabilization or optimization.

## Restored runtime architecture

The cold-start notebook now restores the full production path:

`Persisted artefacts + DuckDB → request parser/profile memory → request-aware hybrid retrieval → filtering/ranking → final cards → conversational response → persistent chat/API → React workspace`

Key restart-safe layers include the N5/N8 conversational and active-memory stack; N18E/M2 outfit clarification and chat-pending bridge; N18H outfit composition; N18L 15-row outfit persistence; N18O grouped reload; N19/N19A/N19B/N19C load-only foundation; and the N20/N21/N22 performance layers.

## Optimizations retained

- **N20** — request-scoped generation timing (`request_performance_v1`).
- **N21** — immutable, request-scoped parser/candidate reuse (`request_scoped_reuse_v1`).
- **N22** — frozen exact metadata-match index (`frozen_metadata_match_index_v1`), with semantic equivalence and the non-default candidate-limit safeguard retained.

These layers reduce duplicated work only. They do not change recommendation inputs, candidate order, scores, model configuration, persistence schema, or returned cards.

## Performance

Frozen N20 generation baselines from the final Phase 2 proof:

| Scenario | Before | Final generation baseline |
| --- | ---: | ---: |
| Nike shoes under $100 | 15.74 s | 0.88 s |
| T-shirts around $50 | 18.45 s | 0.85 s |
| Black Nike shoes under $40 | 30.81 s | 2.60 s |
| Increase budget to $80 follow-up | 30.95 s | 2.56 s |
| Complete 3×5 outfit | 105.60 s | 7.10 s |

The final API regression also completed successfully. Its external HTTP wall times were recorded separately because they include the API/controller boundary: Nike 2.56 s, T-shirts 2.53 s, memory turn 1 3.97 s, memory turn 2 4.36 s, outfit turn 2 8.76 s.

## Final fresh-kernel regressions

| Check | Result |
| --- | --- |
| Fresh saved manifest and FastAPI start | PASS |
| Nike shoes under $100 | PASS — 10 Nike footwear cards, numeric historical prices ≤ $100 |
| T-shirts around $50 | PASS — request state retained T-Shirts/Shirts and $50 maximum |
| Black Nike shoes under $40 → budget $80 | PASS — Nike, black, Shoes retained; $40 replaced by $80 |
| Makeover clarification → Men | PASS — 3 complete outfits returned |
| Ordinary persistence/reload | PASS — flat `products` mode, 10 stored rows |
| Outfit persistence/reload | PASS — 15 stored rows, 3 groups × 5 products, pending state cleared |
| Frontend TypeScript check | PASS (`npm.cmd run typecheck`) |
| Frontend contract | PASS — `products` and `outfit` modes remain distinct; price and generation-time mappings are present in the served frontend |

For the validated outfit response, all groups had the five required slots, unique catalogue product IDs, Amazon links, valid historical prices, and totals of $189.48, $217.81, and $198.13 — all inside the $500 budget.

## Known limitations

- Prices are historical Amazon Reviews 2023 dataset values, not live prices or availability.
- The backend is intentionally notebook-kernel hosted for the thesis prototype; FastAPI must be started from the initialized kernel.
- Performance baselines are environment- and cache-sensitive; no further optimization should be made without first profiling and re-running the frozen regression suite.

## Change-control guidance

`SECTION 153E7N23 — FINAL APPLICATION FREEZE` in `Notebooks/Thesis_clean.ipynb` is documentation only. Do not alter the saved startup stack, frozen configuration, or active wrappers without a new clean-kernel proof covering ordinary recommendations, active memory, outfit clarification/generation, 15-row persistence, and 3×5 reload.
