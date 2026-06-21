# CV Assistant — Full Technical Context Report
**Generated:** 2026-06-21  
**Purpose:** Input context for Claude Opus 4.8 audit and improvement plan  
**Scope:** Entire repository `/opt/cv-assistant`

---

## 1. High-Level Overview

CV Assistant is a single-user German job application tool. Given a job posting pasted by the user, it:

1. Researches the company (SerpAPI → Google)
2. Scores the candidate's fit (5 dimensions, GPT-4.1)
3. Tailors the candidate's CV to the posting (multi-step LLM pipeline)
4. Writes a German cover letter (Anschreiben)
5. Stores the result in Postgres and shows a diff of CV changes

The system was migrated from a no-code n8n workflow to Python. Most pipeline logic is explicitly documented as "ports the n8n X node." The frontend was also recently rebuilt from scratch in React 19 + Vite, replacing a NiceGUI/Python server-rendered UI.

**Key design constraints:**
- German-language app (all UI, LLM prompts, responses in German by default)
- Single deployment (Docker + Caddy) on Hetzner VPS
- PostgreSQL on the host machine (not containerised); container connects via `network_mode: host`
- No auth layer — single user, no login
- `StrictMode` was intentionally removed from `frontend/src/main.tsx` to prevent double-mounting

---

## 2. Repository Structure

```
/opt/cv-assistant/
├── backend/
│   ├── main.py                    FastAPI app, uvicorn entry, SPA fallback
│   ├── config.py                  pydantic-settings (reads .env)
│   ├── db.py                      asyncpg pool (lazy-init singleton, min=2, max=10)
│   ├── llm.py                     Unified LLM wrapper: call_raw, call_structured
│   │
│   ├── api/
│   │   ├── analyze.py             POST /api/analyze → SSE stream
│   │   ├── applications.py        GET /api/applications, GET /…/cv.docx, GET /…/anschreiben.docx
│   │   ├── profiles.py            GET/POST/PUT /api/profiles, GET /api/profiles/{id}
│   │   └── chat.py                POST /api/chat → SSE stream
│   │
│   ├── pipeline/
│   │   ├── main_pipeline.py       Orchestrator: 8-step pipeline
│   │   ├── analysis_scoring.py    GPT-4.1 Analyzer → dimensions → threshold → gap analysis
│   │   ├── anschreiben.py         Sonnet cover letter generation
│   │   ├── company_research.py    Haiku extractor + SerpAPI + text capping
│   │   ├── cv_tailoring.py        Classifier → Enforcer → Generator → Validator → Rewriter
│   │   ├── profile_extraction.py  Profile CREATE/UPDATE: market research, candidate profile
│   │   └── translation_cache.py   CV translation with SHA-256 cache invalidation
│   │
│   ├── deterministic/
│   │   ├── cv_editor.py           LCS diff, apply_removes_by_content, validate_generator_output
│   │   ├── cv_utils.py            normalize_cv (promote headers to ##), hash_cv (SHA-256)
│   │   ├── language.py            detect_language: DE/EN stopword scoring
│   │   ├── scoring.py             calculate_dimensions (clamp), calculate_threshold
│   │   ├── word_budget.py         compute_word_budget, enforcer (DISTRAKTOR→ENTFERNEN)
│   │   ├── company_research.py    build_search_query, extract_results_text (800-word cap)
│   │   └── response_formatter.py  format_score_header, format_pass_response (legacy)
│   │
│   ├── models/
│   │   ├── analysis.py            Pydantic: AnalyzerOutput, ScoringResult, DimensionScores
│   │   ├── company.py             Pydantic: CompanyExtractorOutput, CompanyResearchResult
│   │   ├── tailoring.py           Pydantic: ClassifierOutput, GeneratorOutput, TailoringResult
│   │   └── profile.py             Pydantic: ProfileRow, ProfileSummary, LLM output models
│   │
│   ├── prompts/v1/                12 .txt system prompt files (versioned in git)
│   ├── ui/
│   │   ├── docx_export.py         generate_cv_docx, generate_anschreiben_docx → bytes
│   │   └── components/avatar.py   Pillow image resize + base64 data URL
│   │
│   └── migrations/
│       ├── 001_llm_logs.sql       llm_logs table
│       ├── 002_llm_node_benchmarks.sql
│       └── 003_tailored_cv.sql    ALTER TABLE job_applications ADD COLUMN tailored_cv TEXT
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx               React 19 root (no StrictMode)
│   │   ├── App.tsx                BrowserRouter + layout (Sidebar + outlet)
│   │   ├── context/AppContext.tsx Global state (profile, toasts, analyzeResult, analyzing, stepMsg)
│   │   ├── lib/api.ts             Typed API client (fetch wrappers)
│   │   ├── lib/profileColor.ts    Deterministic hue from profile ID
│   │   ├── types/index.ts         TypeScript types: Application, ScoringResult, PipelineResult
│   │   ├── pages/
│   │   │   ├── AnalysePage.tsx    Left panel (textarea + button) + right panel (StepList/results)
│   │   │   └── VerlaufPage.tsx    Timeline list + detail panel (Bewertung + CvDiff + Anschreiben)
│   │   └── components/
│   │       ├── Sidebar.tsx        Fixed 44px nav, expands to 160px on hover
│   │       ├── Bewertung.tsx      5-dimension score bars with expandable reasoning
│   │       ├── CvDiff.tsx         LCS diff viewer (monospace, +/- lines only, show more)
│   │       ├── Anschreiben.tsx    Editable textarea with copy/download
│   │       ├── ChatPopup.tsx      Fixed-position SSE chat widget
│   │       ├── StepList.tsx       Animated step progress (pulse dot, check, pending circle)
│   │       ├── ProfileModal.tsx   Create/edit profile form (react-hook-form + zod)
│   │       └── ProfileSlider.tsx  Slide-in profile switcher panel
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
│
├── Dockerfile                     2-stage: node build → python runtime (uv)
├── docker-compose.yml             host network, env_file, nicegui_storage volume
├── pyproject.toml                 Python deps: fastapi, anthropic, openai, asyncpg, python-docx
├── .env                           API keys + DB credentials (gitignored)
└── ARCHITECTURE.md                Outdated (still references NiceGUI)
```

