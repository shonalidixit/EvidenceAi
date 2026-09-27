# EvidenceAI

**Ask questions about a CSV and inspect the evidence behind every answer.** A portfolio-ready FastAPI + DuckDB project with a responsive browser interface, deterministic SQL analyses, a dataset fingerprint, and a one-click verification flow.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-API-009688) ![DuckDB](https://img.shields.io/badge/DuckDB-analytics-f5c400)

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Click **Try the example dataset**, or upload your own CSV. Ask “What is the total revenue by region?” and click **Analyze dataset**. To run the API tests: `pytest -q`.

Docker alternative: `docker build -t evidenceai . && docker run --rm -p 8000:8000 evidenceai`.

## What it demonstrates

- CSV ingestion with file size, row count and column validation.
- Natural language routing for **counts, totals and averages**, optionally grouped by a matching category column.
- Read-only, generated DuckDB aggregation with visible SQL and result rows.
- SHA-256 fingerprint of uploaded bytes; **Verify this answer** recomputes the result and compares the data fingerprint, SQL and output rows.
- Responsive UI, example dataset, API tests, Docker packaging.

## Scope and honest limitations

This is a working **descriptive analytics MVP**, not an autonomous data scientist. Questions outside counts, totals and averages are mapped to the closest supported analysis and may not capture intent. Inspect the selected columns and SQL before trusting an answer. It does not infer causality, run statistical tests, generate arbitrary Python or query private databases. CSV files live temporarily in the process memory (maximum 20 active datasets), with no persistent storage or user authentication. Do not upload confidential data to a public deployment. Run behind appropriate authentication before using real customer datasets.

The verifier checks reproducibility within this running process; it does not independently certify truth or prove the source data is accurate. No LLM API key is required, and no model-generated code executes.

## API

- `POST /api/upload` — multipart `file` (CSV); returns dataset ID, fingerprint and column profile.
- `POST /api/analyze` — JSON `{ "dataset_id": "...", "question": "total revenue by region" }`.
- `POST /api/verify` — same fields plus `expected_sha256`, `expected_sql`, and `expected_rows` from the analysis result.
- `GET /docs` — interactive OpenAPI docs.

## GitHub upload

Create a new repository named `evidenceai` on GitHub. Upload **the contents of this folder** (including `app`, `tests`, `sample_data`, `README.md`, `requirements.txt`, and `Dockerfile`) using **Add file → Upload files**. Or from inside this folder:

```bash
git init
git add .
git commit -m "Build EvidenceAI analytics MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/evidenceai.git
git push -u origin main
```

## Next iterations

Date-aware period comparisons, explicit column selection, statistical uncertainty, chart export, persisted analysis runs, sandboxed Python tools, optional LLM planning with strict validation, and evaluation against a labeled question set.
