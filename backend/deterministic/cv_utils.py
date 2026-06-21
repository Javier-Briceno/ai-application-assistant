"""
CV normalization and hashing utilities.
Mirrors the normalizeCV() function and SHA-256 logic from the
n8n Extract Profile workflow (Validate Inputs + Hash CV nodes).
"""
import hashlib
import re


# Section headers that appear in plain-text CVs.
# These are promoted to ## markdown so the LLM can locate them reliably.
_SECTION_PATTERNS = [
    r"^(Berufserfahrung|Work Experience|Professional Experience|Experience)",
    r"^(Ausbildung|Education|Bildung)",
    r"^(Fähigkeiten|Skills|Kenntnisse|Technical Skills|Technische Kenntnisse)",
    r"^(Projekte|Projects)",
    r"^(Zertifikate|Certifications|Certificates|Zertifizierungen)",
    r"^(Sprachen|Languages)",
    r"^(Zusammenfassung|Summary|Profil|Profile|Über mich|About Me)",
    r"^(Freiwilligenarbeit|Volunteering|Ehrenamt)",
    r"^(Publikationen|Publications)",
    r"^(Interessen|Interests|Hobbys|Hobbies)",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _SECTION_PATTERNS]


def normalize_cv(cv_text: str) -> str:
    """
    Promote plain-text section headers to ## markdown headers.
    Only promotes lines that exactly match a known header and are
    not already prefixed with # or *.
    """
    lines = cv_text.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("*"):
            for pattern in _COMPILED:
                if pattern.match(stripped):
                    line = f"## {stripped}"
                    break
        result.append(line)
    return "\n".join(result)


def hash_cv(cv_text: str) -> str:
    """Return SHA-256 hex digest of the CV text (UTF-8 encoded)."""
    return hashlib.sha256(cv_text.encode("utf-8")).hexdigest()


def compute_content_hash(cv_text: str, career_target: str, market_research: str) -> str:
    """SHA-256 over all three LLM-input fields (null-byte separated).

    Used to detect whether candidate_profile / role_type_scores need to be
    regenerated.  Any change to cv_text, career_target, or market_research
    changes this hash; changes to profile metadata (name, city, …) do not.
    """
    combined = f"{cv_text}\x00{career_target}\x00{market_research}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
