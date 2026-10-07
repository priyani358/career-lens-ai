# CareerLens AI MVP
An O*NET-grounded career planning MVP. Core flow: create an account → complete a short profile → compare career matches → choose a career → view skill gaps and a practical roadmap.

## Setup (macOS / Windows)
Requires Python 3.10+ and Node 18+.

Backend (macOS): `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
Backend (Windows): `cd backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt`
Then: copy `.env.example` to `.env`. An LLM key is optional: deterministic O*NET matching and the built-in roadmap planner work without one. For the free-model route, create an OpenRouter key and put it in `OPENROUTER_API_KEY`; leave `OPENROUTER_MODEL=openrouter/free` and set `LLM_PROVIDER=openrouter` (or leave provider blank for auto-detection). OpenRouter free models are rate-limited and availability may vary. For Anthropic, use `ANTHROPIC_API_KEY` and set `LLM_PROVIDER=anthropic`. Never put API keys in the frontend. Check provider setup without exposing the key at `/api/health`. Then run
`python -m app.rag.store` (ingest the knowledge base; downloads a small embedding model once) and
`uvicorn app.main:app --reload --port 8000`

Frontend: `cd frontend && npm install && npm run dev` -> http://localhost:5173

## Career dataset
The bundled [O*NET 31.0 occupational catalog](data/onet/careers_31_0.json) contains occupations, descriptions, essential/transferable skill importance, job zones, core task statements, interest types, related occupations, and hot/in-demand technology examples. Skill importance is mapped from O*NET's 1–5 scale to CareerLens' 3-level skill-gap scale. CareerLens does not infer projects or certifications from O*NET data.

O*NET data is provided by the U.S. Department of Labor, Employment and Training Administration under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). O*NET is a USDOL/ETA trademark; CareerLens is not affiliated with or endorsed by USDOL/ETA. See [data/onet/README.md](data/onet/README.md) for attribution and importer details.

To update the dataset, download the CSV archive from the [official O*NET Database page](https://www.onetcenter.org/database.html) and run `python -m app.onet_import /path/to/db_31_0_csv.zip` from `backend/`. Career descriptions, core skills, and related roles come from the bundled O*NET catalog; edit `data/resources/resources.json` for learning resources. After modifying data, run `python -m app.rag.store` to re-embed it.

## MVP scope
- Five-step profile assessment and five evidence-based career matches from an explainable, catalog-wide TF-IDF recommender.
- Search all 1,016 O*NET occupations by title, skill, task, and technology, with Job Zone filtering.
- Transparent skill coverage and hybrid match-score breakdown.
- Career selection, O*NET skill-gap analysis, and a roadmap with progress tracking.
- Hybrid Chroma + BM25 retrieval; retrieved O*NET evidence and source links are visible in results.
- Optional Claude explanations. Without Claude credentials, deterministic explanations and a generated starter roadmap keep the core flow usable.

The MVP intentionally keeps the main navigation focused on Overview, Assessment, Career matches, Career plan, and Roadmap. Secondary resources, profile details, and chat remain available in the implementation but are not part of the primary user journey.

The end-to-end recommendation model builds TF-IDF vectors from the full O*NET occupation catalog and ranks each profile against occupation names, descriptions, skills, tasks, and technologies. It blends profile similarity (25%), deterministic O*NET skill coverage (50%), interest fit (15%), and preferred-role fit (10%). The response exposes every component. This is an explainable content-based model, not a supervised employment-probability predictor. RAG grounds its evidence in Chroma semantic search plus BM25 keyword search using Reciprocal Rank Fusion.

## Connected career workspace
The Career Plan view persists a selected career, then derives skill gaps, roadmap completion, an upcoming weekly action plan, matching learning resources, and alternative-career effort comparisons from the user's profile and saved roadmap. The AI coach receives this computed workspace context; the numbers remain application-derived rather than model-generated. Workspace API routes are `/api/workspace` and `/api/select-career`.
