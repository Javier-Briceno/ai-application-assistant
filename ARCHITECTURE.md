# CV Assistant — Architecture

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + TypeScript — SPA compiled to `frontend/dist/` |
| Backend API | FastAPI (async), served by uvicorn on port 8000 |
| LLM | Anthropic SDK (Haiku / Sonnet) + OpenAI SDK (GPT-4.1) |
| DB | PostgreSQL via asyncpg — schema `job_application_assistant` in DB `projects` |
| Documents | python-docx — server-side DOCX generation |
| Runtime | Python 3.12 + uv (backend), Node 20+ (frontend build only) |
| Deploy | Docker Compose + Caddy reverse proxy on Hetzner |

## Process model

One uvicorn process on port 8000 serves both the API and the compiled React static files.

```
Caddy (:443) → uvicorn (:8000)
                  ├── FastAPI API routes  /api/*
                  └── Static files        /  (React SPA, served from frontend/dist/)
```

In development, `vite dev` runs separately on `:5173`; FastAPI has CORS open to that origin.

## Module layout

```
/opt/pilot/
├── backend/
│   ├── main.py                    ← FastAPI app + uvicorn entry point
│   ├── config.py                  ← pydantic-settings (reads .env)
│   ├── db.py                      ← asyncpg pool + get_conn() context manager
│   ├── llm.py                     ← Unified LLM wrapper (Anthropic + OpenAI), DB logging
│   │
│   ├── api/
│   │   ├── analyze.py             ← POST /api/analyze — SSE streaming pipeline
│   │   ├── applications.py        ← GET/DELETE /api/applications + DOCX download
│   │   ├── profiles.py            ← CRUD /api/profiles + avatar upload
│   │   └── chat.py                ← POST /api/chat — contextual Q&A on saved applications
│   │
│   ├── models/
│   │   ├── analysis.py            ← ScoringResult, AnalyzerOutput, ScoreDims
│   │   ├── company.py             ← CompanyResearchResult
│   │   ├── profile.py             ← CandidateProfile, all extraction outputs
│   │   ├── requirements.py        ← RequirementsAnalysis, BlockerItem
│   │   └── tailoring.py           ← ClassifierOutput, GeneratorOutput, TailoringResult
│   │
│   ├── deterministic/             ← Pure Python — no LLM, no DB
│   │   ├── cv_editor.py           ← validate_generator_output(), apply_removes_by_content(), compute_diff()
│   │   ├── cv_utils.py            ← normalize_cv(), hash_cv(), compute_content_hash()
│   │   ├── language.py            ← detect_language(text) → 'de' | 'en'
│   │   ├── company_research.py    ← build_search_query(), extract_results_text()
│   │   ├── scoring.py             ← calculate_dimensions(), calculate_threshold(), apply_requirements_override()
│   │   └── word_budget.py         ← compute_word_budget(), enforcer()
│   │
│   ├── pipeline/                  ← One module per pipeline stage
│   │   ├── main_pipeline.py       ← Orchestrator: runs all stages, stores result
│   │   ├── profile_extraction.py  ← Profile setup: CV parsing, skill extraction, DB upsert
│   │   ├── company_research.py    ← DuckDuckGo search + Haiku extraction
│   │   ├── analysis_scoring.py    ← GPT-4.1 Analyzer + requirements check + threshold
│   │   ├── requirements_check.py  ← Haiku requirements/dealbreaker analysis
│   │   ├── cv_tailoring.py        ← Classifier → Generator → Rewriter → compute_diff()
│   │   ├── anschreiben.py         ← Sonnet cover letter generation
│   │   ├── truthfulness.py        ← Haiku truthfulness validation of Anschreiben
│   │   └── translation_cache.py   ← CV translation (Sonnet), cached by content hash
│   │
│   ├── prompts/
│   │   ├── loader.py              ← load_prompt(name, version='v1') → str
│   │   └── v1/                    ← All system prompts as .txt files
│   │       ├── analyzer_system.txt
│   │       ├── anschreiben.txt
│   │       ├── binary_classifier.txt
│   │       ├── candidate_profile.txt
│   │       ├── company_extractor.txt
│   │       ├── core_skills_extractor.txt
│   │       ├── cv_classifier.txt
│   │       ├── cv_generator.txt
│   │       ├── cv_rewriter.txt
│   │       ├── cv_translator.txt
│   │       ├── gap_analysis.txt
│   │       ├── market_research_extractor.txt
│   │       ├── requirements_extractor.txt
│   │       └── truthfulness_validator.txt
│   │
│   ├── tests/
│   │   ├── test_cv_diff.py        ← 13 tests for compute_diff()
│   │   ├── test_requirements.py   ← 20 tests for requirements/dealbreaker logic
│   │   ├── test_truthfulness.py   ← Truthfulness validation tests
│   │   └── test_fixes.py          ← Regression tests for past bugs
│   │
│   └── ui/                        ← Legacy NiceGUI code (no longer active in production)
│       ├── docx_export.py         ← generate_cv_docx(), generate_anschreiben_docx() — still used by api/applications.py
│       └── components/avatar.py   ← process_avatar() — still used by api/profiles.py
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AnalysePage.tsx    ← Main analysis form + SSE result display
│   │   │   ├── VerlaufPage.tsx    ← History view: timeline + detail panel
│   │   │   └── EinstellungenPage.tsx ← App info / settings
│   │   ├── components/
│   │   │   ├── Bewertung.tsx      ← Score panel with per-dimension bars
│   │   │   ├── CvDiff.tsx         ← Unified diff renderer (add/del/ctx/hunk lines)
│   │   │   ├── Anschreiben.tsx    ← Cover letter display + DOCX download
│   │   │   ├── ResultPanel.tsx    ← Wraps Bewertung + CvDiff + Anschreiben
│   │   │   ├── ProfileModal.tsx   ← Profile create/edit dialog
│   │   │   ├── ProfileSlider.tsx  ← Profile selector
│   │   │   ├── ChatPopup.tsx      ← Contextual chat overlay
│   │   │   └── Sidebar.tsx        ← Navigation
│   │   ├── types/index.ts         ← All TypeScript interfaces (ScoringResult, Application, etc.)
│   │   ├── lib/api.ts             ← API client functions
│   │   └── context/AppContext.tsx ← Global app state (profile, toasts)
│   └── dist/                      ← Compiled output (gitignored, served by FastAPI)
│
├── pyproject.toml
└── .env                           ← API keys + DB credentials (gitignored)
```

