# Architecture

## Overview

The current system is a deterministic multi-workflow n8n pipeline built around profile-scoped candidate data.

The exported setup is split into:

1. `utility-extract-profile.json`
2. `utility-get-profiles.json`
3. `main-workflow.json`
4. `company-research.json`
5. `cv-translation-cache.json`
6. `analysis-scoring.json`
7. `cv-tailoring-planner.json`

`main-workflow.json` is the runtime orchestrator. The other runtime JSONs are called through `Execute Workflow` nodes.

Core design properties:

- profile data is stored per `profile_id`
- scoring arithmetic is computed in code
- CV translation is cached and invalidated with `cv_hash`
- CV tailoring is separated into classify, enforce, generate, validate, and rewrite stages
- pass/caution and fail branches converge into one formatter

## High-Level Flow

```text
utility-extract-profile.json
  POST /profile-setup
    -> CREATE TABLES
    -> Validate Inputs
    -> Hash CV + Detect CV Language
    -> create or update profiles row
    -> UPSERT source keys into candidate_context
    -> if cv changed: delete translation cache keys
    -> if source fields require refresh:
       Fetch Full Context
       -> market-research extraction + core-skill extraction
       -> Dynamic Filter
       -> Extract Candidate Profile
       -> UPSERT candidate_profile + role_type_scores
    -> success response

utility-get-profiles.json
  GET /profiles
    -> SELECT * FROM profiles
    -> Respond to Webhook

main-workflow.json
  POST /job-application
    -> Guardrails
    -> Validate Profile ID
    -> Fetch Config + Load Config
    -> Input Wrapper
    -> Call Company Research
    -> Call CV Translation Cache
    -> Call Analysis Scoring
    -> Passed Threshold?
       -> true: Call CV Tailoring Planner -> deterministic edit step -> CV Rewriter -> Diff Engine -> Anschreiben
       -> false: Gap Analysis
    -> Format + Respond
    -> Respond to Webhook
    -> INSERT Job Application in DB
```

## Main Workflow

### Entry and validation

- `Webhook` exposes `POST /job-application`
- `Guardrails` checks `body.chatInput`
- `Validate Profile ID` requires a positive integer in `body.profile_id`
- rejected prompt-injection input goes to `Respond: Error`
- invalid profile IDs go to `Respond: Error1`

The guardrails rejection branch returns plain text:

`I'm sorry, the text contains patterns that I can't process. Please paste only the text of the job posting.`

### Config loading

`Fetch Config` loads these fixed keys from PostgreSQL for the requested `profile_id`:

- `candidate_profile`
- `role_type_scores`
- `cv_text`
- `cv_language`
- `guide_text_de`
- `guide_text_en`

`Load Config` parses:

- `candidate_profile`
- `cv_language`
- `role_type_scores`

### Input normalization

`Input Wrapper`:

- validates minimum input length
- wraps the posting in `<job_posting> ... </job_posting>`
- heuristically detects posting language
- outputs:
  - `job_posting_wrapped`
  - `job_post_language`
  - `raw_input`
  - `char_count`

### Company research sub-workflow

`Call Company Research` executes `company-research.json`.

That sub-workflow:

- extracts `company_name` and `search_name`
- builds a deterministic query
- optionally runs SerpAPI
- returns:
  - `company_name`
  - `company_profile`
  - `search_results_found`

### CV translation sub-workflow

`Call CV Translation Cache` executes `cv-translation-cache.json`.

That sub-workflow:

- compares `cv_language` with posting language
- fetches profile-scoped cache keys:
  - `translated_cv_text_<language>`
  - `cv_hash`
  - `translated_cv_text_<language>_source_hash`
- reuses cached translation only when both translated text exists and the hash matches
- otherwise translates the CV and stores:
  - `translated_cv_text_<language>`
  - `translated_cv_text_<language>_source_hash`
- resolves:
  - `cv_text_final`
  - `guide_text_final`

### Analysis scoring sub-workflow

`Call Analysis Scoring` executes `analysis-scoring.json`.

The LLM returns semantic judgments in `scoring_inputs`, including:

- `core_skills_match_count`
- `secondary_tools_match_count`
- `skill_gaps_classification`
- `muss_kriterien_met`
- `muss_kriterien_total`
- `format_match`
- `role_type_category`
- `location_classification`
- `strategic_brand`
- `strategic_ai`
- `strategic_gaps_exposure`

Then code nodes compute:

- `technical`
- `requirements`
- `role_fit`
- `location`
- `strategic`

Finally `Calculate Threshold` computes:

- `pass` for `>= 55`
- `caution` for `45-54`
- `fail` for `< 45`

### Pass/caution generation branch

If threshold is not `fail`, the main workflow calls `cv-tailoring-planner.json`.

That sub-workflow:

- computes a target CV budget of 500 words
- classifies CV segments as `DIREKT`, `TRANSFERABEL`, or `DISTRAKTOR`
- enforces deterministic action rules
- generates `cv_anpassungen`
- validates generated instructions
- retries only flagged transferable-removal mistakes

Back in `main-workflow.json`:

- `CV Deterministic Editor` removes `ENTFERNEN` items deterministically before LLM rewrite
- `CV Rewriter` produces the full rewritten CV
- `Diff Engine` returns:
  - `cv_markdown`
  - `cv_diff`
- `Anschreiben` generates the cover letter using:
  - score context
  - company context
  - resolved guide text
  - CV-tailoring context

### Fail branch

`Gap Analysis` returns exactly three sections:

- why the role is not an optimal fit
- the two most important gaps and next actions
- better-fitting alternatives

### Final formatting and logging

`Format + Respond` always returns:

- `output`
- `cv_diff`
- `cv_markdown`
- `body_text`

`Respond to Webhook` sends JSON with:

- `output`
- `cv_diff`
- `cv_markdown`

`INSERT Job Application in DB` writes:

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

It uses `continueErrorOutput`, so logging failure does not necessarily block the webhook response.

## Utility Workflows

### `utility-extract-profile.json`

This is the profile provisioning and refresh workflow exposed at `POST /profile-setup`.

It supports two modes:

- create mode: requires profile metadata plus the five core context fields
- update mode: requires `profile_id`, then updates only provided fields

Stored source keys:

- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`

Derived keys:

- `cv_hash`
- `cv_language`
- `candidate_profile`
- `role_type_scores`

Important behavior reflected in the current workflow:

- `profiles` rows are created or updated before context writes
- all `candidate_context` writes are scoped by `profile_id`
- when `cv_text` changes, cached translations for `en` and `de` are deleted
- LLM extraction only reruns when a refresh is needed; simple profile metadata updates can return success without recomputing derived keys
- `role_type_scores` is stored as a JSON string and must contain exactly one role with score `12`

### `utility-get-profiles.json`

This helper workflow exposes `GET /profiles` and returns ordered rows from `job_application_assistant.profiles`.

## Data Model

All tables live in the `job_application_assistant` schema.

### `profiles`

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

Columns:

- `profile_id`
- `key`
- `value`
- `updated_at`

It contains:

- manual source inputs
- generated candidate-profile data
- translation cache data

### `job_applications`

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
