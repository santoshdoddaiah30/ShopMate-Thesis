# ShopMate

**Hybrid Recommendation System with Conversational AI for Personalized E-Commerce**

Santosh Doddaiah<br>
MSc Data Science<br>
University of Europe for Applied Sciences<br>
Matriculation number: 31288471

## Project overview

ShopMate is a thesis prototype for personalized, conversational product
recommendation. It combines offline recommendation models with deterministic
catalogue grounding and a conversational interface. The system is evaluated on
historical Amazon Reviews 2023 data from the All Beauty, Amazon Fashion, and
Clothing, Shoes and Jewelry categories.

## Architecture

ShopMate separates three responsibilities:

```text
Recommendation ranking
    -> canonical product semantics and deterministic eligibility
    -> grounded conversational response generation
```

The frozen N23 recommender generates and ranks candidates. The additive N24
layer represents catalogue facts through `CanonicalProductSemantics`, applies
deterministic hard-constraint evaluation, and maintains conversational state
through `ResultSet` and `PendingOffer`. Product facts and eligibility decisions
are not delegated to the language model.

The application uses Qwen3:8b through Ollama for bounded language
interpretation, a FastAPI backend, and a Next.js/React frontend.

## Dataset and final catalogue

The experiments use the Amazon Reviews 2023 dataset. Raw downloads, processed
tables, model artefacts, and the local DuckDB database are intentionally not
stored in GitHub because of their size. The final processed catalogue contains
65,546 products. Data acquisition and processing are documented in the
authoritative notebook.

## Final hybrid configuration

| Parameter | Frozen value |
| --- | ---: |
| Content weight | 0.2 |
| Collaborative weight | 0.1 |
| Popularity weight | 0.7 |
| Weighted RRF k | 60 |
| Candidates per source | 500 |
| Latent dimensions | 16 |

These values are frozen and were not changed during the later conversational
system work.

## Project structure

```text
ShopMate-Thesis/
|-- Notebooks/
|   |-- Thesis_clean.ipynb          # authoritative experiment and implementation
|   `-- shopmate_*.py               # runtime, semantics, and validation modules
|-- Frontend/ShopMate/               # Next.js/React application
|-- Results/
|   |-- Tables/                      # final metric tables
|   |-- Figures/                     # thesis-ready evaluation figures
|   `-- FINAL_SYSTEM_VALIDATION_SUMMARY.md
|-- InterfaceAssets/Screenshots/      # final application walkthrough images
|-- Datasets/Processed/              # only small frozen configuration files tracked
|-- requirements.txt                 # direct Python dependencies
|-- README.md
`-- .gitignore
```

## Experimental notebook

[`Notebooks/Thesis_clean.ipynb`](Notebooks/Thesis_clean.ipynb) is the
authoritative experimental notebook. It contains the data-processing pipeline,
offline baseline and hybrid evaluations, the untouched final test evaluation,
the frozen N23 recommender, stored experimental outputs, and the N24
conversational implementation and evidence. Historical or backup notebooks are
not authoritative.

The notebook is preserved with its existing outputs. It should not be rerun
merely to inspect the reported results.

## Results

For the reported `positive_test` scope, the final locked hybrid outperforms the
TF-IDF content model and tuned latent-factor collaborative-filtering model on
all five reported ranking metrics.

The comparison with the popularity baseline is mixed and should not be
interpreted as universal hybrid superiority:

- Popularity is higher at HR@5, HR@10, MRR@10, and NDCG@10.
- The hybrid is higher at HR@20.

The source values are available in
[`Results/Tables/final_test_model_metrics.csv`](Results/Tables/final_test_model_metrics.csv),
with additional comparisons and thesis-ready figures under `Results/Tables/`
and `Results/Figures/`.

## Conversational system

The final application includes:

- canonical catalogue representation through `CanonicalProductSemantics`;
- deterministic, evidence-based constraint evaluation;
- `ResultSet` memory for grounded comparison and follow-up turns;
- persisted `PendingOffer` handling for explicit relaxations;
- Qwen3:8b through Ollama for bounded language interpretation;
- a FastAPI application boundary; and
- a Next.js/React user interface.

The N24 application layers are additive and do not retrain, retune, or mutate
the frozen N23 recommender.

Representative screenshots of the final interface and interaction flows are
available in [`InterfaceAssets/Screenshots/`](InterfaceAssets/Screenshots/).

## Validation

The final validation summary records:

- Batch 1: PASS;
- Batch 2: PASS;
- Batch 3: PASS; and
- frozen N23 golden regression: 5/5 PASS.

See
[`Results/FINAL_SYSTEM_VALIDATION_SUMMARY.md`](Results/FINAL_SYSTEM_VALIDATION_SUMMARY.md)
for scope, evidence, and qualifications.

## Known limitations

- Prices are historical Amazon Reviews 2023 values, not live prices.
- The system does not verify live inventory, delivery dates, coupons, or
  current availability.
- Semantic evaluation adds measurable latency, particularly on cold or
  index-heavy paths.
- A genuine `RELAX_COLOUR` offer was not triggered through the live final
  validation path; its isolation logic was covered independently.
- Evaluation is limited to the selected Amazon Reviews 2023 categories and
  experimental protocol.
- Missing trusted attributes can cause strict queries to return no result
  rather than infer unsupported catalogue facts.

## Inspecting the notebook

For review, open `Notebooks/Thesis_clean.ipynb` in a Jupyter-compatible viewer.
The committed notebook already contains the experimental outputs used for the
thesis; data processing and model training do not need to be rerun to inspect
them.

## Running the application

The frontend dependency versions and scripts are defined in
`Frontend/ShopMate/package.json` and its lockfile:

```powershell
cd Frontend/ShopMate
npm ci
npm run dev
```

Direct Python dependencies are documented in `requirements.txt`. Versions are
pinned where the saved notebook records the executed environment; dependencies
without reliable saved version evidence are intentionally left unpinned rather
than assigned invented versions. The Python backend is restored from the
notebook and supporting `Notebooks/shopmate_*.py` modules, and it additionally
requires the large local data/model artefacts excluded from Git. Consequently,
a complete application run requires the documented local artefacts; the
frontend command alone is not a full-system startup.

Available frontend checks are:

```powershell
npm run typecheck
npm run lint
```

## Thesis

This repository accompanies the MSc thesis *Hybrid Recommendation System with
Conversational AI for Personalized E-Commerce*. It provides the authoritative
experimental notebook, implementation source, final evaluation outputs, and
validation evidence. The thesis PDF is not distributed through this repository.
