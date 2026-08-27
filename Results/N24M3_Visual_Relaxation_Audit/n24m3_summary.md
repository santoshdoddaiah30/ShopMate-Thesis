# N24M3 Visual Colour Consistency + Contextual Relaxation Hardening

- Development engine: N24
- Frozen N23 / hybrid ranking weights changed: no
- Required visual cases: 10/10 passed
- Strict visual conflicts returned: 0
- Strict visual unknowns returned: 0
- White T-shirt regression: 2 metadata-eligible, 2 visually checked, 1 returned, 1 visual conflict excluded
- Deterministic adversarial audit: 50 images, 12 metadata/image disagreements, 0 strict conflicts accepted
- Contextual relaxation: R1-R8 passed (8/8)
- Cross-chat pending-action leakage: 0
- Realistic flow: passed
- Focused N24 regression: 14/14 passed
- N23 A-E: all passed
- Visual-only cold overhead across ordinary uncached test queries: median 0.306 s, maximum 2.213 s
- Cached overhead: 0.004 s for white shoes; 0.040 s for white T-shirts
- Typical images checked per colour query: median 2.5, mean 4.6
- Additional LLM calls for visual checking: 0
- Raw visual-debug labels exposed in cards: no

The visual verifier uses local Pillow/NumPy foreground analysis. Connected
near-white edge/background pixels are removed before estimating canonical
foreground colour proportions. Raw image evidence is cached by product and
image URL. `VISUAL_UNKNOWN` is conservatively excluded from strict exact
results, as are visual conflicts and unapproved mixed-colour images.
