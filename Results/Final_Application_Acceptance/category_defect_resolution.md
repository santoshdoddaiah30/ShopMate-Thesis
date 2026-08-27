# Cross-category defect resolution

Date: 2026-08-27  
Status: **PASS after correction**

## Reproduction and root cause

The exact real-API conversation reproduced the defect in chat 654. The final hard state was categories `Shirts`, colours `black`; the result set contained only `B0743MHZX2`, displayed as Match 100%.

Raw evidence for `B0743MHZX2`:

- title: `Razor for Men`
- brand: Gillette
- main_category: `All Beauty`
- source_dataset: `Clothing, Shoes and Jewelry`
- categories: `Clothing, Shoes & Jewelry → Novelty & More → Clothing → Novelty → Men → Shirts → T-Shirts`
- details include `Number of Blades: 3`, `Color: Black`, and manufacturer P&G
- features/description explicitly describe a body razor, shaving and grooming

The merged raw record therefore contains a contaminated clothing hierarchy that contradicts its independent main category, title and details. N24M2 previously treated every non-empty structured category hierarchy as intrinsically trustworthy. Exact string equality with `Shirts` returned category EXACT; the black variant field returned colour EXACT; two of two hard constraints then generated Match 100%. The card faithfully reflected the erroneous eligibility evidence.

## Correction

N24M2 now applies a deterministic product-family contradiction guard to the hierarchy in both the full evidence evaluator and fast eligibility path. It recognizes mutually exclusive shirt, footwear, watch, handbag, dress, jewelry and beauty/grooming signals from independent main-category, title and selected structured-detail fields. A hierarchy match cannot be EXACT when those signals prove another family.

For the razor after correction:

- category: `VIOLATION`
- reason: `independent title/details prove conflicting product family: BEAUTY`
- colour: `EXACT`
- overall match score: 50%, ineligible
- fast eligibility: false

Thus an invalid category cannot survive to a card or receive Match 100%.

## Candidate trace and latency

For a validated black-Shirts request, frozen ranking produced 527 candidate IDs. Trusted eligibility found zero exact catalogue products, so zero IDs remained after hard filtering and zero products were returned. The first 20 pre-filter candidate IDs were captured during the audit in the live kernel.

Measured stage timings:

- deterministic interpretation: 0 Qwen calls
- trusted full-catalogue eligibility: 0.322 s
- uncached frozen ranking: 33.181 s
- fresh post-fix black-shirt HTTP request: 1.749 s when ranking cache was present
- exact three-turn regression final request in the regenerated suite: 37.761 s on its uncached fingerprint

The reported 103.5-second browser observation is consistent with a cold/queued ranking-path outlier. The former suite was largely cache-warmed, which made its 0.609-second median unrepresentative of unseen query fingerprints. No N24M2 index rebuild, visual download, or Qwen call occurred per reproduced request; uncached frozen ranking is the measured dominant stage.

## Validation

- Independent raw-metadata adversarial audit: 15/15 passed during diagnosis.
- Persisted final suite adversaries: 13/13 passed.
- Required 16 live queries: zero observed cross-category violations.
- `black shirt`: zero exact products; no razor.
- `red shirt`: zero exact products; no padding.
- `white shirt`: two products with explicit tee/shirt title evidence.
- `razor` and `men's razor`: explicit unsupported beauty/grooming response, zero cards.
- Final acceptance v2: 35/35 scenarios, 48 turns, zero hard-constraint violations.
