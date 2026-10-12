#!/usr/bin/env python3
"""Score captured job postings against the candidate profile and write reports.

    python run.py                      # score everything in jobs/
    python run.py --threshold 75       # change the apply/gap cutoff
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from src.gaps import aggregate, by_category
from src.scoring import ScoreResult, load_profile, parse_posting, score
from src.taxonomy import detect, load_taxonomy

ROOT = Path(__file__).parent
JOBS = ROOT / "jobs"
REPORTS = ROOT / "reports"


def run(threshold: float) -> List[ScoreResult]:
    taxonomy = load_taxonomy(ROOT / "data" / "taxonomy.json")
    profile = load_profile(ROOT / "data" / "profile.json")

    results = []
    for path in sorted(JOBS.glob("*.txt")):
        posting = parse_posting(path)
        results.append(score(posting, detect(posting.body, taxonomy), profile))

    return sorted(results, key=lambda r: -r.match_pct)


def write_matches(results: List[ScoreResult], threshold: float) -> None:
    lines = ["# Match report", ""]
    lines.append("| Match | Decision | Eligibility | Role | Company | Location |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        lines.append(
            "| {:.0f}% | {} | {} | {} | {} | {} |".format(
                r.match_pct, r.decision, r.eligibility, r.posting.title,
                r.posting.company, r.posting.location,
            )
        )

    for r in results:
        lines += ["", "## {} — {} ({:.0f}%)".format(r.posting.title, r.posting.company, r.match_pct)]
        if r.posting.url:
            lines.append(r.posting.url)
        lines.append("")
        lines.append("- Eligibility: **{}** ({})".format(r.eligibility, r.eligibility_note))
        lines.append("- Have: {}".format(", ".join(r.matched) or "none detected"))
        if r.partial:
            lines.append("- Partial (coursework/certificate only): {}".format(", ".join(r.partial)))
        if r.missing:
            hard = [d.skill for d in r.missing if d.weight == 1.0]
            soft = [d.skill for d in r.missing if d.weight < 1.0]
            if hard:
                lines.append("- Missing (required): {}".format(", ".join(hard)))
            if soft:
                lines.append("- Missing (preferred): {}".format(", ".join(soft)))

    (REPORTS / "matches.md").write_text("\n".join(lines) + "\n")


def write_learning_plan(results: List[ScoreResult], threshold: float) -> None:
    gaps = aggregate(results, threshold)
    lines = [
        "# Learning plan",
        "",
        "Ranked by demand across postings scoring under {:.0f}%. Demand sums each "
        "posting's weight for that skill, so hard requirements outrank bonus mentions.".format(threshold),
        "",
    ]

    for category, items in by_category(gaps).items():
        lines += ["## {}".format(category), ""]
        lines.append("| Skill | Demand | Postings |")
        lines.append("|---|---|---|")
        for gap in items:
            lines.append("| {} | {:.1f} | {} |".format(gap.skill, gap.demand, gap.frequency))
        lines.append("")

    (REPORTS / "learning-plan.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=80.0)
    args = parser.parse_args()

    REPORTS.mkdir(exist_ok=True)
    results = run(args.threshold)
    if not results:
        print("No postings found in {}/".format(JOBS.name))
        return

    write_matches(results, args.threshold)
    write_learning_plan(results, args.threshold)

    print("{:<6} {:<10} {:<12} {}".format("MATCH", "DECISION", "ELIGIBILITY", "ROLE"))
    for r in results:
        print("{:<6} {:<10} {:<12} {} — {}".format(
            "{:.0f}%".format(r.match_pct), r.decision, r.eligibility,
            r.posting.title, r.posting.company,
        ))
    print("\nReports written to {}/".format(REPORTS.name))


if __name__ == "__main__":
    main()