---

## 3. Backend — All Endpoints

### `POST /api/analyze`
**File:** `backend/api/analyze.py`

Accepts `{ profile_id: int, job_posting: str }`. Returns `text/event-stream` with two event types:

```
data: {"type": "step", "message": "Profil wird geladen..."}
data: {"type": "result", "data": { ... }}   # or {"type": "error", "message": "..."}
```

**Implementation:** Uses `asyncio.Queue` to interleave step events while the pipeline runs in a separate `asyncio.create_task`. The step events are drained via a 0.5s timeout loop. On pipeline completion, the full `PipelineResult` is serialised and emitted as the `result` event.

**Step messages (exact strings, matched in frontend STEP_LABELS):**
1. `"Profil wird geladen..."`
2. `"Unternehmen wird recherchiert & Lebenslauf wird vorbereitet..."`
3. `"Stelle wird analysiert & bewertet..."`
4. `"Lebenslauf wird angepasst..."`
5. `"Anschreiben wird verfasst..."`
6. `"Ergebnisse werden gespeichert..."`

**Risk:** Dead first version of `generate()` is still in the file (unused). Two implementations of the same endpoint exist in the file — the first one (without steps) is never called. Only `generate_with_steps` is used via `StreamingResponse`.

---

### `GET /api/applications`
**File:** `backend/api/applications.py`

Optional `?profile_id=N` query parameter. Returns list of all stored applications, including `cv_diff`, `anschreiben`, `gaps`, `scoring_details` (JSONB parsed to dict). `date_applied` is serialised via `.isoformat()`.

**Note:** `scoring_details` is stored as JSONB in Postgres and returned as a Python dict directly by asyncpg; the `isinstance(r["scoring_details"], str)` fallback `json.loads()` is defensive but handles old rows.

---

### `GET /api/applications/{id}/cv.docx`
**File:** `backend/api/applications.py`

Fetches `tailored_cv` from `job_applications` JOIN `profiles`. Returns 404 if `tailored_cv` is empty. Calls `generate_cv_docx(cv_text, candidate_name=...)` which returns `bytes`, wraps in `BytesIO`, streams as `.docx`.

**Known limitation (Task 13):** Applications created before migration 003 (`tailored_cv` column added) have `tailored_cv = NULL`. These return 404 with no user-facing explanation.

---

### `GET /api/applications/{id}/anschreiben.docx`
**File:** `backend/api/applications.py`

Same pattern. Passes `candidate_address=row.get("city")` from the profile JOIN. The Anschreiben DOCX includes a sender block (name + city) and recipient block (company name).

