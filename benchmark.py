"""
LLM Node Benchmarking Script.
Run individual pipeline nodes against test inputs and store results
in job_application_assistant.llm_node_benchmarks.

Usage:
  uv run python benchmark.py --node <node_name> [--model <model>] [--n <runs>]

Available nodes:
  company_extractor
  market_research_extractor
  binary_classifier
  core_skills_extractor
  candidate_profile
  analyzer
  cv_classifier
  cv_generator
  cv_rewriter
  anschreiben
  gap_analysis
  cv_translator

Examples:
  uv run python benchmark.py --node company_extractor
  uv run python benchmark.py --node analyzer --model gpt-4.1 --n 3
"""
import argparse
import asyncio
import json
import time

import asyncpg

from backend.config import settings
from backend.db import close_pool, get_pool

# ── Test fixtures ──────────────────────────────────────────────────────────────

TEST_JOB_POSTING = """
Werkstudent (m/w/d) Controlling – Siemens AG
Standort: Siegen, NRW (Hybrid)

Aufgaben:
- Unterstützung bei der Budgetplanung und dem Soll-Ist-Abgleich
- Erstellung von Finanzberichten und Abweichungsanalysen
- Pflege und Weiterentwicklung unserer Power BI Dashboards

Anforderungen:
- Studium BWL, Wirtschaftswissenschaften
- MS Excel, Power BI Kenntnisse
- 20 Stunden/Woche
"""

TEST_CV = """## Berufserfahrung
Werkstudentin Controlling bei ACME GmbH (2023–heute)
- Budgetplanung und Soll-Ist-Abgleiche mit Excel
- Erstellung von Power BI Dashboards
- Liquiditätsplanung und Kostenstellenübersicht

Minijobberin Café (2021–2022)
- Bestellungen aufnehmen
- Kasse bedienen

## Ausbildung
Bachelor BWL, Universität Siegen (2021–heute)
Schwerpunkt: Controlling, Note: 1.8

## Kenntnisse
Microsoft Excel, Power BI, DAX, Power Query, SAP, Python (Grundkenntnisse)
"""

TEST_MARKET_RESEARCH = """
Section 1: Executive Summary
Werkstudent Controlling-Stellen sind in NRW sehr häufig.

Section 2: Arbeitsmärkte und Städte
Hauptstandorte: Siegen, Cologne, Frankfurt. Siegen: 0 Stunden Fahrtzeit.

Section 3: Berufliche Positionierung
Übergang von Werkstudent zu Junior Controller gut möglich.

Section 4: Rollenanalyse und Häufigkeiten
Werkstudent Controlling: Sehr hohe Häufigkeit, direkte Zielrolle.
Werkstudent Finance: Hohe Häufigkeit, starke Brücke.
Werkstudent Accounting: Moderate Häufigkeit, moderate Brücke.

Section 5: Technologiebedarf (aus Stellenanzeigen)
Microsoft Excel, Power BI, SAP, DAX, Python, SQL, Tableau

Section 6: Technologiebedarf (aus CV-Projekten)
Microsoft Excel, Power BI, DAX, Power Query

Section 7: Weiterbildungsempfehlungen
SAP FI Zertifizierung empfohlen.
"""

TEST_CANDIDATES = ["Microsoft Excel", "Power BI", "DAX", "SAP", "Python", "SQL", "Tableau",
                   "generic business process", "some skill", "Power Query"]

TEST_CANDIDATE_PROFILE = {
    "name": "Sara Mustermann",
    "core_skills": "Budgetplanung, Soll-Ist-Abgleiche, Power BI, Excel",
    "secondary_tools": "SAP, Power Query, DAX",
    "skill_gaps": '[{"technology": "SQL", "qualifier": "no hands-on experience"}]',
    "home_location": "Siegen, NRW",
    "commute_options": "Siegen (~0h, Heimatstadt) | Cologne (~1h 30min by train)",
    "target_format": "Werkstudent, 20h/Woche, Hybrid",
}


# ── Node runners ───────────────────────────────────────────────────────────────

async def bench_company_extractor(conn, model: str) -> dict:
    from backend import llm
    from backend.models.company import CompanyExtractorOutput
    from backend.prompts.loader import load_prompt
    system = load_prompt("company_extractor")
    user = f"<job_posting>\n{TEST_JOB_POSTING}\n</job_posting>"
    start = time.monotonic()
    result = await llm.call_structured(conn, model=model or "claude-haiku-4-5-20251001",
        system=system, user=user, response_model=CompanyExtractorOutput,
        max_tokens=300, node_name="bench_company_extractor")
    return {"output": result.model_dump(), "latency_ms": int((time.monotonic()-start)*1000)}


async def bench_market_research_extractor(conn, model: str) -> dict:
    from backend import llm
    from backend.models.profile import MarketResearchOutput
    from backend.prompts.loader import load_prompt
    system = load_prompt("market_research_extractor")
    user = f"<market_research>\n{TEST_MARKET_RESEARCH}\n</market_research>"
    start = time.monotonic()
    result = await llm.call_structured(conn, model=model or "claude-haiku-4-5-20251001",
        system=system, user=user, response_model=MarketResearchOutput,
        max_tokens=2048, node_name="bench_market_research_extractor")
    return {"candidates": len(result.candidates), "cities": len(result.city_list),
            "roles": len(result.role_list), "latency_ms": int((time.monotonic()-start)*1000)}


