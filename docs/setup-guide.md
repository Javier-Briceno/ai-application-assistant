# Setup Guide

This guide matches the current exported workflows:

- `utility-extract-profile.json`
- `utility-get-profiles.json`
- `main-workflow.json`
- `company-research.json`
- `cv-translation-cache.json`
- `analysis-scoring.json`
- `cv-tailoring-planner.json`

## Prerequisites

Before importing anything, make sure you have:

- n8n running and reachable
- PostgreSQL reachable from n8n
- Anthropic credentials with access to:
  - Claude Haiku 4.5
  - Claude Sonnet 4.6
- SerpAPI credential
- enough timeout budget for several sequential LLM calls

## Step 1: Import All Workflows

Import these files into n8n:

1. `utility-extract-profile.json`
2. `utility-get-profiles.json`
3. `company-research.json`
4. `cv-translation-cache.json`
5. `analysis-scoring.json`
6. `cv-tailoring-planner.json`
7. `main-workflow.json`

Recommended order:

- utility workflows first
- runtime sub-workflows second
- main last

After import, re-map credentials where needed.

## Step 2: Check Credentials

You should see these credential types in use:

- Postgres
- Anthropic API
- SerpAPI

Verify all required nodes show valid credentials before execution.

## Step 3: Create Database Tables

Open `utility-extract-profile.json` and execute the workflow once through `POST /profile-setup`.

The workflow runs `CREATE TABLES` automatically and creates:

- schema `job_application_assistant`
- `profiles`
- `candidate_context`
- `job_applications`

The SQL uses `CREATE ... IF NOT EXISTS`, so re-running is safe.

Current schema:

`profiles`

- `id SERIAL PRIMARY KEY`
- `full_name TEXT NOT NULL`
- `email TEXT`
- `phone TEXT`
- `location TEXT`
- `linkedin_url TEXT`
- `github_url TEXT`
- `website_url TEXT`
- `avatar_url TEXT`
- `notes TEXT`
- `created_at TIMESTAMP DEFAULT NOW()`
- `updated_at TIMESTAMP DEFAULT NOW()`

`candidate_context`

- `profile_id INTEGER NOT NULL REFERENCES job_application_assistant.profiles(id) ON DELETE CASCADE`
- `key VARCHAR(100) NOT NULL`
- `value TEXT NOT NULL`
- `updated_at TIMESTAMP DEFAULT NOW()`
- `PRIMARY KEY (profile_id, key)`

`job_applications`

- `id SERIAL PRIMARY KEY`
- `profile_id INTEGER REFERENCES job_application_assistant.profiles(id) ON DELETE SET NULL`
- `company VARCHAR(200)`
- `role_title VARCHAR(200)`
- `job_posting TEXT`
- `score INTEGER`
- `threshold VARCHAR(20)`
- `location_type VARCHAR(50)`
- `gaps TEXT`
- `highlights TEXT`
- `cv_diff TEXT`
- `anschreiben TEXT`
- `date_applied TIMESTAMP DEFAULT NOW()`
- `status VARCHAR(50) DEFAULT 'applied'`
- `notes TEXT`

## Step 4: Create a Profile with `POST /profile-setup`

`utility-extract-profile.json` is now webhook-driven. For a new profile, send a request to:

- `POST /profile-setup`

Required fields in create mode:

- `full_name`
- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`

Optional profile metadata fields:

- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `website_url`
- `avatar_url`
- `notes`

Example request:

```bash
curl -X POST "http://YOUR_N8N_HOST/webhook/profile-setup" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Candidate Name",
    "cv_text": "Plain-text CV",
    "guide_text_de": "German guide",
    "guide_text_en": "English guide",
    "market_research": "Structured market research",
    "career_target": "Target role strategy"
  }'
```

## Step 5: Verify the Profile Was Created

Successful create or update responses look like:

```json
{
  "success": true,
  "profile_id": "1",
  "action": "created"
}
```

Verify the row exists:

```sql
SELECT id, full_name, updated_at
FROM job_application_assistant.profiles
ORDER BY id DESC;
```

## Step 6: Verify Stored Context Keys

After profile setup finishes, verify that `candidate_context` contains at least these keys for the new `profile_id`:

- `candidate_profile`
- `career_target`
- `cv_hash`
- `cv_language`
- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `role_type_scores`

Example query:

```sql
SELECT key, updated_at
FROM job_application_assistant.candidate_context
WHERE profile_id = 1
ORDER BY key;
```

At this stage, `translated_cv_text_<language>` and `translated_cv_text_<language>_source_hash` may still be absent.

## Step 7: Check Sub-Workflow References

Open `main-workflow.json` and confirm the `Execute Workflow` nodes point to the imported sub-workflows:

- `Call Company Research`
- `Call CV Translation Cache`
- `Call Analysis Scoring`
- `Call CV Tailoring Planner`

If your n8n instance assigned different workflow IDs on import, reconnect them before activation.

## Step 8: Activate the Runtime Workflows

Activate:

- `main-workflow.json`
- `utility-get-profiles.json`

Activate `utility-extract-profile.json` too if you want to create or update profiles through the webhook instead of manual execution in the editor.

## Step 9: Test `GET /profiles`

The profile-list helper endpoint is:

- `GET /profiles`

It returns all rows from `job_application_assistant.profiles` ordered by `full_name`.

## Step 10: Send a Test Runtime Request

The main runtime entry point is:

- `POST /job-application`

It expects:

- `profile_id`
- `chatInput`

Example request:

```bash
curl -X POST "http://YOUR_N8N_HOST/webhook/job-application" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "chatInput": "Paste the full job posting text here"
  }'