---

### `GET /api/profiles`
**File:** `backend/api/profiles.py`

Returns `[{ id, display_name, first_name, last_name, avatar_data_url, home_location }]`. Reads from `profiles` table only (no `candidate_context` join).

---

### `GET /api/profiles/{id}`
**File:** `backend/api/profiles.py`

Returns full profile including `cv_text`, `market_research`, `career_target` (fetched via `LEFT JOIN candidate_context`). Uses `MAX(CASE WHEN ... END)` aggregation pattern.

---

### `POST /api/profiles` and `PUT /api/profiles/{id}`
**File:** `backend/api/profiles.py`

Both use `multipart/form-data` (FastAPI `Form` params + optional `UploadFile avatar`). On avatar upload: Pillow resize → base64 data URL via `process_avatar()`.

Both call `run_profile_setup(conn, ...)` which runs the full profile extraction LLM pipeline (5 Haiku/Sonnet calls). This is NOT just a DB write — profile save triggers market research extraction, candidate profile construction, etc.

---

### `POST /api/chat`
**File:** `backend/api/chat.py`

Accepts `{ job_application_id: int|null, company_name: str, messages: [{role, content}] }`. Streams Claude Haiku response as SSE `data: {"delta": "..."}`. 

**Context limitation:** Does NOT inject the stored job posting, CV diff, or scoring data into the conversation. The system prompt is generic: "Du bist ein hilfreicher Bewerbungsassistent..." The model only knows the company name from the welcome message, not from any stored data. The `job_application_id` is received but not used to fetch context from DB.

---

### `GET /api/health`
Returns `{"status": "ok"}`. No DB check.

---

### Design Interview routes (legacy)
`GET /design-interview` through `/design-interview-11` and `POST /api/design-answers` through `/api/design-answers-11`. These serve static HTML files for an internal UX research tool. Eleven identical route handlers. JSON answers saved to local files in the repo root. These routes should be cleaned up.

---

## 4. Frontend Analysis

### State Architecture

**Global state (`AppContext.tsx`):**
- `activeProfileId: number | null` — persists across page navigation
- `analyzeResult: PipelineResult | null` — full pipeline result; persists across navigation
- `analyzePosting: string` — posting textarea value; persists
- `analyzing: boolean` — true while SSE stream is active
- `stepMsg: string` — current step label (matched to STEP_LABELS)
- `analyzeError: string | null`
- `profileSliderOpen: boolean`
- `toasts: Toast[]`

**Module-level GC prevention:**
```typescript
let _analyzeTask: Promise<void> | null = null
```
`_runAnalysis` is assigned to `_analyzeTask` so the Promise is not garbage-collected when the component unmounts during navigation. This is the key mechanism that allows an analysis to survive a tab switch.

### SSE Stream Consumption (`frontend/src/lib/api.ts`)
`streamAnalyze()` is an async generator that reads an SSE stream via `ReadableStream`, accumulates text, splits on `\n`, and parses `data: {...}` lines. Yields typed events: `StepEvent | ResultEvent | ErrorEvent`.

### Page: AnalysePage
- Left panel: `<textarea>` for posting input, profile info, `Analysieren` button
- Right panel: `<StepList>` (while analyzing), error state, empty state, or results
- Results order: company header → ThresholdChip → `<Bewertung>` → `<CvDiff>` → `<Anschreiben>`
- `<ChatPopup>` fixed-position, only visible when results are present
- Scroll hint: animated "↑ Neue Ergebnisse" banner when results arrive

### Page: VerlaufPage
- Left panel: profile filter `<select>` + scrollable applications list (newest first)
- Right panel: same result layout as AnalysePage (Bewertung + CvDiff + Anschreiben)
- `<ChatPopup>` present whenever an app is selected
- `appToScoring()` converts `Application` to `ScoringResult` — per-dimension `score` values come from `scoring_details` JSONB, not the top-level `score` column

### Sidebar
Fixed 44px left-side bar. CSS-only expand: `.sb-inner:hover { width: 160px }`. Labels hidden by `.sb-label { opacity: 0; max-width: 0; overflow: hidden }`, revealed by `.sb-inner:hover .sb-label { opacity: 1; max-width: 120px }`. Critical invariant: these properties MUST remain in CSS classes, not inline styles (inline styles override `:hover` pseudo-class rules regardless of specificity, which was the root cause of a previous bug).

