"""Skill detection: turn free-text job descriptions into weighted skill requirements."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, NamedTuple

OPTIONAL_WEIGHT = 0.5
REQUIRED_WEIGHT = 1.0

# A posting's "even better if you have" block should not count as hard as its
# "requirements" block, so section state carries across lines until the next header.
_OPTIONAL_SECTION = re.compile(
    r"(nice[- ]to[- ]have|even better|bonus|preferred qualification|preferred skills|"
    r"preferred:|pluses|optional)",
    re.I,
)
_REQUIRED_SECTION = re.compile(
    r"(requirement|qualification|responsibilit|what you.{0,3}ll do|what you will do|"
    r"what you will be doing|must have|required|your background|we are looking for|"
    r"in this role|about the role|you will)",
    re.I,
)
_OPTIONAL_INLINE = re.compile(
    r"(is a plus|a plus\b|nice to have|preferred|bonus|ideally|not required)", re.I
)


class Detection(NamedTuple):
    skill: str
    category: str
    weight: float
    evidence: str


def load_taxonomy(path: Path) -> Dict[str, dict]:
    with open(path) as handle:
        return json.load(handle)["skills"]


def _compile(aliases: List[str]) -> re.Pattern:
    # Plain \b fails on aliases ending in punctuation (c#, next.js, ci/cd).
    body = "|".join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9])(?:" + body + r")(?![A-Za-z0-9])", re.I)


def detect(text: str, taxonomy: Dict[str, dict]) -> List[Detection]:
    patterns = {skill: _compile(spec["aliases"]) for skill, spec in taxonomy.items()}
    best: Dict[str, Detection] = {}
    optional_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _OPTIONAL_SECTION.search(line):
            optional_section = True
        elif _REQUIRED_SECTION.search(line):
            optional_section = False

        optional = optional_section or bool(_OPTIONAL_INLINE.search(line))
        weight = OPTIONAL_WEIGHT if optional else REQUIRED_WEIGHT

        for skill, pattern in patterns.items():
            if not pattern.search(line):
                continue
            # A skill named in both a requirements block and a bonus block is a
            # requirement; keep the strongest signal.
            previous = best.get(skill)
            if previous is None or weight > previous.weight:
                best[skill] = Detection(skill, taxonomy[skill]["category"], weight, line[:200])

    return sorted(best.values(), key=lambda d: (-d.weight, d.skill))
