# Setup Guide

This guide matches the current exported workflows:

- `utility-extract-profile.json`
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
2. `company-research.json`
3. `cv-translation-cache.json`
4. `analysis-scoring.json`
5. `cv-tailoring-planner.json`
6. `main-workflow.json`

Recommended order:

- utility first
- sub-workflows second
- main last

Reason:

- the utility workflow creates the tables and seeds `candidate_context`
- the main workflow references the runtime sub-workflows by `Execute Workflow`

After import, re-map credentials where needed.

## Step 2: Check Credentials

You should see these credential types in use:

- Postgres
- Anthropic API
- SerpAPI

Verify all required nodes show valid credentials before execution.

## Step 3: Create Database Tables

Open `utility-extract-profile.json` and run:

- `CREATE TABLES`

This creates:

- `candidate_context`
- `job_applications`

The query uses `CREATE TABLE IF NOT EXISTS`, so re-running is safe.

Current schema:

`candidate_context`

- `key VARCHAR(100) PRIMARY KEY`
- `value TEXT NOT NULL`
- `updated_at TIMESTAMP DEFAULT NOW()`

`job_applications`

- `id SERIAL PRIMARY KEY`
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

## Step 4: Fill `Set Up Workflow Context`

Open `utility-extract-profile.json` and edit `Set Up Workflow Context`.

The workflow expects these five manual inputs:

- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`

What they do:

- `cv_text`: base CV in plain text
- `guide_text_de`: German cover-letter guide
- `guide_text_en`: English cover-letter guide
- `market_research`: market context for profile and role derivation
- `career_target`: target-role strategy and constraints

## Step 5: Execute the Utility Workflow

Run the workflow from:

- `When clicking 'Execute workflow'`

It will:

1. compute `cv_hash`
2. detect the base CV language
3. extract `candidate_profile`
4. extract `role_type_scores`
5. upsert everything into `candidate_context`

## Step 6: Verify Stored Keys

After the utility workflow finishes, verify that `candidate_context` contains at least:

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
FROM candidate_context
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

## Step 8: Activate the Main Workflow

Activate `main-workflow.json` after:

- credentials are valid
- sub-workflow references are correct
- `candidate_context` has been populated
- the database is reachable

## Step 9: Send a Test Request

The main runtime entry point is:

- `POST /job-application`

It expects the job posting in `body.chatInput`.

Example request:

```bash
curl -X POST "http://YOUR_N8N_HOST/webhook/job-application" \
  -H "Content-Type: application/json" \
  -d '{
    "chatInput": "Paste the full job posting text here"
  }'
```

## Step 10: Validate the Response

A successful response is JSON with:

- `output`
- `cv_diff`
- `cv_markdown`

Expected behavior by threshold:

- `pass` (`>= 55`): application package
- `caution` (`45-54`): application package with caution framing
- `fail` (`< 45`): gap analysis, usually with empty CV artifacts

## Step 11: Verify Translation Cache

Run one test where:

- CV language matches posting language

and another where:

- CV language differs from posting language

After a cross-language run, check cache state:

```sql
SELECT key, updated_at
FROM candidate_context
WHERE key LIKE 'translated_cv_text_%'
ORDER BY updated_at DESC;
```

You should see paired keys such as:

- `translated_cv_text_en`
- `translated_cv_text_en_source_hash`

The workflow only reuses the cached translation when the stored source hash matches current `cv_hash`.

## Step 12: Verify Application Logging

After a successful runtime request, check:

```sql
SELECT company, role_title, score, threshold, date_applied, status
FROM job_applications
ORDER BY date_applied DESC;
```

Remember:

- the webhook response can still succeed if logging fails
- the insert node is configured to continue on error

## Troubleshooting

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

Check whether both of these exist and match:

- `translated_cv_text_<language>`
- `translated_cv_text_<language>_source_hash`

Also verify `cv_hash` changed or did not change as expected.

### Wrong guide language is used

Guide selection is based on the job-posting language, not CV language.

Check:

- `job_post_language.language`
- `guide_text_de`
- `guide_text_en`

### Main workflow errors after import

Most often this means one or more `Execute Workflow` nodes still point to missing or wrong workflow IDs. Rebind the imported sub-workflows and test again.

## Maintenance

Update CV:

- edit `cv_text`
- re-run the utility workflow

Update guides:

- edit `guide_text_de` and/or `guide_text_en`
- re-run the utility workflow

Update market assumptions or role strategy:

- edit `market_research` or `career_target`
- re-run the utility workflow

Inspect candidate context:

```sql
SELECT key, updated_at
FROM candidate_context
ORDER BY key;
```

Inspect logged applications:

```sql
SELECT company, role_title, score, threshold, date_applied, status
FROM job_applications
ORDER BY date_applied DESC;
```
