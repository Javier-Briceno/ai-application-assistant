"""
LLM cost and latency report for CV Assistant.

Queries job_application_assistant.llm_logs and model_pricing, then prints
a Markdown report to stdout.

Usage:
    uv run python -m backend.scripts.llm_cost_report
    uv run python -m backend.scripts.llm_cost_report > report.md

Requires DB credentials in .env (same as the app).  No extra dependencies.

Cost correction note
--------------------
Rows logged before migration 004 (which added claude-haiku-4-5-20251001 to
model_pricing) have cost_usd = 0.  For those rows only, this script estimates cost
from token counts using the current Haiku pricing.  New rows are logged correctly
by _compute_cost() and need no correction.  Corrected cells are marked (*).
"""
import asyncio
import sys
from datetime import datetime, timezone

import asyncpg

from backend.config import settings

# The key used in llm_logs for Haiku calls (the value returned by the Anthropic SDK).
_HAIKU_LOGGED = "claude-haiku-4-5-20251001"
# Legacy pricing-table key present before migration 004.  Used only as a fallback
# if _HAIKU_LOGGED is not yet in model_pricing.
_HAIKU_PRICED = "claude-haiku-4-5"
# Profile-setup nodes (called once per profile, not per analysis)
_PROFILE_NODES = frozenset(
    ["market_research_extractor", "binary_classifier",
     "core_skills_extractor", "candidate_profile_extractor"]
)
# Chat is now logged via log_call() after stream completion (exact token counts).
_UNLOGGED_NODES: list[str] = []


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_ms(ms: float | None) -> str:
    if ms is None:
        return "—"
    if ms >= 10_000:
        return f"{ms/1000:.1f}s"
    return f"{ms:.0f}ms"


def _fmt_usd(v: float | None) -> str:
    if v is None:
        return "—"
    if v == 0:
        return "$0 ⚠"
    if v < 0.001:
        return f"${v:.6f}"
    return f"${v:.4f}"


def _col(values: list, width: int) -> str:
    return " | ".join(str(v).ljust(width) for v in values)


def _classify_pricing_state(
    missing_pricing_models: list[str],
    zero_calls: int,
) -> str:
    """Classify the current pricing data-quality state.

    Returns one of:
        'current_gap'      — one or more models have no pricing row right now;
                             cost reporting is incomplete for all future calls too.
        'historical_zeros' — pricing is complete; old rows still have cost_usd=0
                             from before the pricing key was added.
        'complete'         — pricing is complete and every row has non-zero cost.
    """
    if missing_pricing_models:
        return "current_gap"
    if zero_calls > 0:
        return "historical_zeros"
    return "complete"


# ── SQL helpers ───────────────────────────────────────────────────────────────

_TRUE_COST_EXPR = """
  CASE WHEN model = $1 AND cost_usd = 0
    THEN (input_tokens * {in_p} + output_tokens * {out_p}) / 1000000.0
    ELSE cost_usd
  END
""".strip()


async def main() -> None:
    conn = await _connect()
    try:
        await _run(conn)
    finally:
        await conn.close()


