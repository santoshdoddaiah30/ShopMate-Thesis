# SECTION 153E7N24M — Final Validation Summary

- Catalogue: 65,546 real products.
- Capability registry: `n24m_catalogue_capabilities_v1`.
- Eligibility engine: `n24m_deterministic_eligibility_v1`.
- Deterministic properties: 272/272 PASS in 13.589 seconds.
- Live natural-language acceptance: 53/53 exact PASS.
- Additional required examples: 20/20 PASS.
- Exact manual live API regression: PASS; 0 eligible, 0 returned, 0 hard or match-label violations.
- Frozen 75-scenario replay: 73 PASS, 2 PARTIAL, 0 FAIL, 0 UNSUPPORTED; 97.33% supported pass rate.
- N23 golden A–E: all PASS.
- N24 recommendation/show-more/reference/comparison/preference/outfit/price/auth/persistence regressions: all PASS.
- Cross-chat leakage: 0.
- Fabricated product facts: 0.
- Critical hard-constraint failures: 0.
- Deterministic eligibility scan: 228.417 ms average over 20 full 65,546-row scans; 0 additional LLM calls.
- Development engine: N24; local `qwen3:8b` response composer restored.

## Genuine limitations

- Explicit derived colour evidence covers 17.47% of products; unknown colour is excluded from strict exact results.
- Material evidence covers 7.09% and remains soft-only.
- Historical size evidence covers 2.82%; current size availability remains unsupported.
- General style and occasion metadata are sparse and remain contextual unless an exact structured subcategory exists.
- No live stock, delivery, coupon, or current-price feed exists.
- Shared-budget multi-product basket optimization remains unsupported.

## Runtime verification

- Backend OpenAPI: HTTP 200 on PID 2592.
- Frontend: HTTP 200 on PID 23812.
- `SHOPMATE_ENGINE=n24`.
- Frozen N23 controller preserved.
