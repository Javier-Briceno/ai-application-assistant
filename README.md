# Job Application Assistant

An n8n-based application workflow that evaluates a pasted job posting against a stored candidate profile, scores fit from 0 to 100, and returns either:

- an application package for `pass` and `caution` matches
- a gap analysis for `fail` matches

The current exported setup is built from six workflows:

1. `utility-extract-profile.json`
2. `main-workflow.json`
3. `company-research.json`
4. `cv-translation-cache.json`
5. `analysis-scoring.json`
6. `cv-tailoring-planner.json`

## What It Does

The runtime entry point is `POST /job-application`.

For each request, the system:

- runs prompt-injection guardrails on `body.chatInput`
- detects the job posting language heuristically
- loads candidate context from PostgreSQL
- extracts the hiring company and optionally enriches it with SerpAPI
- resolves CV language using a translation cache keyed by both target language and source CV hash
- scores the role across five dimensions
- generates either:
  - an application package with tailored CV artifacts and an individualized `Anschreiben`, or
  - a structured gap analysis
- returns JSON with:
  - `output`
  - `cv_diff`
  - `cv_markdown`
- attempts to log the run to `job_applications`

## Workflow Layout

### `utility-extract-profile.json`
Manual bootstrap and profile-refresh workflow. It:

- creates `candidate_context` and `job_applications`
- stores the manual source inputs from `Set Up Workflow Context`
- computes `cv_hash`
- detects the base CV language
- extracts `candidate_profile`
- extracts `role_type_scores`
- writes everything to PostgreSQL

It currently persists these fixed keys:

- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`
- `candidate_profile`
- `role_type_scores`
- `cv_language`
- `cv_hash`

### `main-workflow.json`
Runtime webhook workflow. It orchestrates the other sub-workflows and handles branching, formatting, and logging.

### `company-research.json`
Extracts the company name from the posting, builds a deterministic search query, optionally runs SerpAPI, and returns a compact `company_profile`.

### `cv-translation-cache.json`
Resolves `cv_text_final` and `guide_text_final`.

Important behavior:

- if CV language already matches posting language, it reuses the base CV
- otherwise it checks `translated_cv_text_<language>`
- it only reuses a cached translation when the stored `translated_cv_text_<language>_source_hash` matches the current `cv_hash`
- on cache miss or stale cache, it retranslates and rewrites both keys

### `analysis-scoring.json`
Runs structured semantic analysis and computes dimension scores in code.

The final threshold logic is:

- `pass` for scores `>= 55`
- `caution` for scores `45-54`
- `fail` for scores `< 45`

### `cv-tailoring-planner.json`
Classifies CV segments, enforces action rules, generates `cv_anpassungen`, and corrects invalid edit instructions before the main workflow rewrites the CV.

## Database Model

### `candidate_context`
Key-value store for:

- manual source inputs
- generated candidate profile data
- CV translation cache data

Columns:

- `key`
- `value`
- `updated_at`

Common runtime cache keys:

- `translated_cv_text_en`
- `translated_cv_text_de`
- `translated_cv_text_<language>_source_hash`

### `job_applications`
Application-run log table.

Columns:

- `id`
- `company`
- `role_title`
- `job_posting`
- `score`
- `threshold`
- `location_type`
- `gaps`
- `highlights`
- `cv_diff`
- `anschreiben`
- `date_applied`
- `status`
- `notes`

## Request Contract

Webhook:

- `POST /job-application`

Minimal request body:

```json
{
  "chatInput": "Paste the full job posting text here"
}
```

Success response:

```json
{
  "output": "markdown report with score header and body",
  "cv_diff": "line diff between original and rewritten CV",
  "cv_markdown": "full rewritten CV in markdown"
}
```

Guardrails rejection response:

- plain text, not JSON

## Prerequisites

- self-hosted n8n
- PostgreSQL reachable from n8n
- Anthropic credentials with access to:
  - Claude Haiku 4.5
  - Claude Sonnet 4.6
- SerpAPI credential
- enough timeout budget for several sequential LLM calls

## Quick Start

1. Import all six workflow JSON files.
2. Re-map credentials.
3. Run `CREATE TABLES` from `utility-extract-profile.json`.
4. Fill `Set Up Workflow Context`.
5. Execute the utility workflow.
6. Verify `candidate_context` contains the fixed keys, including `cv_hash`.
7. Activate `main-workflow.json`.
8. Send a test `POST /job-application` request.

## Docs

- [docs/setup-guide.md](/d:/Yo/github/job-application-assistant/docs/setup-guide.md)
- [docs/architecture.md](/d:/Yo/github/job-application-assistant/docs/architecture.md)
- [config/candidate_context_template.md](/d:/Yo/github/job-application-assistant/config/candidate_context_template.md)
