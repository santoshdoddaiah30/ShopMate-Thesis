# ShopMate N24N implementation freeze record

Date: 2026-08-27  
Authoritative notebook: `Notebooks/Thesis_clean.ipynb`

## Runtime chain

`N24L -> N24M -> N24M2 -> N24M3 -> N24N`

Cell 421 is the idempotent resolver. Its live binding audit passed after a warm
reload. N24N owns pending-action resolution and deterministic grounded response
fast paths; N24M2 remains the trusted catalogue eligibility implementation and
N24M3 remains the visual-colour boundary.

## Frozen recommender

- content weight: 0.2
- collaborative weight: 0.1
- popularity weight: 0.7
- weighted RRF k: 60
- candidates per frozen source: 500
- latent dimensions: 16

No weights, factors, training artefacts, or frozen ranking logic were changed.
The live N23 golden report remained passing.

## N24N behavior verified

- Pending mixed-colour acceptance recognizes `yes`, `ok show me mixed`, and
  `ok show me mixed colours`, consumes the offer once, retains the requested
  colour/category, and performs no LLM call.
- Rejection clears the pending offer without changing hard constraints.
- Mixed colour is offered only after a real N24M2+N24M3 eligibility probe.
- Colour modes are explicit: `STRICT`, `MIXED_ALLOWED`, and `MONOCHROME`.
- `men all black shoes` clears a stale Nike brand, retains Shoes/black, sets
  recipient `men`, disables mixed colour, and uses `MONOCHROME`.
- Questions and show-more do not mutate hard search state.

## Live HTTP acceptance evidence

All checks used the real `POST /api/messages` route and catalogue product cards.

- A, red shirt: strict count 0; verified mixed count 0; no mixed option offered.
- B, black Nike shoes -> men all-black shoes: Nike cleared; five returned cards;
  all colour components black.
- C, white shoes: five returned cards; no WHITE MOUNTAIN or White Ledge false
  colour matches.
- D, men's shoes: all five card audiences were `MEN`.
- E, all-black shoes: `MONOCHROME`, mixed disabled, all card colour components
  black.

The reproducible focused runner is `Notebooks/shopmate_n24n_validation.py`.

## Performance

Measured first-request totals in dedicated chats:

- red-shirt no-match (cached/probed): 4.148 s
- white shoes: 60.006 s
- men's shoes: 46.791 s
- all-black shoes: 55.808 s
- black Nike shoes: 35.238 s
- men all-black reformulation: 58.798 s

N24M3 metrics showed cached visual analysis itself below 0.01 s in representative
requests; the dominant cold cost is frozen retrieval/ranking (roughly 27-55 s).
The N24M2 trusted-index rebuild measured 51.331 s during a full layer reload.

After the N24N deterministic grounded composer, the repeated white-shoes API
request improved from 4.788 s to 0.508 s and made zero Qwen calls. The repeated
two-turn B flow measured 0.622 s and 0.522 s. Cold, previously unseen ranking
requests remain slow; caches do not weaken eligibility or alter frozen ranking.

## Known limitations

- First-time query fingerprints can take 35-60 s because the frozen ranking
  implementation is expensive; warm deterministic requests are sub-second.
- Trusted colour coverage is sparse, so honest zero/fewer-result responses are
  expected.
- Historical dataset prices are not live prices; stock, delivery, coupons, and
  live availability are unsupported.
- The red-shirt example has no verified mixed-colour alternative in the current
  catalogue, despite the older runtime having offered one blindly.
