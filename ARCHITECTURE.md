# CV Assistant — Architecture

## Stack

| Layer | Technology |
|---|---|
| UI | NiceGUI 3.x (pure-Python, server-rendered, WebSocket-based) |
| API | FastAPI (async), mounted inside NiceGUI's uvicorn process |
| LLM | Anthropic SDK (Haiku/Sonnet) + OpenAI SDK (GPT-4.1) |
| DB | PostgreSQL via asyncpg — schema `job_application_assistant` in DB `projects` |
| Runtime | Python 3.12 + uv for dependency management |
| Deploy | Docker Compose + Caddy reverse proxy on Hetzner |

## Process model

One uvicorn process on port 8000. NiceGUI runs inside it. No separate frontend server.

```
Caddy (:443) → uvicorn (:8000)
                  ├── FastAPI routes  /api/*
                  └── NiceGUI pages  /  (WebSocket UI)
```

## Module layout

```
/opt/cv-assistant/
├── backend/
│   ├── main.py                 ← FastAPI app + NiceGUI mount + uvicorn entry
│   ├── config.py               ← pydantic-settings (reads .env)
│   ├── db.py                   ← asyncpg pool factory + get_conn() context manager
│   ├── llm.py                  ← Unified LLM wrapper (Anthropic + OpenAI) with DB logging
│   │
│   ├── migrations/
│   │   └── 001_llm_logs.sql    ← CREATE TABLE llm_logs (run once)
│   │
│   ├── deterministic/          ← Pure Python — no LLM, no DB
│   │   ├── language.py         ← detect_language(text) → 'de' | 'en'
│   │   └── cv_utils.py         ← normalize_cv(), hash_cv()
│   │
│   ├── prompts/
│   │   ├── loader.py           ← load_prompt(name, version='v1') → str
│   │   └── v1/                 ← All system prompts as .txt files (versioned in git)
│   │       ├── market_research_extractor.txt
│   │       ├── binary_classifier.txt
│   │       ├── core_skills_extractor.txt
│   │       └── candidate_profile.txt
│   │
│   ├── models/
│   │   └── profile.py          ← Pydantic models for profile extraction LLM outputs
│   │
│   ├── pipeline/               ← One module per n8n sub-workflow
│   │   └── profile_extraction.py  ← Full profile setup pipeline (CREATE + UPDATE)
│   │
│   └── ui/
│       ├── components/
│       │   ├── avatar.py           ← Server-side image resize (Pillow)
│       │   └── profile_modal.py    ← NiceGUI profile create/edit dialog
│       └── pages/
│           └── main_page.py        ← Root page: profile selector + posting input + result panel
│
├── src/                        ← OLD JS frontend — NOT deleted until parity reached
├── index.html                  ← OLD static entry point
├── pyproject.toml              ← uv project config
└── .env                        ← API keys + DB credentials (gitignored)
```

## LLM call pattern

Every LLM call goes through `llm.py`. No direct SDK calls elsewhere.

```python
# Structured output (validates with Pydantic, retries on failure)
result = await llm.call_structured(
    conn,
    model="claude-haiku-4-5-20251001",
    system=load_prompt("market_research_extractor"),
    user=f"<market_research>\n{text}\n</market_research>",
    response_model=MarketResearchOutput,
    node_name="market_research_extractor",
    profile_id=42,
)

# Raw text (for prompts with built-in schema, or non-structured outputs)
text = await llm.call_raw(conn, model=..., system=..., user=..., node_name=...)
```

All calls log to `job_application_assistant.llm_logs`: model, node_name, profile_id, tokens, latency, cost.

## Model assignments (hard constraint)

| Pipeline node | Model |
|---|---|
| Analyzer / Classifier (analysis scoring) | gpt-4.1 |
| Market Research Extractor | claude-haiku-4-5-20251001 |
| Binary Classifier (technologies) | claude-haiku-4-5-20251001 |
| Core Skills Extractor | claude-haiku-4-5-20251001 |
| Candidate Profile Extractor | claude-sonnet-4-6 |
| CV Tailoring Generator / Rewriter | claude-haiku-4-5-20251001 |
| Anschreiben | claude-sonnet-4-6 |
| Company Extractor | claude-haiku-4-5-20251001 |
| CV Translator | claude-sonnet-4-6 |
| Gap Analysis | claude-sonnet-4-6 |
| Guardrails | claude-haiku-4-5-20251001 |

## Prompt versioning

Prompts live in `backend/prompts/v1/*.txt`. To change a prompt: create a `v2/` copy and update the `load_prompt()` call at the pipeline call site. Old version stays in git history. The version directory is the "prompt version" label.

## Hard constraints (non-negotiable)

1. No candidate-specific or profile-specific content in any prompt file
2. All arithmetic, counting, scoring math, string matching → Python code (`deterministic/`)
3. Every LLM call goes through `llm.py` (no direct SDK calls)
4. DB schema unchanged — no destructive migrations
5. Old JS frontend not deleted until NiceGUI reaches parity
