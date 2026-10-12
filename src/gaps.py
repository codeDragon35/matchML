"""Turn below-threshold postings into a ranked learning plan."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from .scoring import ScoreResult


@dataclass
class Gap:
    skill: str
    category: str
    postings: List[str]
    demand: float

    @property
    def frequency(self) -> int:
        return len(self.postings)


def aggregate(results: List[ScoreResult], threshold: float = 80.0) -> List[Gap]:
    """Rank missing skills by demand across the postings that fell short.

    Demand sums each posting's weight for the skill, so something listed as a hard
    requirement in five postings outranks a bonus skill mentioned in eight.
    """
    tally: Dict[str, Gap] = {}

    for result in results:
        if result.match_pct >= threshold:
            continue
        for detection in result.missing:
            gap = tally.get(detection.skill)
            if gap is None:
                gap = Gap(detection.skill, detection.category, [], 0.0)
                tally[detection.skill] = gap
            gap.postings.append(result.posting.title)
            gap.demand += detection.weight

    return sorted(tally.values(), key=lambda g: (-g.demand, g.skill))


def by_category(gaps: List[Gap]) -> Dict[str, List[Gap]]:
    grouped = defaultdict(list)
    for gap in gaps:
        grouped[gap.category].append(gap)
    return dict(grouped)
