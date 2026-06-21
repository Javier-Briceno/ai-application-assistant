# Migration Plan: n8n → Python

## Status legend
- ✅ Done
- 🚧 In progress / this session
- ⬜ Pending

---

## Slice 1 — Profile Setup ✅ (this session)

**Scope:** Profile create/edit form, LLM extraction pipeline, profile selector.

**What was built:**
- `backend/config.py` — Settings via pydantic-settings
- `backend/db.py` — asyncpg pool
- `backend/llm.py` — Unified wrapper (Anthropic + OpenAI), logs to `llm_logs`
- `backend/migrations/001_llm_logs.sql` — llm_logs table (run ✅)
- `backend/deterministic/language.py` — detect_language()
- `backend/deterministic/cv_utils.py` — normalize_cv(), hash_cv()
- `backend/prompts/v1/*.txt` — 4 system prompts ported verbatim
- `backend/models/profile.py` — Pydantic models for all extraction outputs
- `backend/pipeline/profile_extraction.py` — Full CREATE/UPDATE pipeline
- `backend/ui/components/profile_modal.py` — NiceGUI form dialog (German)
- `backend/ui/components/avatar.py` — Server-side image resize (Pillow)
- `backend/ui/pages/main_page.py` — Two-panel main page (German)
- `backend/main.py` — FastAPI + NiceGUI mount
- App boots and loads profiles from DB ✅

**To test end-to-end:** Add API keys to `.env`, run `uv run python -m backend.main`,
open http://server:8000, create a profile.

---

## Slice 2 — Company Research ✅

**Scope:** Company name extraction + SerpAPI search + result parsing.

**n8n source:** `Utility: Company Research` sub-workflow.

**What to build:**
- `backend/prompts/v1/company_extractor.txt`
- `backend/models/company.py` — CompanyExtractorOutput, SearchResult
- `backend/pipeline/company_research.py` — extract_company_name() + serpapi_search() + parse_results()
- `backend/deterministic/company_research.py` — Build Search Query + Extract Results Code Nodes

**Model:** claude-haiku-4-5-20251001 for company extraction

**Notes:**
- SerpAPI call goes through httpx (not llm.py — it's not an LLM call)
- Result text capped at ~800 words (mirrors n8n Extract Results Code Node)
- If company name empty → return empty profile (pipeline still continues)

---

## Slice 3 — CV Translation Cache ✅

**Scope:** Hash-based CV translation with DB caching.

**n8n source:** `Utility: CV Translation Cache` sub-workflow.

**What to build:**
- `backend/prompts/v1/cv_translator.txt`
- `backend/pipeline/translation_cache.py` — translate_cv_if_needed()

**Model:** claude-sonnet-4-6 for translation

**Notes:**
- Skip if cv_language == job_post_language (no translation needed)
- Cache keys: `translated_cv_text_{lang}` + `cv_hash` in candidate_context
- Cache hit: translated text exists AND cv_hash matches source_hash

---

## Slice 4 — Analysis & Scoring ✅

**Scope:** 5-dimension scoring, threshold calculation, gap analysis for fail.

**n8n source:** `Utility: Analysis Scoring` sub-workflow.

**What to build:**
- `backend/prompts/v1/analyzer_system.txt` — the 2500-token scoring rubric
- `backend/models/analysis.py` — AnalyzerOutput, ScoringResult
- `backend/deterministic/scoring.py` — calculate_dimensions(), calculate_threshold()
- `backend/pipeline/analysis_scoring.py`
- `backend/prompts/v1/gap_analysis.txt` — for fail case
- `backend/pipeline/gap_analysis.py`

**Model:** **gpt-4.1** for Analyzer (hard constraint), claude-sonnet-4-6 for Gap Analysis

**Notes:**
- Dimension max values: Technical=40, Requirements=25, Role Fit=20, Location=10, Strategic=5
- Threshold logic is pure Python — NOT in the prompt
- Pass: score ≥ 60 AND no dimension at 0
- Caution: score ≥ 45 OR (score ≥ 40 AND no critical dim at 0)
- Fail: everything else

---

## Slice 5 — CV Tailoring Chain ✅

**Scope:** Classifier → Enforcer → Generator → Validator → Retry → CV Deterministic Editor → CV Rewriter.

**n8n source:** `Utility: CV Tailoring Planner` sub-workflow.

**What to build:**
- `backend/prompts/v1/cv_classifier.txt`
- `backend/prompts/v1/cv_generator.txt`
- `backend/prompts/v1/cv_rewriter.txt`
- `backend/models/tailoring.py` — ClassifierOutput, GeneratorOutput, CvAnpassung
- `backend/deterministic/word_budget.py` — compute_word_budget(), enforcer(), validator()
- `backend/deterministic/cv_editor.py` — apply_remove_instructions()
- `backend/pipeline/cv_tailoring.py` — full chain with retry logic

**Models:** **gpt-4.1** for Classifier (hard constraint), claude-haiku-4-5-20251001 for Generator/Rewriter

---

## Slice 6 — Anschreiben ✅

**Scope:** Cover letter generation.

**What to build:**
- `backend/prompts/v1/anschreiben.txt`
- `backend/prompts/v1/anschreiben_guide.txt`
- `backend/pipeline/anschreiben.py`

**Model:** claude-sonnet-4-6

---

## Slice 7 — Full Pipeline + Result UI ✅

**Scope:** Wire all pipeline slices together. Build NiceGUI result panel.

**What to build:**
- `backend/pipeline/main_pipeline.py` — orchestrates slices 2-6 in order
- `backend/deterministic/diff.py` — LCS diff engine (port of n8n Diff Engine Code Node)
- `backend/deterministic/response_formatter.py` — builds the markdown response
- `backend/ui/components/score_panel.py` — score number, bar, dimension grid
- `backend/ui/components/result_panel.py` — sections: cv diff, cover letter, gap analysis
- `backend/ui/docx_export.py` — python-docx Lebenslauf + Anschreiben generation
- Wire up the "Analysieren" button in main_page.py
- Store result in job_applications table

**Caddy cutover:** Once this slice is verified, update Caddy to proxy cv.javierbriceno.com → :8000.

---

## Slice 8 — Application History + Deploy ✅

**What was built:**
- `backend/ui/pages/history_page.py` — expandable history list with diff/anschreiben/gaps tabs
- `backend/ui/components/nav.py` — shared nav bar (Analyse | Verlauf)
- `benchmark.py` — CLI tool: `uv run python benchmark.py --node <name> [--model X] [--n N]`
- `backend/migrations/002_llm_node_benchmarks.sql` — benchmark results table (run ✅)
- `Dockerfile` — single-stage python:3.12-slim, uv sync --system
- `docker-compose.yml` — host network mode (reaches local Postgres)
- `.dockerignore`
- `Caddyfile.example` — cutover steps: `docker compose up -d` → test `/api/health` → update Caddyfile → `caddy reload`

---

## To start the app

```bash
cd /opt/cv-assistant

# Dev (no Docker)
uv run python -m backend.main
# → http://<server-ip>:8000

# Production (Docker)
docker compose up -d --build
# Verify: curl http://localhost:8000/api/health

# Benchmark a node
uv run python benchmark.py --node analyzer --n 3
```

## Caddy cutover (cv.javierbriceno.com → port 8000)

See `Caddyfile.example` for exact steps. Short version:
1. `docker compose up -d`
2. Verify `/api/health`
3. Replace static `file_server` block with `reverse_proxy localhost:8000`
4. `caddy reload`
