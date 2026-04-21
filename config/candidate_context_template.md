# Candidate Context Template

This document reflects the keys used by the current exported workflows.

The `candidate_context` table now serves three roles:

1. manual source-of-truth storage
2. generated candidate-profile storage
3. runtime CV-translation caching

## Key Groups

### Manual source keys
Maintained in `Set Up Workflow Context` inside `utility-extract-profile.json`.

- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `career_target`

### Utility-generated keys
Created or refreshed when the utility workflow runs.

- `candidate_profile`
- `role_type_scores`
- `cv_language`
- `cv_hash`

### Runtime cache keys
Created by `cv-translation-cache.json` only when a cross-language run happens.

- `translated_cv_text_<language>`
- `translated_cv_text_<language>_source_hash`

## Manual Source Keys

### `cv_text`
Base CV stored as plain text.

Used by:

- utility profile extraction
- runtime CV resolution
- translation workflow

Update it when the real source CV changes.

### `guide_text_de`
German-language cover-letter guide used when the posting language is not English.

### `guide_text_en`
English-language cover-letter guide used when the posting language is English.

### `market_research`
Market context used by the utility workflow to derive:

- candidate-relevant technologies
- commute target cities
- role categories and bridge quality

### `career_target`
Human-authored target-role strategy used during profile extraction.

## Utility-Generated Keys

### `candidate_profile`
Structured JSON object stored as a JSON string.

Current fields:

- `name`
- `core_skills`
- `secondary_tools`
- `skill_gaps`
- `home_location`
- `commute_options`
- `target_format`

Notes:

- `skill_gaps` is stored as a string field inside `candidate_profile`
- the extractor restricts gap qualifiers to:
  - `no hands-on experience`
  - `no hands-on experience (has used [X] in the same domain)`

### `role_type_scores`
JSON object stored as a JSON string.

Important behavior:

- exactly one role key must have score `12`
- contract-type words are stripped from role labels before storage
- it always includes:
  - `Other adjacent IT`
  - `Unrelated (sales, legal, manual, etc.)`

The main runtime parses this key back into an object and uses it to compute `role_fit`.

### `cv_language`
Detected language metadata for the base CV, stored as JSON.

Expected structure:

```json
{
  "language": "de",
  "confidence": 0.91,
  "scores": {
    "german": 42,
    "english": 8
  }
}
```

### `cv_hash`
SHA-256 hash of the current `cv_text`.

Purpose:

- lets the translation workflow detect stale cached translations
- ties each `translated_cv_text_<language>` entry to the exact base CV version it came from

## Runtime Cache Keys

### `translated_cv_text_<language>`
Translated CV text for a target language such as:

- `translated_cv_text_en`
- `translated_cv_text_de`

### `translated_cv_text_<language>_source_hash`
The `cv_hash` value that was current when the translation was created.

Runtime resolution rule:

1. if CV language matches posting language, use `cv_text`
2. otherwise read translation cache state
3. reuse cached translation only if:
   - translated text exists, and
   - its `_source_hash` matches current `cv_hash`
4. otherwise translate again and overwrite both cache keys

## Minimal Healthy State

After running the utility workflow, `candidate_context` should contain at least:

- `candidate_profile`
- `career_target`
- `cv_hash`
- `cv_language`
- `cv_text`
- `guide_text_de`
- `guide_text_en`
- `market_research`
- `role_type_scores`

Later, translation cache keys may appear automatically.

## Verification Queries

Show all keys:

```sql
SELECT key, updated_at
FROM candidate_context
ORDER BY key;
```

Show fixed bootstrap keys:

```sql
SELECT key, updated_at
FROM candidate_context
WHERE key IN (
  'candidate_profile',
  'career_target',
  'cv_hash',
  'cv_language',
  'cv_text',
  'guide_text_de',
  'guide_text_en',
  'market_research',
  'role_type_scores'
)
ORDER BY key;
```

Show translation cache state:

```sql
SELECT key, updated_at
FROM candidate_context
WHERE key LIKE 'translated_cv_text_%'
ORDER BY updated_at DESC;
```

## Update Rules

After changing `cv_text`:

- re-run the utility workflow
- old translations become stale automatically because `cv_hash` changes

After changing `guide_text_de` or `guide_text_en`:

- re-run the utility workflow

After changing `market_research` or `career_target`:

- re-run the utility workflow so `candidate_profile` and `role_type_scores` stay aligned

Avoid manually editing generated keys unless you are intentionally debugging the pipeline.