### Component: CvDiff
Receives raw diff string from backend. Filters to only `+` and `-` prefixed lines (context lines with 2-space prefix are hidden). Frontend also strips markdown from each line via `stripMarkdown()` — this handles old records stored before the backend diff fix (Task 12). Backend now also strips markdown before computing the diff, so new records are clean at the source.

**Diff algorithm limitation:** `compute_diff()` in `cv_editor.py` uses a set-based LCS approach. It outputs all context+removed lines first, then all added lines at the end — NOT an interleaved diff. The frontend hides context lines, so this is not visible to the user, but the diff is not positional.

### Component: ChatPopup
Opens a 340×440px fixed-position popup. Maintains message history in local state (resets if component unmounts). Streams assistant response token-by-token. Shows a pulsing dot while streaming an empty response. Does NOT persist chat history across page navigations or application selections.

---

## 5. LLM Pipeline — Complete Call Inventory

All calls go through `backend/llm.py`. Every call is logged to `llm_logs`. `call_structured` appends JSON schema to the user prompt and retries up to 2 times on parse failure.

### 5.1 Profile Setup Pipeline (on profile CREATE or UPDATE)

| # | Node | Model | Function | Input | Output | Max tokens |
|---|---|---|---|---|---|---|
| 1 | `market_research_extractor` | Haiku | `call_structured` | market_research text | `MarketResearchOutput` | 2048 |
| 2 | `binary_classifier` | Haiku | `call_structured` | cv_text + market_research → tech skill presence | `BinaryClassifierOutput` | 1024 |
| 3 | `core_skills_extractor` | Haiku | `call_structured` | cv_text + market_research | `CoreSkillsOutput` | 1024 |
| 4 | `candidate_profile_extractor` | Sonnet | `call_structured` | full context (cv, market, career target, skills) | `CandidateProfileOutput` | 2048 |

Steps 2+3 run in parallel (`asyncio.gather`). Step 4 depends on results from 1, 2, 3.

Results stored in `candidate_context` table as key-value pairs. `candidate_profile` stored as JSON string.

---

### 5.2 Main Analysis Pipeline (on each job posting analysis)

| # | Node | Model | Function | Input | Output | Temp | Max tokens |
|---|---|---|---|---|---|---|---|
| 1 | `company_extractor` | Haiku | `call_structured` | job_posting | `CompanyExtractorOutput` (company_name, search_name) | 0.0 | 300 |
| 2 | `cv_translator` | Sonnet | `call_raw` | cv_text + target_language | translated CV text | 0.2 | 3000 |
| 3 | `analyzer` | GPT-4.1 | `call_structured` | job_posting + candidate_profile + company_profile + cv_text | `AnalyzerOutput` (5 dimension scores + reasoning) | 0.0 | 2000 |
| 4 | `gap_analysis` | Sonnet | `call_raw` | job_posting + score summary + reasoning | 600-word explanation | 0.3 | 600 |
| 5 | `cv_classifier` | GPT-4.1 | `call_structured` | word_budget + career_target + job_posting + cv_items JSON | `ClassifierOutput` (KEEP/DISTRAKTOR/TRANSFERABEL per item) | 0.1 | 8192 |
| 6 | `cv_generator` | Haiku | `call_structured` | job_posting + career_target + items_to_process | `GeneratorOutput` (ENTFERNEN/KÜRZEN with new_content) | 0.1 | 8192 |
| 6r | `cv_generator_retry1` | Sonnet | `call_structured` | same as 6 + validation_errors | `GeneratorOutput` | 0.1 | 8192 |
| 7 | `cv_rewriter` | Haiku | `call_raw` | job_posting + edited_cv | polished CV text | 0.1 | 8192 |
| 8 | `anschreiben` | Sonnet | `call_raw` | job_posting + cv_text + company_profile + candidate_summary | cover letter body (no header/date) | 0.3 | 1000 |
| 9 | `chat` | Haiku | streaming | conversation history | streaming text | — | 1024 |

**Pipeline branching:**
- Steps 1+2 run in parallel (company research + translation)
- Step 4 (gap analysis) only runs if threshold = `fail`; steps 5-8 only run if threshold = `pass` or `caution`
- Step 6r (Sonnet retry) only runs if validator finds errors in Generator output
- CV translation (step 2) is cached: skipped if `cv_language == job_language` or if SHA-256 of cv_text matches stored hash

---

### 5.3 Scoring Logic (Deterministic)

