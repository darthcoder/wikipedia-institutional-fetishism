"""Collision Analysis — find articles where two ghost terms co-occur and measure distance.

The core finding: the Assassination narrative and the Bolshevik narrative barely touch.
Only one article (Sergey Sazonov) mentions both, and the mentions are 2,684 characters
apart — in completely separate narrative sections. Not a causal connection. Just a man
who was present at both moments.

This script produces that finding reproducibly for every ghost term pair.

Input:  output/ghost_mentions.jsonl
Output: output/collision.json
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path


SEPARATION_THRESHOLD = 1000  # chars — above this, mentions are "structurally separate"


def min_distance(positions_a: list[dict], positions_b: list[dict]) -> tuple[int, dict, dict]:
    """Find the closest pair of mentions between two term sets. Returns (distance, pos_a, pos_b)."""
    best_dist = float("inf")
    best_a = best_b = None
    for a in positions_a:
        for b in positions_b:
            # Distance between the two mentions (gap between end of earlier and start of later)
            dist = max(0, max(a["start"], b["start"]) - min(a["end"], b["end"]))
            if dist < best_dist:
                best_dist = dist
                best_a = a
                best_b = b
    return int(best_dist), best_a, best_b


def main() -> None:
    parser = argparse.ArgumentParser(description="Collision analysis for ghost term co-occurrence")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "output",
    )
    args = parser.parse_args()

    mentions_path = args.output_dir / "ghost_mentions.jsonl"
    collision_path = args.output_dir / "collision.json"

    if not mentions_path.exists():
        raise FileNotFoundError(f"Run ghost_hunt.py first: {mentions_path}")

    # Group mentions: pageid → {term → [positions]}
    by_article: dict[int, dict] = defaultdict(lambda: {"title": "", "terms": defaultdict(list)})
    term_article_sets: dict[str, set[int]] = defaultdict(set)

    with mentions_path.open() as f:
        for line in f:
            r = json.loads(line)
            pid = r["pageid"]
            by_article[pid]["title"] = r["title"]
            by_article[pid]["terms"][r["ghost_term"]].extend(r["positions"])
            term_article_sets[r["ghost_term"]].add(pid)

    all_terms = sorted(term_article_sets.keys())
    print(f"Ghost terms found in corpus: {all_terms}")
    print(f"Articles with any ghost mention: {len(by_article)}")

    # Collision matrix: every pair of terms
    collision_matrix: dict[str, dict] = {}
    cross_narrative_isolation: dict[str, str] = {}

    pairs = list(itertools.combinations(all_terms, 2))
    print(f"\nAnalyzing {len(pairs)} term pairs...\n")

    for term_a, term_b in pairs:
        set_a = term_article_sets[term_a]
        set_b = term_article_sets[term_b]
        overlap = set_a & set_b

        pair_key = f"{term_a} | {term_b}"
        collision_articles = []

        for pid in overlap:
            art = by_article[pid]
            positions_a = art["terms"][term_a]
            positions_b = art["terms"][term_b]
            dist, pos_a, pos_b = min_distance(positions_a, positions_b)

            collision_articles.append({
                "pageid": pid,
                "title": art["title"],
                "min_distance": dist,
                "structurally_separate": dist > SEPARATION_THRESHOLD,
                "term_a": term_a,
                "term_a_context": pos_a["context"] if pos_a else "",
                "term_b": term_b,
                "term_b_context": pos_b["context"] if pos_b else "",
            })

        collision_articles.sort(key=lambda x: x["min_distance"], reverse=True)

        overlap_pct_a = round(100 * len(overlap) / len(set_a), 1) if set_a else 0
        overlap_pct_b = round(100 * len(overlap) / len(set_b), 1) if set_b else 0

        collision_matrix[pair_key] = {
            "term_a_article_count": len(set_a),
            "term_b_article_count": len(set_b),
            "collision_count": len(overlap),
            "overlap_pct_of_a": overlap_pct_a,
            "overlap_pct_of_b": overlap_pct_b,
            "articles": collision_articles,
        }

        cross_narrative_isolation[pair_key] = (
            f"{overlap_pct_a}% of {term_a!r} articles mention {term_b!r}; "
            f"{overlap_pct_b}% of {term_b!r} articles mention {term_a!r}"
        )

        # Print summary
        sep_count = sum(1 for a in collision_articles if a["structurally_separate"])
        print(f"{term_a!r} × {term_b!r}")
        print(f"  Collision: {len(overlap)} articles  ({overlap_pct_a}% / {overlap_pct_b}%)")
        if collision_articles:
            print(f"  Structurally separate (>{SEPARATION_THRESHOLD} chars): {sep_count}/{len(overlap)}")
            for art in collision_articles[:3]:
                sep_flag = "SEPARATE" if art["structurally_separate"] else "adjacent"
                print(f"    [{sep_flag} dist={art['min_distance']}] {art['title']}")
        print()

    result = {
        "separation_threshold": SEPARATION_THRESHOLD,
        "collision_matrix": collision_matrix,
        "cross_narrative_isolation": cross_narrative_isolation,
    }

    with collision_path.open("w") as f:
        json.dump(result, f, indent=2)

    print(f"Collision analysis written to {collision_path}")

    # Key finding summary
    key_pair = next(
        (k for k in collision_matrix if "Bolshev" in k and "Assassin" in k), None
    )
    if key_pair:
        cm = collision_matrix[key_pair]
        print(f"\n=== KEY FINDING: {key_pair} ===")
        print(f"Collisions: {cm['collision_count']} article(s)")
        for art in cm["articles"]:
            print(f"  '{art['title']}' — min distance: {art['min_distance']} chars")
            print(f"    {art['term_a']!r} context: ...{art['term_a_context'][:80]}...")
            print(f"    {art['term_b']!r} context: ...{art['term_b_context'][:80]}...")


if __name__ == "__main__":
    main()
