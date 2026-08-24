"""Prompt templates, versioned as files rather than inline strings.

Prompts are kept out of Python for three reasons: they diff readably in git,
they can be reviewed by a finance domain expert who does not read Python, and
each carries a version tag that gets recorded in the audit log -- so a decision
made six weeks ago can be traced to the exact prompt that produced it.

    triage.md        classification instructions + taxonomy definitions
    investigate.md   tool-use guidance and stopping conditions
    hypothesize.md   proposal schema + evidence-citation requirements
    narrate.md       controller-language explanation style
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent

# Bumped whenever any template changes; recorded on every agent decision.
PROMPT_VERSION = "v0.1.0"


def load(name: str) -> str:
    """TODO(phase-5): read ``{name}.md`` from this directory, cached."""
    return _load(name)


@cache
def _load(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")
