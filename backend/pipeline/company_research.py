"""
Company research pipeline.
Ports the n8n "Utility: Company Research" sub-workflow to Python.

Flow:
  1. LLM extracts company_name + search_name from job posting (Haiku)
  2. Build search query (deterministic)
  3. If query is empty → return empty CompanyResearchResult
  4. SerpAPI Google search (5 results)
  5. Extract and cap result text at ~800 words (deterministic)
  6. Return CompanyResearchResult
"""
import logging

import asyncpg
import httpx

from backend import llm
from backend.config import settings
from backend.deterministic.company_research import build_search_query, extract_results_text
from backend.models.company import CompanyExtractorOutput, CompanyResearchResult
from backend.prompts.loader import load_prompt

log = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"
_SERPAPI_URL = "https://serpapi.com/search"
_SEARCH_RESULTS_COUNT = 5


async def _extract_company_name(
    conn: asyncpg.Connection,
    job_posting: str,
    profile_id: int | None,
) -> CompanyExtractorOutput:
    system = load_prompt("company_extractor")
    user = f"<job_posting>\n{job_posting}\n</job_posting>"
    return await llm.call_structured(
        conn,
        model=_HAIKU,
        system=system,
        user=user,
        response_model=CompanyExtractorOutput,
        max_tokens=300,
        temperature=0.0,
        node_name="company_extractor",
        profile_id=profile_id,
    )


async def _serpapi_search(query: str) -> list[dict]:
    """Call SerpAPI and return organic_results list."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            _SERPAPI_URL,
            params={
                "q": query,
                "api_key": settings.serpapi_key,
                "num": _SEARCH_RESULTS_COUNT,
                "engine": "google",
                "gl": "de",
                "hl": "de",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic_results", [])


async def _lookup_company_address(company_name: str, city: str = "") -> str:
    """
    Look up a company's street address via SerpAPI Google Maps.
    Returns a formatted address string (e.g. "Musterstraße 1, 12345 Berlin")
    or "" if not found or on any error.
    """
    q = f"{company_name} {city}".strip()
    if not q:
        return ""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _SERPAPI_URL,
                params={
                    "engine": "google_maps",
                    "q": q,
                    "type": "search",
                    "api_key": settings.serpapi_key,
                    "hl": "de",
                    "gl": "de",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        local_results = data.get("local_results", [])
        if local_results:
            address: str = local_results[0].get("address", "")
        elif "place_results" in data:
            # City-specific query returns a single place_results card instead of a list
            address = data["place_results"].get("address", "")
        else:
            return ""
        # Strip trailing country suffix — implicit on a German CV
        for suffix in (", Germany", ", Deutschland"):
            if address.endswith(suffix):
                address = address[: -len(suffix)]
        return address.strip()
    except Exception:
        log.warning("Company address lookup failed for %r — continuing without address", company_name)
        return ""


async def run_company_research(
    conn: asyncpg.Connection,
    *,
    job_posting: str,
    profile_id: int | None = None,
) -> CompanyResearchResult:
    """
    Extract company name from job posting, search via SerpAPI,
    and return a CompanyResearchResult with company_profile text.
    An empty company_profile is a valid result (no search results found).
    Never raises — returns an empty result on any failure so the main
    pipeline can continue without company context.
    """
    try:
        extractor = await _extract_company_name(conn, job_posting, profile_id)
    except Exception:
        log.exception("Company extractor LLM failed — returning empty result")
        return CompanyResearchResult()

    company_name = extractor.company_name or ""
    search_name = extractor.search_name or ""

    query = build_search_query(search_name)
    if not query:
        log.info("No company identified — skipping search")
        return CompanyResearchResult(company_name=company_name, search_name=search_name)

    try:
        organic_results = await _serpapi_search(query)
    except Exception:
        log.exception("SerpAPI search failed for query %r — continuing without company profile", query)
        return CompanyResearchResult(company_name=company_name, search_name=search_name)

    company_profile = extract_results_text(organic_results)
    log.info(
        "Company research complete: %r — %d results, %d words",
        company_name,
        len(organic_results),
        len(company_profile.split()),
    )

    company_address = await _lookup_company_address(company_name, city=extractor.job_city or "")
    if company_address:
        log.info("Company address found: %r", company_address)
    else:
        log.info("Company address not found for %r", company_name)

    return CompanyResearchResult(
        company_name=company_name,
        search_name=search_name,
        company_profile=company_profile,
        company_address=company_address,
        contact_person=extractor.contact_person or "",
    )
