"""Pass 3 -- fuzzy scored matching. PLACEHOLDER -- signatures only.

Generates candidates via blocking, scores each on multiple features, and
accepts only when the winner clears both the score threshold and the margin
over the runner-up (see ``recon.scoring.pick_best``).

Every accepted match carries its per-feature breakdown, so the UI can show
*why* rather than just a number.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import MatchMethod
from ledgerpilot.recon.engine import PassResult, ReconContext
from ledgerpilot.recon.scoring import ScoredCandidate


class FuzzyScoreRule:
    """TODO(phase-2)."""

    name = "fuzzy_score"
    method = MatchMethod.FUZZY_SCORE

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        raise NotImplementedError

    def candidates_for(self, ctx: ReconContext, record_id: str) -> list[ScoredCandidate]:
        """TODO: blocking -> score. Also exposed as a read-only agent tool.

        Reusing the same candidate generator for the agent means the agent
        reasons over exactly the evidence the engine saw -- no divergence
        between what the rules considered and what the LLM is shown.
        """
        raise NotImplementedError