**Threshold calculation (`deterministic/scoring.py`):**
- `pass`: total ≥ 60 AND neither technical nor requirements score = 0
- `caution`: total ≥ 45 AND critical dims ≠ 0; OR total ≥ 60 but a critical dim = 0
- `fail`: everything else

**Dimension maxima:** technical/40, requirements/25, role_fit/20, location/10, strategic/5 (total max = 100)

---

### 5.4 CV Tailoring Detail

**Word budget:** target = max(700, min(0.80 × word_count, 950)). If CV already ≤ 700 words, no budget pressure.

**Classifier → Enforcer mapping:**
- `DISTRAKTOR` → Enforcer produces `ENTFERNEN` instruction
- `TRANSFERABEL` → Enforcer produces `KÜRZEN` if item ≥ 25 words, else implicitly KEEP
- `KEEP` → not passed to Generator at all

**Validator checks:**
1. No-op: item marked KÜRZEN but content unchanged
2. TRANSFERABEL + ENTFERNEN: forbidden (must be KÜRZEN)
3. Cluster guard: if >50% of items in one section marked ENTFERNEN → validation error

On validation error: retry with Sonnet + error context. On second failure: exception propagates.

**Apply removes:** Regex pattern `[ \t]*(?:[-•*]\s+)? + re.escape(content) + [ \t]*\n?` for exact-match line removal. KÜRZEN applied via `str.replace(original, replacement, 1)`.

---

## 6. Job-Profile Matching Logic

The Analyzer (GPT-4.1) evaluates 5 dimensions. The system prompt in `prompts/v1/analyzer_system.txt` defines the rubric (not read in this session — contents opaque from report perspective). The structured output constrains scores to Pydantic ranges (technical 0-40, etc.). After scoring, `calculate_dimensions()` clamps any out-of-range values.

The candidate profile JSON (from `candidate_context.candidate_profile`) is passed directly to the Analyzer. This JSON is built by `CandidateProfileOutput` (Sonnet, during profile setup). The schema of this model is in `backend/models/profile.py`.

The company profile (800-word Google snippet) is also injected into the Analyzer. If SerpAPI fails, company_profile is empty string — the Analyzer runs with no company context but still produces valid scores.

---

## 7. CV Tailoring Logic (Detailed)

```
1. Parse CV → numbered items (item_000, item_001, ...)
   - Lines starting with ## → section headers (not items)
   - Each non-empty, non-header line → one item (content stripped of leading -•*)

2. Compute word budget

3. GPT-4.1 Classifier
   - Receives: all items + job_posting + career_target + word_budget
   - Outputs: per-item KEEP / DISTRAKTOR / TRANSFERABEL

4. Enforcer (deterministic)
   - DISTRAKTOR → ENTFERNEN instruction
   - TRANSFERABEL + len ≥ 25 words → KÜRZEN instruction
   - KEEP → nothing sent to Generator

5. Haiku Generator
   - Receives: only items that need action (ENTFERNEN or KÜRZEN)
   - Outputs: per-item ENTFERNEN / KÜRZEN with new_content

6. Validator
   - 3 checks (no-op, transferabel-remove, cluster-guard-50%)
   - If invalid → retry with Sonnet

7. Apply edits (deterministic)
   - KÜRZEN: str.replace(original_content, new_content, 1) on cv_text
   - ENTFERNEN: regex removal of matching line

8. Haiku Rewriter
   - Receives full edited CV + job_posting
   - Returns polished version (fixes flow, transitions)

9. compute_diff(original, rewritten)
   - Strips markdown from both before LCS comparison
   - Outputs +/- prefixed lines
```

**Known limitation in diff algorithm:** `common = set(_lcs(...))` — this uses a SET of common line texts, not indices. If the same text appears in both CVs at different positions, it will always be classified as "common" regardless of context. Short or generic lines (e.g. "Python", "3 Jahre") could produce false positives in the LCS.

---

## 8. Cover Letter Logic

**Model:** Sonnet, temperature 0.3, max 1000 tokens.  
**Input:** job_posting + company_name + company_profile + cv_text (tailored) + candidate_summary (name, core skills, career_target, work format preference, location/commute).  
**Output:** Body text only — no date, no sender/recipient address block.

The DOCX export (`generate_anschreiben_docx`) adds a structural sender block (name + city right-aligned) and recipient block (company name). The `candidate_address` is the profile's `city` field — a city name, not a full street address.