## Main analysis pipeline (SSE)

`POST /api/analyze` streams progress as Server-Sent Events (`type: "step"`) and emits one final `type: "result"` event.

```
1. Fetch candidate profile from DB
2. Parallel:
   ├── Company research: DuckDuckGo → Haiku extractor → CompanyResearchResult
   └── CV translation: if CV language ≠ 'de', Sonnet translates (cached by content hash)
3. Analysis & scoring:
   ├── GPT-4.1 Analyzer → AnalyzerOutput (5 dimension scores + reasoning)
   ├── calculate_dimensions() + calculate_threshold()  ← deterministic
   ├── Requirements check: Haiku → RequirementsAnalysis (dealbreakers / hard missing)
   └── apply_requirements_override()  ← deterministic: caution/fail adjustment
4. Branch on threshold:
   ├── fail → Gap Analysis (Sonnet) only; no documents generated
   └── pass/caution → Parallel:
       ├── CV tailoring: Classifier (Haiku) → Generator (Haiku) → Rewriter (Haiku) → compute_diff()
       ├── Anschreiben: Sonnet cover letter
       └── Gap Analysis: Sonnet (for the caution-case summary)
5. Truthfulness validation: Haiku checks Anschreiben claims against CV text
6. Store to DB: job_applications row; scoring_details JSONB (dimensions + requirements_analysis + truthfulness_warning)
7. Emit type=result SSE with full payload
```

## Profile setup pipeline

Triggered by `POST /api/profiles` (create) or `PUT /api/profiles/{id}` (update CV).

```
1. normalize_cv() → hash_cv()  ← skip re-extraction if hash unchanged
2. Parallel:
   ├── detect_language() → CV translation if non-German
   ├── Core skills extraction (Haiku)
   ├── Binary technology classifier (Haiku)
   └── Market research extractor (Haiku)
3. Candidate profile synthesis (Sonnet) → CandidateProfile with commute_options, career_target, etc.
4. Upsert profile row in DB
```

