# ShopMate

ShopMate is an MSc Data Science thesis project: a personalized conversational
recommender built on historical Amazon Reviews 2023 data.

## Recommendation engine

A hybrid recommender combining:

- Content-based filtering
- Collaborative filtering (latent factor / SVD)
- Popularity ranking
- Weighted Reciprocal Rank Fusion (RRF) to merge candidate lists

**Frozen configuration** (selected via offline validation, see
`Datasets/Processed/final_hybrid_configuration.json`):

| Parameter | Value |
|---|---|
| Content weight | 0.2 |
| Collaborative weight | 0.1 |
| Popularity weight | 0.7 |
| RRF constant (k) | 60 |
| Candidate depth per source | 500 |
| Latent dimensions | 16 |

## Conversational layer

- Local Qwen3:8b model served through Ollama
- Bounded language interpretation of user intent
- Deterministic catalogue grounding and hard-constraint enforcement (the
  language model interprets intent; it does not fabricate product data)

## Application

- **Backend:** FastAPI
- **Frontend:** React / Next.js (`Frontend/ShopMate`)

## Repository layout

- `Notebooks/` — `Thesis_clean.ipynb` (the authoritative development
  notebook), supporting Python scripts, and evaluation/validation harnesses
- `Frontend/ShopMate/` — Next.js frontend and API routes
- `Results/` — evaluation reports, metrics tables, and figures produced
  during offline and application-level testing
- `InterfaceAssets/` — UI assets used by the frontend

## Data and models — not included

This repository contains **code and documentation only**. The following are
intentionally excluded (see `.gitignore`) because of their size and are not
tracked in Git history:

- Raw Amazon Reviews 2023 dataset files (`*.jsonl`, `*.jsonl.gz`)
- Processed dataset artifacts (parquet/pickle/model files under
  `Datasets/Processed/`)
- The local DuckDB database (`thesis_recommendation.duckdb`, ~11 GB) and its
  WAL file
- `node_modules/` and frontend build output

To reproduce a full local environment, the raw Amazon Reviews 2023 category
files (All Beauty, Amazon Fashion, Clothing/Shoes/Jewelry) must be downloaded
separately and processed via the pipeline in `Thesis_clean.ipynb`.

## Project status

This is a working thesis project, not a finished release. Some development
threads (e.g. semantic consolidation work) are still in progress. See
`Notebooks/MIGRATION_LOG.md` and the reports under `Results/` for the current
state of evaluation and known issues.