**Limitation:** The Anschreiben textarea in the UI shows raw body text with no header. The header is only present in the downloaded DOCX. There is no way for the user to see or edit the full formatted letter in-app.

---

## 9. Data Model (PostgreSQL)

All tables in schema `job_application_assistant` in database `projects`.

### `profiles`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| first_name | TEXT | |
| last_name | TEXT | |
| email | TEXT | |
| phone_country_code | TEXT | |
| phone_number | TEXT | |
| street_address | TEXT | |
| postal_code | TEXT | |
| city | TEXT | Used in docx cover letter as sender address |
| linkedin_url | TEXT | |
| github_url | TEXT | |
| avatar_url | TEXT | base64 data URL (can be very long) |

### `candidate_context`
| Column | Type | Notes |
|---|---|---|
| profile_id | INT FK profiles | |
| key | TEXT | |
| value | TEXT | |
| updated_at | TIMESTAMPTZ | |
| PK | (profile_id, key) | |

Known keys: `cv_text`, `market_research`, `career_target`, `cv_language`, `candidate_profile` (JSON string), `translated_cv_text_{lang}`, `translated_cv_text_{lang}_source_hash`

### `job_applications`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| profile_id | INT FK profiles | |
| company | TEXT | |
| role_title | TEXT | First non-empty line of job_posting, max 200 chars |
| job_posting | TEXT | Full raw posting stored |
| score | INT | Total 0-100 |
| threshold | TEXT | 'pass', 'caution', 'fail' |
| cv_diff | TEXT | LCS diff output string |
| tailored_cv | TEXT | Full tailored CV (added in migration 003) |
| anschreiben | TEXT | Cover letter body only |
| gaps | TEXT | Gap analysis text (fail path only) |
| scoring_details | JSONB | {technical, requirements, role_fit, location, strategic} each {score, reasoning} |
| date_applied | TIMESTAMPTZ | |

### `llm_logs`
| Column | Type |
|---|---|
| id | SERIAL PK |
| model | VARCHAR(100) |
| node_name | VARCHAR(100) |
| profile_id | INT FK profiles |
| input_tokens | INT |
| output_tokens | INT |
| latency_ms | INT |
| cost_usd | NUMERIC(12,6) |
| created_at | TIMESTAMPTZ |

### `llm_node_benchmarks`
Stores manual benchmark runs from `benchmark.py`. Not used in production flow.

### `model_pricing`
Referenced by `llm.py:_compute_cost()`. Columns: `model`, `input_price`, `output_price` (per 1M tokens). If a model is not in this table, cost is logged as 0.0.

---

## 10. Quality Risks

### 10.1 Functional Risks

**[F1] No auth or rate limiting.** Any request to `/api/analyze` runs the full LLM pipeline (~8 sequential/parallel LLM calls). If exposed externally, one request could cost ~$0.05-0.20 USD.

**[F2] Dead code in `analyze.py`.** The unused first `generate()` function creates confusion about which code path is active. It should be deleted.

**[F3] Chat endpoint ignores job_application_id.** The model has no access to the stored application data (posting, CV diff, scores). It can only respond to what the user pastes in. The system prompt claims to be a "Bewerbungsassistent" but has no actual application context.

**[F4] `_extract_role_title` is unreliable.** Returns the first non-empty line of the job posting (max 200 chars). If the posting starts with "Wir sind ein führendes Unternehmen...", role title is garbage. This is stored in `job_applications.role_title`.

**[F5] Old applications have no `tailored_cv`.** Migration 003 added the column but old rows have `NULL`. Download endpoint returns 404. Task 13 (better error message) is pending.

**[F6] CvDiff shows only +/- lines, no context.** User cannot see where in the CV each change was made — no surrounding context. The "show more" button reveals more changes but still no position context.

**[F7] Anschreiben body has no date or greeting in the UI.** The textarea shows plain body text. User doesn't know who the letter is addressed to or when it's dated until they download the DOCX.

**[F8] Profile avatar stored as base64 data URL.** Could be very large (10s of KB) per row, returned on every `GET /api/profiles` response. For a single-user app this is acceptable but would scale poorly.

---

### 10.2 Technical Risks

**[T1] asyncpg pool on module-level singleton.** Pool is created on first request and never reset on reconnection failure. If Postgres restarts while the container is running, connections fail silently until the next cold start.

