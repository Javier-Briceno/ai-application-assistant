"""
Deterministic helpers for company research.
Ports the Build Search Query and Extract Results Code Nodes from n8n.
"""


def build_search_query(search_name: str) -> str:
    """
    Build a Google search query for the company.
    Mirrors the n8n Build Search Query Code Node.
    Returns empty string if search_name is empty.
    """
    if not search_name or not search_name.strip():
        return ""
    name = search_name.strip()
    return f'"{name}" Arbeitgeber Bewerbung Unternehmenskultur'


def extract_results_text(organic_results: list[dict], max_words: int = 800) -> str:
    """
    Build a plain-text company profile from SerpAPI organic_results.
    Mirrors the n8n Extract Results Code Node (caps at ~800 words).
    Each result contributes: title + snippet + link, separated by blank lines.
    Stops adding results once max_words would be exceeded.
    """
    parts: list[str] = []
    word_count = 0

    for result in organic_results:
        title = (result.get("title") or "").strip()
        snippet = (result.get("snippet") or "").strip()
        link = (result.get("link") or "").strip()

        entry_lines = [line for line in [title, snippet, link] if line]
        if not entry_lines:
            continue

        entry = "\n".join(entry_lines)
        entry_words = len(entry.split())

        if word_count + entry_words > max_words:
            break

        parts.append(entry)
        word_count += entry_words

    return "\n\n".join(parts)
