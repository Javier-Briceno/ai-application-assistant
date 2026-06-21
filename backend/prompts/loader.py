from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, version: str = "v1") -> str:
    """Load a system prompt from prompts/<version>/<name>.txt"""
    path = _PROMPTS_DIR / version / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