**[T2] SSE step-draining with `asyncio.wait_for` timeout=0.5s.** If a pipeline step completes in <0.5s, the next step event may be delayed by up to 0.5s in the drain loop. For a pipeline with 6 steps this adds ~3s of latency to event delivery.

**[T3] `_analyzeTask` module-level reference.** This prevents the GC from collecting a running analysis. However, if the server restarts mid-analysis (container redeploy), the frontend's SSE connection drops and there is no reconnect mechanism — the user sees no result and no error.

**[T4] `compute_diff` uses `set()` for common lines.** If the same line appears multiple times in the CV (e.g. "Python", "3 Jahre Erfahrung"), the LCS set conflates all occurrences. The diff may misclassify some changes.

**[T5] `apply_removes_by_content` uses `re.escape()` + substring.** If a CV item contains special regex characters (rare but possible), the `re.escape()` handles it. But if the same content string appears in multiple lines (e.g. a skill listed in two sections), only the first match per item is removed.

**[T6] Docker `network_mode: host` required for local Postgres.** Not portable; will not work in cloud environments where DB is on a separate host without code changes.

**[T7] ARCHITECTURE.md is out of date.** Still references NiceGUI and the old Python-rendered UI. Misleading for any new developer.

**[T8] 11 near-identical design-interview routes in `main.py`.** These should be consolidated but create noise in the codebase and increase startup time marginally.

---

### 10.3 LLM / Semantic Risks

**[L1] CV classifier (GPT-4.1) receives ALL items.** For a long CV (200+ items), the prompt may become very long. The 8192 token limit is generous, but there is no chunking or batching logic. If a CV exceeds this, the call will fail.

**[L2] Generator retry uses Sonnet.** If the Haiku Generator consistently fails validation for a given CV, the Sonnet retry is also subject to the same validator. If Sonnet also fails, the pipeline raises an exception and the user sees an error. No graceful degradation (e.g., return unmodified CV).

**[L3] `detect_language()` is stopword-frequency only.** Mixed-language CVs (German CV with English technical terms) could misdetect as English. This would trigger unnecessary translation via Sonnet, adding latency and cost.

**[L4] Translation cache invalidates on any CV change.** Even a one-character edit to the CV invalidates the `translated_cv_text_en` cache. If the user frequently edits their CV, translation is re-run on every analysis for English job postings.

**[L5] `_strip_md()` regex is not idempotent for all cases.** The italic regex `_([^_\s][^_]*)_` could theoretically produce incorrect results for certain underscored identifiers (e.g., snake_case variable names). Low risk for German CVs but worth noting.

**[L6] Anschreiben prompt gets 1000 token max.** German cover letters average ~300-500 words. 1000 tokens is usually sufficient but could truncate an unusually long response.

**[L7] No validation that the Anschreiben is actually in the correct language.** If `job_language = 'en'` but the prompt instructs German output by default, the anschreiben prompt system prompt must handle language switching. The `<job_language>` tag is included in the user prompt — but whether the system prompt properly handles it depends on prompt content (not inspected in this report).

---

### 10.4 Security Risks

**[S1] No input validation on job_posting length.** A malicious or accidental 100,000-word posting would be sent to multiple LLMs. Should add a max-length check (e.g., 50,000 chars).

**[S2] `_di*.html` files served without auth.** The design-interview forms are accessible to anyone with the URL. They save answers to local `.json` files. Minor for an internal tool but noteworthy.

**[S3] CORS configured for localhost dev origins only.** The production deployment goes through Caddy (same-origin). This is correct. But if someone adds a new origin without updating CORS, requests will be blocked in production.

**[S4] `.env` in repo root.** gitignored, but `.env.example` is committed with placeholder values. The `.env` itself is referenced in `docker-compose.yml` via `env_file: [.env]`. If accidentally committed, API keys would be exposed.

**[S5] Avatar stored as data URL in DB.** No size limit enforced. A user could upload a 10MB image; `process_avatar()` in `avatar.py` does resize with Pillow, but the max output size should be verified.

---

### 10.5 UX Risks

**[U1] Analysis state is not persisted across server restarts.** If the server restarts mid-analysis or after completion, the `AppContext` state is lost on next page load. The user would need to re-run the analysis. Historical results are in Verlauf but the fresh result on the analyze page is gone.

**[U2] `role_title` extraction failure is silent.** A badly extracted role title in `job_applications` shows up in the Verlauf panel with no indication that it's wrong.

**[U3] Chat has no history persistence.** Closing the popup or switching applications resets the chat. The welcome message resets each time.