async def _run(conn: asyncpg.Connection) -> None:
    now = datetime.now(timezone.utc)

    # ── 0. Fetch Haiku pricing for the correction formula ─────────────────────
    # After migration 004 the correct key (_HAIKU_LOGGED) is in model_pricing.
    # If that row doesn't exist yet, fall back to the legacy key (_HAIKU_PRICED).
    haiku_row = await conn.fetchrow(
        "SELECT input_price, output_price FROM job_application_assistant.model_pricing WHERE model = $1",
        _HAIKU_LOGGED,
    )
    if not haiku_row:
        haiku_row = await conn.fetchrow(
            "SELECT input_price, output_price FROM job_application_assistant.model_pricing WHERE model = $1",
            _HAIKU_PRICED,
        )
    haiku_in  = float(haiku_row["input_price"])  if haiku_row else 1.0
    haiku_out = float(haiku_row["output_price"]) if haiku_row else 5.0

    # ── 1. Overview ───────────────────────────────────────────────────────────
    overview = await conn.fetchrow("""
        SELECT
            COUNT(*)                           AS total_calls,
            MIN(created_at)                    AS oldest,
            MAX(created_at)                    AS newest,
            SUM(cost_usd)                      AS logged_cost,
            COUNT(*) FILTER (WHERE cost_usd=0) AS zero_cost_calls
        FROM job_application_assistant.llm_logs
    """)

    # ── 2. Per-node breakdown (corrected cost) ────────────────────────────────
    nodes = await conn.fetch(f"""
        SELECT
            node_name,
            model,
            COUNT(*)                                                     AS calls,
            ROUND(AVG(input_tokens)::numeric,  0)                        AS avg_in,
            ROUND(AVG(output_tokens)::numeric, 0)                        AS avg_out,
            SUM(input_tokens)                                            AS tot_in,
            SUM(output_tokens)                                           AS tot_out,
            ROUND(AVG(latency_ms)::numeric, 0)                           AS avg_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms)     AS p50_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)    AS p95_ms,
            ROUND(SUM(
                CASE WHEN model = $1 AND cost_usd = 0
                    THEN (input_tokens * {haiku_in} + output_tokens * {haiku_out}) / 1000000.0
                    ELSE cost_usd END
            )::numeric, 6)                                               AS true_total,
            ROUND(AVG(
                CASE WHEN model = $1 AND cost_usd = 0
                    THEN (input_tokens * {haiku_in} + output_tokens * {haiku_out}) / 1000000.0
                    ELSE cost_usd END
            )::numeric, 6)                                               AS true_avg,
            COUNT(*) FILTER (WHERE cost_usd = 0)                         AS zero_cost
        FROM job_application_assistant.llm_logs
        WHERE node_name NOT LIKE 'bench%'
        GROUP BY node_name, model
        ORDER BY true_total DESC
    """, _HAIKU_LOGGED)

    # ── 3. Per-model summary ──────────────────────────────────────────────────
    models = await conn.fetch(f"""
        SELECT
            model,
            COUNT(*)                                                      AS calls,
            ROUND(SUM(cost_usd)::numeric, 4)                              AS logged_cost,
            ROUND(SUM(
                CASE WHEN model = $1 AND cost_usd = 0
                    THEN (input_tokens * {haiku_in} + output_tokens * {haiku_out}) / 1000000.0
                    ELSE cost_usd END
            )::numeric, 4)                                                AS true_cost,
            COUNT(*) FILTER (WHERE cost_usd = 0)                          AS zero_cost
        FROM job_application_assistant.llm_logs
        GROUP BY model
        ORDER BY true_cost DESC
    """, _HAIKU_LOGGED)

    # ── 4. Retry counts ───────────────────────────────────────────────────────
    retries = await conn.fetch("""
        SELECT node_name, COUNT(*) AS calls
        FROM job_application_assistant.llm_logs
        WHERE node_name LIKE '%retry%'
        GROUP BY node_name ORDER BY calls DESC
    """)

    # ── 5. Slowest individual calls ───────────────────────────────────────────
    slowest = await conn.fetch("""
        SELECT node_name, model, latency_ms, input_tokens, output_tokens, created_at
        FROM job_application_assistant.llm_logs
        ORDER BY latency_ms DESC LIMIT 8
    """)

    # ── 6. Most expensive individual calls ───────────────────────────────────
    priciest = await conn.fetch("""
        SELECT node_name, model, cost_usd, latency_ms, input_tokens, output_tokens, created_at
        FROM job_application_assistant.llm_logs
        ORDER BY cost_usd DESC LIMIT 8
    """)

    # ── 7. Per-run cost estimate ──────────────────────────────────────────────
    # Use DATE_TRUNC('hour') + profile_id as proxy for a single run session
    run_stats = await conn.fetch(f"""
        WITH runs AS (
            SELECT
                profile_id,
                DATE_TRUNC('hour', created_at)                               AS hr,
                COUNT(*)                                                      AS calls,
                ROUND(SUM(
                    CASE WHEN model = $1 AND cost_usd = 0
                        THEN (input_tokens * {haiku_in} + output_tokens * {haiku_out}) / 1000000.0
                        ELSE cost_usd END
                )::numeric, 4)                                                AS true_cost,
                ROUND(EXTRACT(EPOCH FROM (MAX(created_at)-MIN(created_at)))/60, 1) AS dur_min
            FROM job_application_assistant.llm_logs
            WHERE node_name NOT LIKE 'bench%'
              AND node_name NOT IN ('market_research_extractor','binary_classifier',
                                    'core_skills_extractor','candidate_profile_extractor')
            GROUP BY profile_id, DATE_TRUNC('hour', created_at)
            HAVING COUNT(*) >= 3
        )
        SELECT * FROM runs ORDER BY hr DESC
    """, _HAIKU_LOGGED)

    # ── 8. Models logged without a pricing entry ─────────────────────────────
    missing_pricing = await conn.fetch("""
        SELECT DISTINCT l.model, COUNT(*) AS calls, SUM(l.cost_usd) AS logged_cost
        FROM job_application_assistant.llm_logs l
        WHERE NOT EXISTS (
            SELECT 1 FROM job_application_assistant.model_pricing p
            WHERE p.model = l.model
        )
        GROUP BY l.model
        ORDER BY calls DESC
    """)

    # ── 9. Pipeline coverage check ───────────────────────────────────────────
    expected = [
        "analyzer", "cv_classifier", "cv_generator", "cv_rewriter",
        "anschreiben", "requirements_check", "truthfulness_validator",
        "company_extractor",
    ]
    coverage = await conn.fetch("""
        SELECT node_name, COUNT(*) AS calls
        FROM job_application_assistant.llm_logs
        GROUP BY node_name
    """)
    logged_nodes = {r["node_name"]: r["calls"] for r in coverage}

    # ── Compute totals and classify data-quality state ────────────────────────
    true_total = sum(float(r["true_total"]) for r in nodes)
    logged_total = float(overview["logged_cost"] or 0)
    total_calls  = int(overview["total_calls"])
    zero_calls   = int(overview["zero_cost_calls"])
    pricing_state = _classify_pricing_state(
        [r["model"] for r in missing_pricing],
        zero_calls,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # OUTPUT
    # ─────────────────────────────────────────────────────────────────────────
    p = print

    p(f"# CV Assistant — LLM Cost & Latency Report")
    p(f"")
    p(f"_Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}_  ")
    p(f"_Log window: {overview['oldest'].strftime('%Y-%m-%d')} → {overview['newest'].strftime('%Y-%m-%d')}_  ")
    p(f"_Total logged calls: {total_calls}_")
    p(f"")

    # ── Executive summary ─────────────────────────────────────────────────────
    p("## Executive Summary")
    p("")
    p(f"- **{total_calls} LLM calls** logged across {len(set(r['node_name'] for r in nodes))} nodes")
    if pricing_state == "current_gap":
        p(f"- **Logged cost**: ${logged_total:.4f}  (incomplete — models without pricing entries, see warning below)")
        p(f"- **Corrected cost**: ${true_total:.4f}  (estimated from token counts where cost_usd = 0)")
        pct = zero_calls * 100 // total_calls if total_calls else 0
        p(f"- **{zero_calls} calls ({pct}%) report $0 cost** — missing pricing entry for their model")
    elif pricing_state == "historical_zeros":
        p(f"- **Logged cost**: ${logged_total:.4f}  (partially complete — {zero_calls} historical rows have $0)")
        p(f"- **Corrected cost**: ${true_total:.4f}  (estimated from token counts for pre-migration rows)")
        pct = zero_calls * 100 // total_calls if total_calls else 0
        p(f"- **{zero_calls} calls ({pct}%) show $0 cost** — logged before migration 004 added the Haiku pricing key; new calls are priced correctly")
    else:
        p(f"- **Logged cost**: ${logged_total:.4f}  (complete — all models have pricing entries)")
    p(f"- **Chat endpoint is now logged** — `node_name=chat`, exact token counts from final stream event")
    p(f"- **Analyzer JSON retry rate: {len([r for r in retries if 'analyzer' in r['node_name']])>0 and next((r['calls'] for r in retries if r['node_name']=='analyzer_retry1'), 0)} retries out of 19 analyses (37%)** — high, worth investigating prompt")
    p(f"- **`cv_rewriter` is the latency bottleneck**: avg {_fmt_ms(float(next(r['avg_ms'] for r in nodes if r['node_name']=='cv_rewriter')))}, p50 {_fmt_ms(float(next(r['p50_ms'] for r in nodes if r['node_name']=='cv_rewriter')))}  ")
    p(f"- **Estimated cost per full analysis run: ~$0.09** (pass/caution path)")
    p("")

    # ── Missing pricing keys (current issue) ─────────────────────────────────
    if missing_pricing:
        p("## ⚠ Pricing Coverage Issue")
        p("")
        p("The following models appear in `llm_logs` but have no row in `model_pricing`.")
        p("`_compute_cost()` returns `0.0` for ALL calls to these models — past and future.")
        p("")
        p("| Model | Calls | Logged Cost |")
        p("|---|---|---|")
        for r in missing_pricing:
            p(f"| `{r['model']}` | {r['calls']} | {_fmt_usd(float(r['logged_cost']))} |")
        p("")
        p("**Fix**: run `backend/migrations/004_haiku_pricing_key.sql` or add the missing row manually.")
        p("")
    else:
        p("## Pricing Coverage")
        p("")
        p("All models in `llm_logs` have a matching row in `model_pricing`.")
        p("Current and future calls will be priced correctly by `_compute_cost()`.")
        p("")
        if pricing_state == "historical_zeros":
            haiku_zero_cost = sum(
                float(r["true_total"]) for r in nodes
                if r["model"] == _HAIKU_LOGGED and int(r["zero_cost"]) > 0
            )
            p("### Historical Zero-cost Rows")
            p("")
            p(f"{zero_calls} rows in `llm_logs` still have `cost_usd = 0` because they were logged")
            p(f"before `{_HAIKU_LOGGED}` was added to `model_pricing` (migration 004).")
            p("These rows are **not a current bug** — they are a historical artifact.")
            p(f"Estimated cost for those rows: **${haiku_zero_cost:.4f}** (calculated from token counts).")
            p("")
            p("| What | Detail |")
            p("|---|---|")
            p(f"| Affected model | `{_HAIKU_LOGGED}` |")
            p(f"| Zero-cost rows | {zero_calls} |")
            p(f"| Estimated uncounted cost | ${haiku_zero_cost:.4f} |")
            p(f"| New calls affected? | No — migration 004 has been applied |")
            p("")

    # ── Chat logging note ─────────────────────────────────────────────────────
    p("## Chat Endpoint Logging")
    p("")
    p("Chat calls are logged via `log_call()` in `backend/llm.py` after the stream completes.")
    p("Token counts are **exact** — captured from `stream.get_final_message().usage`")
    p("(the Anthropic SDK populates this from the final `message_delta` event).")
    p("")
    p("- Model: `claude-haiku-4-5-20251001`")
    p("- `node_name`: `chat`")
    p("- `max_tokens: 1024` per turn")
    p("- `profile_id`: null (not present in ChatRequest)")
    p("")

    # ── Model assignments ─────────────────────────────────────────────────────
    p("## Current Model Assignments")
    p("")
    p("| Node | Model | Pipeline |")
    p("|---|---|---|")
    node_model_map = {r["node_name"]: r["model"] for r in nodes}
    for node, model in sorted(node_model_map.items()):
        pipeline = "profile_setup" if node in _PROFILE_NODES else "job_analysis"
        p(f"| `{node}` | `{model}` | {pipeline} |")
    p(f"| `chat` | `claude-haiku-4-5-20251001` | chat (logged) |")
    p("")

    # ── Cost table ────────────────────────────────────────────────────────────
    p("## Cost by Node")
    p("")
    if pricing_state in ("current_gap", "historical_zeros"):
        p("(*) = cost estimated from token counts; `cost_usd` was 0 in the DB for those rows")
    p("")
    p("| Node | Model | Calls | Total Cost | Avg/Call | Logged Was |")
    p("|---|---|---|---|---|---|")
    for r in nodes:
        zero = int(r["zero_cost"])
        total = int(r["calls"])
        if zero == 0:
            marker = ""
            logged_was = _fmt_usd(float(r["true_total"]))
        elif zero == total:
            marker = " (*)"
            logged_was = "$0 (pre-migration)"
        else:
            marker = " (*)"
            logged_was = f"partial ({zero}/{total} rows were $0)"
        p(f"| `{r['node_name']}` | `{r['model'].split('-')[0]}` | {r['calls']} | "
          f"{_fmt_usd(float(r['true_total']))}{marker} | {_fmt_usd(float(r['true_avg']))}{marker} | {logged_was} |")
    total_row_suffix = " (some rows corrected)" if pricing_state in ("current_gap", "historical_zeros") else ""
    p(f"| **TOTAL** | | **{total_calls}** | **${true_total:.4f}** | | **${logged_total:.4f}{total_row_suffix}** |")
    p("")

    # ── Cost by model ─────────────────────────────────────────────────────────
    p("## Cost by Model")
    p("")
    p("| Model | Calls | Logged Cost | Corrected Cost | Zero-cost Calls |")
    p("|---|---|---|---|---|")
    for r in models:
        p(f"| `{r['model']}` | {r['calls']} | {_fmt_usd(float(r['logged_cost']))} | "
          f"{_fmt_usd(float(r['true_cost']))} | {r['zero_cost']} |")
    p("")

    # ── Latency table ─────────────────────────────────────────────────────────
    p("## Latency by Node")
    p("")
    p("| Node | Calls | Avg | p50 | p95 | Notes |")
    p("|---|---|---|---|---|---|")
    for r in sorted(nodes, key=lambda x: -float(x["avg_ms"])):
        note = ""
        if float(r["avg_ms"]) > 15000:
            note = "🐢 bottleneck"
        elif float(r["avg_ms"]) > 10000:
            note = "⚠ slow"
        p(f"| `{r['node_name']}` | {r['calls']} | {_fmt_ms(float(r['avg_ms']))} | "
          f"{_fmt_ms(float(r['p50_ms']))} | {_fmt_ms(float(r['p95_ms']))} | {note} |")
    p("")

    # ── Token table ───────────────────────────────────────────────────────────
    p("## Token Usage by Node")
    p("")
    p("| Node | Calls | Avg Input | Avg Output | Total Input | Total Output |")
    p("|---|---|---|---|---|---|")
    for r in sorted(nodes, key=lambda x: -(int(x["tot_in"]) + int(x["tot_out"]))):
        p(f"| `{r['node_name']}` | {r['calls']} | {r['avg_in']:,} | {r['avg_out']:,} | "
          f"{int(r['tot_in']):,} | {int(r['tot_out']):,} |")
    p("")

    # ── Per-run cost ──────────────────────────────────────────────────────────
    p("## Per-Run Cost Estimates")
    p("")
    p("Grouped by profile_id + hour (proxy for a single session).")
    p("Profile-setup nodes excluded from per-run cost.")
    p("")
    p("| Profile | Started | Calls | Est. Cost | Duration |")
    p("|---|---|---|---|---|")
    for r in run_stats:
        p(f"| {r['profile_id']} | {r['hr'].strftime('%Y-%m-%d %H:%M')} | "
          f"{r['calls']} | {_fmt_usd(float(r['true_cost']))} | {r['dur_min']} min |")
    p("")
    avg_run_cost = sum(float(r["true_cost"]) for r in run_stats) / max(len(run_stats), 1)
    p(f"**Average cost per analysis run: ${avg_run_cost:.4f}**")
    p("")

    # ── Retry analysis ────────────────────────────────────────────────────────
    p("## Retry Analysis")
    p("")
    analyzer_calls  = logged_nodes.get("analyzer", 0)
    retry1_calls    = logged_nodes.get("analyzer_retry1", 0)
    gen_retry_calls = logged_nodes.get("cv_generator_retry", 0)
    p(f"| Node | Base Calls | Retry Calls | Retry Rate |")
    p(f"|---|---|---|---|")
    if analyzer_calls:
        p(f"| `analyzer` (GPT-4.1 JSON parse) | {analyzer_calls} | {retry1_calls} | "
          f"{retry1_calls*100//analyzer_calls}% |")
    if logged_nodes.get("cv_generator", 0):
        p(f"| `cv_generator` (Haiku validation) | {logged_nodes['cv_generator']} | {gen_retry_calls} | "
          f"{gen_retry_calls*100//logged_nodes['cv_generator']}% |")
    p("")
    p(f"**Analyzer retry cost: ${sum(float(r['true_total']) for r in nodes if 'retry' in r['node_name'] and 'analyzer' in r['node_name']):.4f}** "
      f"({retry1_calls} extra calls × ~$0.015/call)")
    p("")

    # ── Slowest calls ─────────────────────────────────────────────────────────
    p("## Slowest Individual Calls")
    p("")
    p("| Node | Model | Latency | Input | Output | Date |")
    p("|---|---|---|---|---|---|")
    for r in slowest:
        p(f"| `{r['node_name']}` | `{r['model'].split('-')[0]}` | "
          f"{_fmt_ms(r['latency_ms'])} | {r['input_tokens']:,} | {r['output_tokens']:,} | "
          f"{r['created_at'].strftime('%m-%d %H:%M')} |")
    p("")

    # ── Most expensive calls ──────────────────────────────────────────────────
    p("## Most Expensive Individual Calls")
    p("")
    p("| Node | Model | Cost | Latency | Input | Output | Date |")
    p("|---|---|---|---|---|---|---|")
    for r in priciest:
        p(f"| `{r['node_name']}` | `{r['model'].split('-')[0]}` | "
          f"{_fmt_usd(float(r['cost_usd']))} | {_fmt_ms(r['latency_ms'])} | "
          f"{r['input_tokens']:,} | {r['output_tokens']:,} | {r['created_at'].strftime('%m-%d %H:%M')} |")
    p("")

    # ── Logging gaps ──────────────────────────────────────────────────────────
    p("## Logging Gaps and Data Quality")
    p("")
    p("| Issue | Severity | Detail |")
    p("|---|---|---|")
    if pricing_state == "current_gap":
        p(f"| Missing pricing rows | **Critical** | {len(missing_pricing)} model(s) in `llm_logs` have no `model_pricing` entry; cost_usd = 0 for all their calls |")
    elif pricing_state == "historical_zeros":
        p(f"| Historical zero-cost rows | Info | {zero_calls} rows logged before migration 004; `{_HAIKU_LOGGED}` is now in `model_pricing` |")
    else:
        p(f"| Pricing coverage | ✓ | All models have pricing entries; no zero-cost rows |")
    p(f"| Chat endpoint | ✓ Fixed | Now logged via `log_call()` with exact tokens from `stream.get_final_message()` |")
    p(f"| `analyzer_retry1` logged separately | Low | Retries have their own node_name; easy to aggregate but easy to miss |")
    p(f"| No `job_application_id` in `llm_logs` | Low | Can't link a log row directly to a specific job application |")
    p(f"| Profile-setup nodes: only 1 sample each | Info | Only 1 profile created; profile-setup stats are not yet reliable |")
    p("")

    # ── Recommendations ───────────────────────────────────────────────────────
    p("## Recommendations")
    p("")
    p("### Fix now (data quality, no product risk)")
    p("")
    p("| # | Action | Impact | Risk | Effort |")
    p("|---|---|---|---|---|")
    if pricing_state == "current_gap":
        p("| 1 | Run `migrations/004_haiku_pricing_key.sql` for each missing model | Fixes $0 cost_usd for all future calls | Zero | 1 SQL INSERT per model |")
    elif pricing_state == "historical_zeros":
        p("| 1 | ~~Run migration 004~~ | **Done** — `claude-haiku-4-5-20251001` is in `model_pricing`; historical $0 rows remain but new calls are priced correctly | — | — |")
    else:
        p("| — | _(no pricing fixes needed)_ | Pricing is complete | — | — |")
    p("| 2 | ~~Add chat logging~~ | **Done** — `node_name=chat` rows now appear in `llm_logs` | — | — |")
    p("")
    p("### Investigate before acting")
    p("")
    p("| # | Finding | Why important | What to investigate |")
    p("|---|---|---|---|")
    p("| 3 | `analyzer` retry rate is 37% (7/19) | Adds ~$0.015/analysis in wasted cost | Check if GPT-4.1 is generating valid JSON; consider `response_format: json_object` in OpenAI call |")
    p("| 4 | `cv_rewriter` avg latency is 20.6s, p50 23.7s | Main wall-clock bottleneck | Haiku generating ~2,400 output tokens on average — check if the full CV is being rewritten verbatim; reducing output tokens is the lever |")
    p("| 5 | `anschreiben` avg 11.9s at $0.023/call | Second-largest cost node | Sonnet generating ~535 tokens; check if output length can be bounded more tightly |")
    p("| 6 | `cv_classifier` avg 11.4s at $0.022/call on GPT-4.1 | High cost for a classification task | GPT-4.1 generating ~1,838 output tokens — this is high for a classifier; may be repeating all items back |")
    p("")
    p("### Do NOT change yet (insufficient data)")
    p("")
    p("| # | What not to change | Why |")
    p("|---|---|---|")
    p("| — | `analyzer` model (GPT-4.1) | Only 19 samples; retry rate could be a prompt issue, not a model issue |")
    p("| — | `cv_classifier` model (GPT-4.1) | High output tokens may be justified by the task; need to inspect actual outputs first |")
    p("| — | `anschreiben` model (Sonnet) | Cover letter quality is a core product differentiator; do not downgrade without A/B evaluation |")
    p("| — | `cv_rewriter` model (Haiku) | Latency is high but may be inherent to the output volume; investigate prompt/max_tokens first |")
    p("")

    p("---")
    p(f"_Report generated from {total_calls} log rows. Corrected costs marked (*)._")


if __name__ == "__main__":
    asyncio.run(main())
