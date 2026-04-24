# Job Application Assistant

An n8n-based job-application pipeline that evaluates a pasted job posting against a stored candidate profile, scores fit from 0 to 100, and returns either:

- an application package for `pass` and `caution` matches
- a gap analysis for `fail` matches

The current exported setup is built from seven workflows:

1. `utility-extract-profile.json`
2. `utility-get-profiles.json`
3. `main-workflow.json`
4. `company-research.json`
5. `cv-translation-cache.json`
6. `analysis-scoring.json`
7. `cv-tailoring-planner.json`

## What It Does

The runtime entry point is `POST /job-application`.

For each request, the system:

- validates `body.profile_id`
- runs prompt-injection guardrails on `body.chatInput`
- loads candidate context from PostgreSQL for that profile
- extracts the hiring company and optionally enriches it with SerpAPI
- resolves CV language using a translation cache keyed by target language and source CV hash
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
Profile create/update workflow exposed at `POST /profile-setup`. It:

- creates the `job_application_assistant` schema and the `profiles`, `candidate_context`, and `job_applications` tables
- creates a new profile or updates an existing one
- stores source inputs in `candidate_context`
- computes `cv_hash`
- detects `cv_language`
- regenerates `candidate_profile` and `role_type_scores` when needed
- clears translated CV cache keys if the CV changed

Stored source keys:

- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`

Generated keys:

- `candidate_profile`
- `role_type_scores`
- `cv_language`
- `cv_hash`

### `utility-get-profiles.json`
Simple helper workflow exposed at `GET /profiles`. It returns rows from the `profiles` table so a UI or client can list selectable candidate profiles.

### `main-workflow.json`
Runtime webhook workflow exposed at `POST /job-application`. It orchestrates the runtime sub-workflows, validates the profile ID, formats output, and logs the run.

### `company-research.json`
Extracts the company name from the posting, builds a deterministic search query, optionally runs SerpAPI, and returns:

- `company_name`
- `company_profile`
- `search_results_found`

### `cv-translation-cache.json`
Resolves `cv_text_final` and `guide_text_final`.

Important behavior:

- if CV language already matches posting language, it reuses the base CV
- otherwise it checks `translated_cv_text_<language>` for the current `profile_id`
- it only reuses a cached translation when the stored `translated_cv_text_<language>_source_hash` matches the current `cv_hash`
- on cache miss or stale cache, it retranslates and rewrites both keys

### `analysis-scoring.json`
Runs structured semantic analysis and computes dimension scores in code.

The final threshold logic is:

- `pass` for scores `>= 55`
- `caution` for scores `45-54`
- `fail` for scores `< 45`

### `cv-tailoring-planner.json`
Classifies CV segments, applies deterministic action rules, enforces a target word budget of 500 words, generates `cv_anpassungen`, and corrects invalid transferable-removal instructions before the main workflow rewrites the CV.

## Database Model

All tables live in the `job_application_assistant` schema.

### `profiles`
Profile metadata table.

Columns:

- `id`
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `website_url`
- `avatar_url`
- `notes`
- `created_at`
- `updated_at`

### `candidate_context`
Profile-scoped key-value store for:

- manual source inputs
- generated candidate profile data
- CV translation cache data

Columns:

- `profile_id`
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
- `profile_id`
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

## API Contracts

### `POST /profile-setup`

Create profile:

```json
{
  "full_name": "Candidate Name",
  "cv_text": "Plain-text CV",
  "guide_text_de": "German guide",
  "guide_text_en": "English guide",
  "market_research": "Structured market research",
  "career_target": "Target role strategy"
}
```

Update profile:

```json
{
  "profile_id": 1,
  "cv_text": "Updated plain-text CV"
}
```

Success response:

```json
{
  "success": true,
  "profile_id": "1",
  "action": "created"
}
```

### `GET /profiles`

Returns all profile rows ordered by `full_name`.

### `POST /job-application`

Minimal request body:

```json
{
  "profile_id": 1,
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

Validation / guardrails rejection responses:

- invalid `profile_id`: JSON error
- rejected posting content: plain text, not JSON

## Prerequisites

- self-hosted n8n
- PostgreSQL reachable from n8n
- Anthropic credentials with access to:
  - Claude Haiku 4.5
  - Claude Sonnet 4.6
- SerpAPI credential
- enough timeout budget for several sequential LLM calls

## Quick Start

1. Import all seven workflow JSON files.
2. Re-map credentials.
3. Run `POST /profile-setup` with the required profile payload.
4. Verify the new `profile_id` exists in `profiles`.
5. Verify `candidate_context` contains the expected keys for that profile.
6. Activate `main-workflow.json` and `utility-get-profiles.json`.
7. Send a test `POST /job-application` request with `profile_id` and `chatInput`.

## Docs

- [docs/setup-guide.md](/d:/Yo/github/job-application-assistant/docs/setup-guide.md)
- [docs/architecture.md](/d:/Yo/github/job-application-assistant/docs/architecture.md)
- [config/candidate_context_template.md](/d:/Yo/github/job-application-assistant/config/candidate_context_template.md)