**[U4] No loading state on profile slider open.** If profiles are slow to load (`GET /api/profiles`), the slider appears empty for a moment.

**[U5] `Anschreiben` textarea is editable but edits are lost on navigation.** The user can edit the cover letter text but if they navigate away, the edit is gone. Only the stored version (from the pipeline) is in the DB.

---

### 10.6 Cost Risks

**[C1] Each analysis runs 6-8 LLM calls.** Approximate costs per analysis:
- company_extractor (Haiku): ~$0.001
- analyzer (GPT-4.1, 2000 tokens out): ~$0.006
- cv_classifier (GPT-4.1, 8192 tokens out): ~$0.025
- cv_generator (Haiku, 8192 tokens out): ~$0.005
- cv_rewriter (Haiku, 8192 tokens out): ~$0.005
- anschreiben (Sonnet, 1000 tokens out): ~$0.005
- cv_translator (Sonnet, 3000 tokens out): ~$0.015 (only on language mismatch)
- Total per analysis: ~$0.04-0.07 USD

**[C2] No analysis deduplication.** The same job posting can be analyzed multiple times. There is no check for duplicate postings.

**[C3] LLM logs don't capture prompt content.** Cost data is captured but without the actual prompts, debugging expensive or broken calls requires log correlation by time + node_name.

---

## 11. Testing Status

**There are no automated tests in this repository.** No `tests/` directory, no pytest configuration, no CI/CD configuration.

All verification has been done manually (user testing via browser). The `llm_node_benchmarks` table and `benchmark.py` suggest some manual benchmarking was done, but this is not a test suite.

**Missing tests (high priority):**
1. `deterministic/scoring.py:calculate_threshold` — pure function, testable with 10 cases
2. `deterministic/cv_editor.py:compute_diff` — compare known inputs/outputs
3. `deterministic/word_budget.py:compute_word_budget` — boundary cases
4. `deterministic/language.py:detect_language` — mixed-language inputs
5. `llm.py:_strip_fences` — various markdown fence formats
6. API endpoints — FastAPI `TestClient` + mocked LLM calls
7. `docx_export.py` — verify bytes output is valid DOCX (python-docx can re-parse it)

---

## 12. Questions for the Next Auditor (Claude Opus 4.8)

1. **Prompt quality:** Read all 12 prompt files in `backend/prompts/v1/`. Do they have clear, unambiguous instructions? Are the JSON schemas explicitly stated? Are there conflicts between what the prompt asks and what the Pydantic model validates?

2. **Classifier accuracy:** The CV classifier (GPT-4.1) determines what gets removed or shortened. Is the distinction between DISTRAKTOR and TRANSFERABEL clear enough in the prompt? What's the failure mode if a critical skill is classified as DISTRAKTOR?

3. **Chat context injection:** Should the `chat` endpoint fetch the stored job_application data (posting, cv_diff, scoring_details, anschreiben) and inject it as system context? This would make the chat genuinely useful rather than a generic assistant.

4. **Diff UX:** The current diff shows only what changed, with no positional context. Should we switch to an interleaved diff (showing unchanged context lines between changes)? The LCS algorithm can support this.

5. **Generator retry strategy:** Currently if Haiku fails validation, Sonnet retries with the error context. Should the retry just skip the validator entirely and pass the Sonnet output directly (trusting Sonnet more)? Or add a second Sonnet retry?

6. **Old application handling (Task 13):** For applications where `tailored_cv` is NULL, what should the DOCX download do? Options: (a) return 404 with a clear user message, (b) reconstruct from `cv_diff` (reverse-apply additions to infer full CV), (c) return the original un-tailored CV.

7. **ARCHITECTURE.md:** Should be rewritten to reflect the current React+FastAPI stack. The current doc references NiceGUI and an old module structure that no longer exists.

8. **Design interview routes:** Should all 11 `/design-interview-*` routes be extracted to a separate blueprint/router or simply deleted?

9. **Profile extraction cost:** Every profile save triggers 4 LLM calls. Is this appropriate? Should some steps (e.g., binary_classifier, core_skills_extractor) only run on CV change, not on profile metadata updates?

10. **Word budget effectiveness:** The 80% target (700-950 word range) — is this actually reducing CV length for candidates? Does the validator's cluster guard (50% remove limit) prevent meaningful tailoring for over-qualified candidates?

---

*End of report. All information derived from current codebase state as of 2026-06-21.*
