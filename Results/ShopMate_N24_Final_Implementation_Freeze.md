# ShopMate N24 final implementation freeze

Freeze date: 2026-08-27  
Status: **PASS — reissued after cross-category correction**

> Supersedes the revoked freeze. The contaminated razor/shirt case is corrected and covered by real-API plus independent raw-metadata regression tests.

## Authoritative implementation

- Notebook: `Notebooks/Thesis_clean.ipynb`
- Runtime chain: N24L → N24M → N24M2 → N24M3 → N24N
- Final resolver: notebook cell 421
- Runtime modules: `shopmate_n24m_complete_product_semantics.py`, `shopmate_n24m2_truth.py`, `shopmate_n24m3_visual_relaxation.py`, `shopmate_n24n_conversation_planner.py`
- Validation modules: `shopmate_n24n_validation.py`, `shopmate_final_acceptance.py`

## Frozen recommender contract

N23 remains callable and unchanged as the thesis comparison baseline. Content weight 0.2, collaborative weight 0.1, popularity weight 0.7, RRF k=60, 500 candidates/source, and 16 latent dimensions. No retraining or retuning was performed.

## Catalogue and capabilities

The processed catalogue contains 65,546 historical Amazon 2023 products. Supported application behavior includes grounded product retrieval, trusted hard-constraint filtering, audience/brand/price/rating handling, strict/mixed/monochrome colour modes, visual conflict protection, result memory, comparisons, pending relaxations, outfits, soft preferences, authentication, and persistent chats.

Unsupported live facts include current stock, delivery dates, coupons, live prices, real-time availability, and exact size availability. The assistant must identify these as unavailable historical-catalogue facts.

## Acceptance and performance

Final acceptance v2: 35/35 scenarios passed, 48 recorded turns/checks, zero known hard-constraint violations, mean measured HTTP latency 3.983 s, median 0.859 s. Thirteen persisted and fifteen diagnostic raw-metadata cross-category adversaries passed. Cold/index-heavy paths remain expensive; uncached black-shirt frozen ranking measured 33.181 s and trusted eligibility 0.322 s.

Controlled fresh-kernel restoration completed through N24N with intended bindings, N23 goldens passing, and the API subsequently restored. Two consecutive resolver calls returned `ok=true` with identical bindings. See `Results/Final_Application_Acceptance/cold_start_report.md`.

## Local model

Qwen3:8b is served locally through Ollama for language interpretation where required. Deterministic fast paths handle supported unambiguous turns; Qwen is not used per product or for eligibility filtering.

## Limitations

- Trusted structured colour coverage is 4,049 products (6.18%); UNKNOWN never becomes EXACT.
- Historical catalogue evidence cannot support live commerce facts.
- Some legitimate strict queries return zero results because evidence is missing.
- Cold startup is long because notebook cells contain embedded regression workloads and repeated index construction.
- One legacy cold-load Nike anchor fixture currently reports no result set; it is guarded and non-fatal, while independent end-to-end coverage passes.

The N24M2 category contract now rejects a raw hierarchy when independent main-category/title/detail evidence proves a mutually exclusive product family. See `Results/Final_Application_Acceptance/category_defect_resolution.md`.

No further architectural change is authorized after this freeze unless a concrete regression is demonstrated.