## LLM call pattern

Every LLM call goes through `llm.py`. No direct SDK calls elsewhere.

```python
# Structured output — validates with Pydantic, retries on schema mismatch
result = await llm.call_structured(
    conn,
    model="claude-haiku-4-5-20251001",
    system=load_prompt("requirements_extractor"),
    user="<job_posting>...</job_posting><candidate_profile>...</candidate_profile>",
    response_model=RequirementsAnalysis,
    node_name="requirements_check",
    temperature=0.0,
    max_tokens=1000,
)

# Raw text — for non-structured outputs
text = await llm.call_raw(conn, model=..., system=..., user=..., node_name=...)
```

All calls log to `job_application_assistant.llm_logs`: model, node_name, profile_id, input/output tokens, latency, estimated cost.

## Model assignments (hard constraint)

| Pipeline node | Model |
|---|---|
| Main Analyzer (5-dimension scoring) | gpt-4.1 |
| Requirements / dealbreaker check | claude-haiku-4-5-20251001 |
| Truthfulness validator | claude-haiku-4-5-20251001 |
| CV Classifier | claude-haiku-4-5-20251001 |
| CV Generator | claude-haiku-4-5-20251001 |
| CV Rewriter | claude-haiku-4-5-20251001 |
| Core Skills Extractor | claude-haiku-4-5-20251001 |
| Binary Technology Classifier | claude-haiku-4-5-20251001 |
| Market Research Extractor | claude-haiku-4-5-20251001 |
| Company Extractor | claude-haiku-4-5-20251001 |
| Candidate Profile Synthesizer | claude-sonnet-4-6 |
| CV Translator | claude-sonnet-4-6 |
| Anschreiben | claude-sonnet-4-6 |
| Gap Analysis | claude-sonnet-4-6 |

## Requirements and dealbreaker analysis

After `calculate_threshold()`, `requirements_check.py` calls Haiku with the job posting, candidate profile summary, and CV text. The prompt classifies only explicit mandatory requirements:

- **`triggered_dealbreakers`** — legal/impossible mismatches only: work permit, legally required licence, language level explicitly below stated minimum. These do NOT include location or work-format issues.
- **`missing_hard_requirements`** — all other unmet mandatory requirements: location/on-site format, relocation, years of experience, degree, non-legal certifications. When uncertain, the prompt always defaults to this category.

`apply_requirements_override()` then adjusts the threshold deterministically:
- Dealbreaker found + base was `pass`/`caution` → `caution` (never forced to `fail`; documents still generated)
- Dealbreaker found + base was `fail` → stays `fail`
- Missing hard requirement + base was `pass` → `caution`

## CV diff generation

`compute_diff(original, modified)` in `deterministic/cv_editor.py` uses `difflib.unified_diff` (Python stdlib). Output format:

```
@@ -a,b +c,d @@     hunk header (position marker)
 context line        single-space prefix
-removed line        minus prefix
+added line          plus prefix
```

File-name headers (`---`/`+++`) are stripped. Context lines = 2 (configurable via `_DIFF_CONTEXT`). `CvDiff.tsx` renders all line types; backward-compatible with the old set-based format.

## Document downloads

`GET /api/applications/{id}/download/cv` and `.../download/anschreiben` call `generate_cv_docx()` / `generate_anschreiben_docx()` from `backend/ui/docx_export.py` and stream the result as `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

## Prompt versioning

Prompts live in `backend/prompts/v1/*.txt`. To change a prompt: create a `v2/` copy and update the `load_prompt()` call at the pipeline call site. The version directory is the prompt version label; old versions stay in git history.

## Hard constraints (non-negotiable)

1. No candidate-specific or profile-specific content in any prompt file
2. All arithmetic, counting, scoring, string matching → Python (`deterministic/`)
3. Every LLM call goes through `llm.py` (no direct SDK calls)
4. DB schema unchanged — no destructive migrations
5. Model assignments above are fixed — do not swap models between nodes
