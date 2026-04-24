"""Ghost Hunt — find corpus articles that mention officially-empty Wikipedia categories.

Wikipedia has official categories (e.g. "Bolshevism", "Western Front") that return
0 members from the category API. This script reverse-hunts: searching article *text*
for these ghost terms to show the substance is there but structurally invisible.

Input:  corpus JSONL  (default: ./data/wwi_extended.jsonl)
Output: output/ghost_mentions.jsonl  — one record per (term, article) pair
        output/ghost_summary.json    — {term: {article_count, total_mentions}}
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# Ghost terms: official Wikipedia category names that return 0 members.
# These concepts are structurally invisible in Wikipedia's category hierarchy
# despite being central to understanding WWI.
GHOST_TERMS: list[str] = [
    # Original ghost terms
    "Assassination of Archduke Franz Ferdinand",
    "Western Front",
    "Bolshevism",
    "Bolshevik",
    "Lenin",
    "Revolution",
    # People
    "Rosa Luxemburg",
    "Enver Pasha",
    "Talaat Pasha",
    "Trotsky",
    "Rasputin",
    "Mustafa Kemal",
    # Organizations / Movements
    "Young Turks",
    "Spartacist",
    "Mensheviks",
    "Pan-Slavism",
    "Zionism",
    # Theaters / Places
    "Persia",
    "Gallipoli",
    "Mesopotamia",
    "Caucasus",
    "Salonika",
    # Events / Concepts
    "July Crisis",
    "Armenian",
    "Brest-Litovsk",
    "Schlieffen",
    "War guilt",
]

CONTEXT_WINDOW = 150  # chars of context around each mention


def find_mentions(text: str, term: str) -> list[dict]:
    """Find all case-insensitive mentions of term in text, with context."""
    mentions = []
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    for m in pattern.finditer(text):
        start = m.start()
        end = m.end()
        ctx_start = max(0, start - CONTEXT_WINDOW)
        ctx_end = min(len(text), end + CONTEXT_WINDOW)
        mentions.append({
            "start": start,
            "end": end,
            "context": text[ctx_start:ctx_end],
        })
    return mentions


def main() -> None:
    parser = argparse.ArgumentParser(description="Find ghost term mentions in corpus")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "wwi_extended.jsonl",
        help="Corpus JSONL (default: ./data/wwi_extended.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "output",
    )
    parser.add_argument(
        "--terms",
        nargs="+",
        metavar="TERM",
        help="Override ghost terms (space-separated; quote multi-word terms)",
    )
    args = parser.parse_args()

    ghost_terms = args.terms if args.terms else GHOST_TERMS

    if not args.corpus.exists():
        raise FileNotFoundError(
            f"Corpus not found: {args.corpus}\n"
            "Run the fetch pipeline in the parent project first, or pass --corpus <path>"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    mentions_path = args.output_dir / "ghost_mentions.jsonl"
    summary_path = args.output_dir / "ghost_summary.json"

    print(f"Corpus: {args.corpus}")
    print(f"Ghost terms ({len(ghost_terms)}): {', '.join(ghost_terms)}")
    print()

    # Load corpus
    articles = []
    with args.corpus.open() as f:
        for line in f:
            line = line.strip()
            if line:
                articles.append(json.loads(line))
    print(f"Loaded {len(articles)} articles")

    # Hunt
    summary: dict[str, dict] = defaultdict(lambda: {"article_count": 0, "total_mentions": 0})
    records_written = 0

    with mentions_path.open("w") as out:
        for article in articles:
            text = article.get("wikitext") or article.get("text") or ""
            pageid = article.get("pageid")
            title = article.get("title", "")

            for term in ghost_terms:
                hits = find_mentions(text, term)
                if not hits:
                    continue
                summary[term]["article_count"] += 1
                summary[term]["total_mentions"] += len(hits)
                record = {
                    "ghost_term": term,
                    "pageid": pageid,
                    "title": title,
                    "mention_count": len(hits),
                    "positions": hits,
                }
                out.write(json.dumps(record) + "\n")
                records_written += 1

    # Write summary
    with summary_path.open("w") as f:
        json.dump(dict(summary), f, indent=2)

    # Print results
    print(f"\nResults written to {mentions_path}")
    print(f"Total (term, article) pairs: {records_written}\n")
    print(f"{'Ghost term':<45} {'Articles':>8} {'Mentions':>9}")
    print("-" * 65)
    for term in ghost_terms:
        s = summary.get(term, {"article_count": 0, "total_mentions": 0})
        print(f"{term:<45} {s['article_count']:>8} {s['total_mentions']:>9}")


if __name__ == "__main__":
    main()
