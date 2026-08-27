# Pre-Final Product Acceptance Audit

## Scope and method

- Diagnostic only; no fixes, training, tuning, evaluation, or recommender changes were performed.
- Frozen manifest: 75 scenarios and 117 turns.
- Scenarios were saved before execution and then run sequentially through the live frozen API.
- Exact active state, response summary, returned IDs, and persisted price evidence were captured per turn.

## Result totals

- Total scenarios: 75
- Total turns: 117
- PASS: 27
- PARTIAL: 9
- FAIL: 37
- UNSUPPORTED: 2
- Pass rate excluding unsupported: 36.99%

## Failures by category

Counts below are non-pass turn observations, plus one cross-layer price-display finding and one authentication-UX finding.

- PARSER: 13
- STATE_MEMORY: 16
- PROFILE_PERSONALIZATION: 1
- FILTERING: 0
- RANKING: 0
- RESULT_REFERENCE: 5
- CONVERSATION_RESPONSE: 10
- OUTFIT: 5
- PERSISTENCE: 0
- PRICE_DISPLAY: 1
- DATA_LIMITATION: 2
- AUTH_UX: 1
- OTHER: 0

## Top critical defects

1. Budget removal and named relaxation phrases do not clear active constraints.
2. Genuine new shopping goals inherit obsolete brand, colour, and budget within the same chat.
3. Negative colour language can invert into a positive hard filter.
4. Preference language is treated as a hard current request and is not stored as a profile preference.
5. Outfit intent/pending clarification breaks across the requested natural three-turn flow.
6. Show-more, relative refinement, and ordinal result references do not operate on prior results.
7. Frontend price reconstruction rejects formatted historical price strings despite numeric persisted prices.

## Current capabilities that behave realistically

- Basic category, explicit brand, explicit colour, direct maximum/range budget parsing, and restrictive no-match behavior were reliable in the tested catalogue-grounded requests.
- Exact explicit brand replacement (Nike to adidas), colour replacement, and category replacement worked in tested cases.
- Three independent new-chat pairs showed no cross-chat leakage, and same-chat reselect preserved its state.
- The engine did not fabricate products for deliberately contradictory requests and did not affirm live stock, delivery, coupon, or current-price claims.
- Product cards are grounded in persisted Amazon catalogue IDs, links, ratings, review evidence, trust, and historical numeric prices.

## Capabilities missing for ChatGPT-style shopping

- Robust negation, constraint removal, and new-goal reset semantics.
- Pagination/show-more with unseen products.
- Relative sorting/refinement and references to prior ranked results.
- Product comparison grounded in prior results.
- Multi-product baskets with a shared budget.
- Stable natural-language outfit dialogue and outfit follow-up editing.
- Direct general advice and explicit unsupported-data explanations.
- Natural preference updates stored as soft personalization signals.
- Typo/casual-language normalization beyond basic product aliases.

## State, personalization, price, and authentication conclusions

- Cross-chat isolation status: **PASS in three independent pairs**. The supplied stale-budget observation was not reproduced across newly created chats; the serious contamination is reproducible within the same chat during new-goal transitions.
- Profile preference vs hard constraint status: **FAIL / not cleanly separated**. The audit user had no saved Nike preference; `I like Nike` created a hard active brand and no preference row. The supplied manual profile-promotion defect remains a critical known defect.
- Historical-price status: **FAIL in frontend reconstruction**. Across all persistence records, 1,287 recommendations had numeric price; 1,152 stored formatted historical strings in `card_json` that the frontend `toNumber` path cannot parse, producing `Historical price unavailable` even though numeric DB price exists.
- Authentication current fields: signup requires Username, Password, Confirm password; Display name and Email are optional. Login accepts Username or email plus Password.
- Can username be removed safely later: **REQUIRES MIGRATION**.
- Display-name greeting currently implemented: **NO**. Display name is returned and shown in the account/sidebar, but greeting text is generic.

## Recommended architecture changes — report only

1. Separate explicit hard constraints, negative constraints, soft profile preferences, and conversation-local refinements in typed state.
2. Add intent-level operations (`replace`, `clear`, `exclude`, `new_goal`, `paginate`, `reference_result`) instead of only merging extracted values.
3. Store result-set identity/order per turn for show-more, relative refinement, explanation, comparison, and link requests.
4. Preserve outfit pending-state fields across follow-ups and route outfit edits to a dedicated deterministic state machine.
5. Return numeric price and explicit `price_display` separately in the API contract; never require the frontend to parse decorated price strings.
6. Add an explicit data-availability response layer for stock, delivery, sizes, current price, and coupons.
7. Migrate authentication toward required unique email plus required display name, while retaining a legacy-username compatibility path.

## Integrity statement

- Files modified outside `Results/Pre_Final_Product_Audit`: none authored by this audit.
- `Thesis_clean.ipynb` modified: NO.
- Frozen model/recommender modified: NO.
