"""Match scoring: how much of what a posting asks for does the candidate actually have?"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .taxonomy import Detection

ELIGIBLE = "eligible"
NEEDS_CHECK = "check"
INELIGIBLE = "ineligible"

_REMOTE = re.compile(r"\bremote\b|work from anywhere|distributed", re.I)


@dataclass
class Posting:
    title: str
    company: str
    location: str
    url: str
    body: str
    source_file: str


@dataclass
class ScoreResult:
    posting: Posting
    match_pct: float
    eligibility: str
    eligibility_note: str
    matched: List[str] = field(default_factory=list)
    partial: List[str] = field(default_factory=list)
    missing: List[Detection] = field(default_factory=list)

    @property
    def decision(self) -> str:
        return "APPLY" if self.match_pct >= 80 else "GAP"


def load_profile(path: Path) -> dict:
    with open(path) as handle:
        return json.load(handle)


def parse_posting(path: Path) -> Posting:
    """Job files carry optional `KEY: value` headers above a blank line, then the body."""
    text = path.read_text()
    headers: Dict[str, str] = {}
    body = text

    if "\n\n" in text:
        head, remainder = text.split("\n\n", 1)
        candidate = {}
        for line in head.splitlines():
            if ":" not in line:
                candidate = {}
                break
            key, value = line.split(":", 1)
            candidate[key.strip().upper()] = value.strip()
        if candidate:
            headers, body = candidate, remainder

    return Posting(
        title=headers.get("TITLE", path.stem),
        company=headers.get("COMPANY", "unknown"),
        location=headers.get("LOCATION", "unspecified"),
        url=headers.get("URL", ""),
        body=body,
        source_file=path.name,
    )


def check_location(location: str, rules: dict) -> Tuple[str, str]:
    """Remote is fine anywhere; on-site in Canada must be Ontario."""
    if _REMOTE.search(location):
        return ELIGIBLE, "remote"

    # Postings often qualify the place in parentheses ("Barcelona, Spain (open to
    # Canada/US candidates)"); the country decision belongs to the primary location.
    primary = location.split("(")[0].strip() or location

    if re.search(r"\bcanada\b|, (on|ON)\b|ontario", primary, re.I):
        region = rules.get("onsite_region_restriction", "Ontario")
        if re.search(region, primary, re.I) or re.search(
            r"toronto|ottawa|mississauga|waterloo|hamilton|greater toronto", primary, re.I
        ):
            return ELIGIBLE, "on-site within {}".format(region)
        return INELIGIBLE, "Canadian role outside {}".format(region)

    if primary == "unspecified":
        return NEEDS_CHECK, "location not stated"

    return NEEDS_CHECK, "on-site outside Canada ({}) - needs relocation/authorisation".format(primary)


def score(posting: Posting, detections: List[Detection], profile: dict) -> ScoreResult:
    held = profile["skills"]
    credit_for = profile["depth_credit"]

    total_weight = sum(d.weight for d in detections)
    earned = 0.0
    matched, partial, missing = [], [], []

    for detection in detections:
        skill = held.get(detection.skill)
        if skill is None:
            missing.append(detection)
            continue
        credit = credit_for[skill["depth"]]
        earned += detection.weight * credit
        (matched if credit == 1.0 else partial).append(detection.skill)

    pct = round(earned / total_weight * 100, 1) if total_weight else 0.0
    eligibility, note = check_location(posting.location, profile["location_rules"])

    return ScoreResult(
        posting=posting,
        match_pct=pct,
        eligibility=eligibility,
        eligibility_note=note,
        matched=sorted(matched),
        partial=sorted(partial),
        missing=sorted(missing, key=lambda d: (-d.weight, d.skill)),
    )