```

## Step 11: Validate the Response

A successful response is JSON with:

- `output`
- `cv_diff`
- `cv_markdown`
- `avatar_url`

Expected behavior by threshold:

- `pass`: application package
- `caution`: application package with caution framing
- `fail`: gap analysis, usually with empty CV artifacts

Thresholds are not assigned from raw score bands. The scoring workflow sums the five dimension scores for display, but assigns `pass`, `caution`, or `fail` from weighted dimension ratios plus hard/soft minimum checks.

## Step 12: Verify Translation Cache

Run one test where:

- CV language matches posting language

and another where:

- CV language differs from posting language

After a cross-language run, check cache state:

```sql
SELECT key, updated_at
FROM job_application_assistant.candidate_context
WHERE profile_id = 1
  AND key LIKE 'translated_cv_text_%'
ORDER BY updated_at DESC;
```

You should see paired keys such as:

- `translated_cv_text_en`
- `translated_cv_text_en_source_hash`

The workflow only reuses the cached translation when the stored source hash matches current `cv_hash`.

## Step 13: Verify Application Logging

After a successful runtime request, check:

```sql
SELECT profile_id, company, role_title, score, threshold, date_applied, status
FROM job_application_assistant.job_applications
ORDER BY date_applied DESC;
```

Remember:

- the webhook response can still succeed if logging fails
- the insert node is configured to continue on error

## Updating an Existing Profile

To update an existing profile, call `POST /profile-setup` with `profile_id` and only the fields you want to change.

Example:

```bash
curl -X POST "http://YOUR_N8N_HOST/webhook/profile-setup" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": 1,
    "cv_text": "Updated plain-text CV"
  }'
```

Important behavior:

- updating only profile metadata may skip LLM recomputation
- updating `cv_text` recomputes `cv_hash` and `cv_language`
- if `cv_text` changed, cached translated CV entries for `de` and `en` are deleted
- updating `market_research` triggers derived key refresh
- updating `career_target` stores the new source text, but does not by itself rerun the derived profile extraction in the current workflow

## Troubleshooting

### `profile_id` errors on runtime requests

Check that:

- `profile_id` is present in the request body
- it is a positive integer
- the profile exists in `job_application_assistant.profiles`

### Response works but nothing is stored in `job_applications`

Likely causes:

- DB credential issue
- Postgres permission issue
- connectivity or insert-time error

### Normal job posting gets rejected immediately

Check the `Guardrails` branch and retest with:

- only the raw job posting
- no extra instructions
- no copied page chrome

### Cached translations are not reused

Check whether both of these exist and match for the same `profile_id`:

- `translated_cv_text_<language>`
- `translated_cv_text_<language>_source_hash`

Also verify `cv_hash` changed or did not change as expected.

### Main workflow errors after import

Most often this means one or more `Execute Workflow` nodes still point to missing or wrong workflow IDs. Rebind the imported sub-workflows and test again.

## Maintenance

Update CV:

- call `POST /profile-setup` with `profile_id` and new `cv_text`

Update guides:

- call `POST /profile-setup` with `profile_id` and updated `guide_text_de` and/or `guide_text_en`

Update market assumptions:

- call `POST /profile-setup` with `profile_id` and updated `market_research`

Update role strategy text:

- call `POST /profile-setup` with `profile_id` and updated `career_target`
- include `cv_text` or `market_research` in the same update if you need `candidate_profile` and `role_type_scores` regenerated immediately

Inspect candidate context:

```sql
SELECT profile_id, key, updated_at
FROM job_application_assistant.candidate_context
ORDER BY profile_id, key;
```

Inspect logged applications:

```sql
SELECT profile_id, company, role_title, score, threshold, date_applied, status
FROM job_application_assistant.job_applications
ORDER BY date_applied DESC;
```
