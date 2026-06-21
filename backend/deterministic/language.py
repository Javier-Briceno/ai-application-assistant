"""
Detect CV/job-posting language via stopword scoring.
Mirrors the Code Node logic from the n8n main workflow (Input Wrapper node).
Returns 'de' or 'en'.
"""

_DE_STOPWORDS = frozenset([
    "und", "oder", "aber", "als", "auch", "auf", "bei", "bin", "bis", "da",
    "das", "dem", "den", "der", "des", "die", "du", "ein", "eine", "einem",
    "einen", "einer", "eines", "er", "es", "für", "hat", "ich", "ihr", "im",
    "in", "ist", "mit", "nach", "nicht", "noch", "oder", "sein", "sie",
    "sind", "so", "über", "um", "und", "uns", "von", "vor", "war", "wir",
    "wird", "zu", "zum", "zur", "zwischen", "haben", "werden", "können",
    "Jahren", "Erfahrung", "Kenntnisse", "Fähigkeiten", "Lebenslauf",
    "Bewerbung", "Stelle", "Aufgaben", "Anforderungen",
])

_EN_STOPWORDS = frozenset([
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "its", "may", "new", "now", "old", "see", "two", "way", "who",
    "did", "she", "use", "their", "what", "with", "have", "from", "they",
    "will", "your", "this", "that", "been", "more", "when", "than", "into",
    "experience", "skills", "work", "team", "job", "role", "position",
    "requirements", "responsibilities", "resume", "application",
])


def detect_language(text: str) -> str:
    """Return 'de' or 'en' based on stopword frequency in the given text."""
    words = text.lower().split()
    if not words:
        return "de"

    de_count = sum(1 for w in words if w.strip(".,;:!?()[]{}\"'") in _DE_STOPWORDS)
    en_count = sum(1 for w in words if w.strip(".,;:!?()[]{}\"'") in _EN_STOPWORDS)

    return "de" if de_count >= en_count else "en"