async def bench_binary_classifier(conn, model: str) -> dict:
    from backend import llm
    from backend.models.profile import BinaryClassifierOutput
    from backend.prompts.loader import load_prompt
    system = load_prompt("binary_classifier")
    user = f"Classify each item:\n{json.dumps(TEST_CANDIDATES)}"
    start = time.monotonic()
    result = await llm.call_structured(conn, model=model or "claude-haiku-4-5-20251001",
        system=system, user=user, response_model=BinaryClassifierOutput,
        max_tokens=2048, node_name="bench_binary_classifier")
    valid = sum(1 for d in result.decisions if d.valid)
    return {"total": len(result.decisions), "valid": valid,
            "latency_ms": int((time.monotonic()-start)*1000)}


async def bench_analyzer(conn, model: str) -> dict:
    from backend import llm
    from backend.models.analysis import AnalyzerOutput
    from backend.prompts.loader import load_prompt
    system = load_prompt("analyzer_system")
    user = (f"<job_posting>\n{TEST_JOB_POSTING}\n</job_posting>\n\n"
            f"<candidate_profile>\n{json.dumps(TEST_CANDIDATE_PROFILE, indent=2)}\n</candidate_profile>\n\n"
            f"<company_profile>\nSiemens ist ein globaler Technologiekonzern.\n</company_profile>\n\n"
            f"<cv_text>\n{TEST_CV}\n</cv_text>")
    start = time.monotonic()
    result = await llm.call_structured(conn, model=model or "gpt-4.1",
        system=system, user=user, response_model=AnalyzerOutput,
        max_tokens=2000, node_name="bench_analyzer")
    total = (result.technical.score + result.requirements.score + result.role_fit.score
             + result.location.score + result.strategic.score)
    return {"total_score": total, "technical": result.technical.score,
            "latency_ms": int((time.monotonic()-start)*1000)}


async def bench_anschreiben(conn, model: str) -> dict:
    from backend import llm
    from backend.models.company import CompanyResearchResult
    from backend.prompts.loader import load_prompt
    system = load_prompt("anschreiben")
    company = CompanyResearchResult(company_name="Siemens AG", search_name="Siemens")
    user = (f"<job_language>de</job_language>\n\n"
            f"<job_posting>\n{TEST_JOB_POSTING}\n</job_posting>\n\n"
            f"<company_name>{company.company_name}</company_name>\n\n"
            f"<cv_text>\n{TEST_CV}\n</cv_text>\n\n"
            f"<candidate_summary>\nName: Sara Mustermann\nCore skills: Excel, Power BI\n"
            f"Career target: Controlling Werkstudent\n</candidate_summary>")
    start = time.monotonic()
    text = await llm.call_raw(conn, model=model or "claude-sonnet-4-6",
        system=system, user=user, max_tokens=1000, temperature=0.3,
        node_name="bench_anschreiben")
    return {"words": len(text.split()), "latency_ms": int((time.monotonic()-start)*1000)}


async def bench_cv_translator(conn, model: str) -> dict:
    from backend import llm
    from backend.prompts.loader import load_prompt
    system = load_prompt("cv_translator")
    user = f"<target_language>en</target_language>\n\n<cv_text>\n{TEST_CV}\n</cv_text>"
    start = time.monotonic()
    text = await llm.call_raw(conn, model=model or "claude-sonnet-4-6",
        system=system, user=user, max_tokens=3000, temperature=0.2,
        node_name="bench_cv_translator")
    return {"words": len(text.split()), "latency_ms": int((time.monotonic()-start)*1000)}


NODES = {
    "company_extractor": ("claude-haiku-4-5-20251001", bench_company_extractor),
    "market_research_extractor": ("claude-haiku-4-5-20251001", bench_market_research_extractor),
    "binary_classifier": ("claude-haiku-4-5-20251001", bench_binary_classifier),
    "analyzer": ("gpt-4.1", bench_analyzer),
    "anschreiben": ("claude-sonnet-4-6", bench_anschreiben),
    "cv_translator": ("claude-sonnet-4-6", bench_cv_translator),
}


async def store_benchmark(conn, *, node_name: str, model: str, output_raw: str,
                          latency_ms: int, notes: str) -> None:
    await conn.execute(
        """
        INSERT INTO job_application_assistant.llm_node_benchmarks
            (node_name, model, prompt_v, latency_ms, output_raw, notes)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        node_name, model, "v1", latency_ms, output_raw, notes,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark individual LLM pipeline nodes.")
    parser.add_argument("--node", required=True, choices=list(NODES), help="Node to benchmark")
    parser.add_argument("--model", default=None, help="Override model (default: node's assigned model)")
    parser.add_argument("--n", type=int, default=1, help="Number of runs (default: 1)")
    args = parser.parse_args()

    default_model, runner = NODES[args.node]
    model = args.model or default_model

    print(f"\nBenchmarking: {args.node} | model: {model} | runs: {args.n}\n")

    pool = await get_pool()
    latencies = []

    for i in range(args.n):
        async with pool.acquire() as conn:
            try:
                result = await runner(conn, model)
                latencies.append(result["latency_ms"])
                output_raw = json.dumps(result, ensure_ascii=False)
                await store_benchmark(
                    conn,
                    node_name=args.node,
                    model=model,
                    output_raw=output_raw,
                    latency_ms=result["latency_ms"],
                    notes=f"benchmark run {i+1}/{args.n}",
                )
                print(f"  Run {i+1}: {result['latency_ms']}ms — {result}")
            except Exception as exc:
                print(f"  Run {i+1}: FAILED — {exc}")

    if latencies:
        avg = sum(latencies) // len(latencies)
        print(f"\nAvg latency: {avg}ms over {len(latencies)} successful run(s)")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
