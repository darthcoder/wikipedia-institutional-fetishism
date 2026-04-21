"""Dispersal Map — measure how ghost-term articles scatter across real Wikipedia categories.

For each article that mentions a ghost term, fetches ALL its actual Wikipedia categories
(not a predefined list — every category the article truly belongs to). Then computes:
  - How many unique categories the ghost-term article set scatters across
  - Which categories cluster vs. which are isolated
  - Category frequency distribution

This produces the dispersal numbers cited in the vault analysis:
  "67 Assassination articles scatter across 757 different categories"

Input:  output/ghost_mentions.jsonl
Output: output/dispersal.json
        output/category_cache.json  (API cache, avoids re-fetching)
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import requests

HEADERS = {"User-Agent": "institutional-fetishism/0.1 (research)"}
API = "https://en.wikipedia.org/w/api.php"
MAX_RETRIES = 6


def api_get(params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        r = requests.get(API, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            wait = 2 ** (attempt + 2)
            print(f"    429 — waiting {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries")


def fetch_all_categories(pageid: int) -> list[str]:
    """Fetch every category an article belongs to (paginated)."""
    categories = []
    params = {
        "action": "query",
        "pageids": pageid,
        "prop": "categories",
        "cllimit": 500,
        "format": "json",
    }
    while True:
        data = api_get(params)
        page = next(iter(data["query"]["pages"].values()))
        for cat in page.get("categories", []):
            categories.append(cat["title"])
        cont = data.get("continue", {}).get("clcontinue")
        if not cont:
            break
        params["clcontinue"] = cont
        time.sleep(0.1)
    return categories


def main() -> None:
    parser = argparse.ArgumentParser(description="Map dispersal of ghost-term articles")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "output",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Sleep between API calls (seconds)",
    )
    args = parser.parse_args()

    mentions_path = args.output_dir / "ghost_mentions.jsonl"
    cache_path = args.output_dir / "category_cache.json"
    dispersal_path = args.output_dir / "dispersal.json"

    if not mentions_path.exists():
        raise FileNotFoundError(f"Run ghost_hunt.py first: {mentions_path}")

    # Load ghost mentions
    by_term: dict[str, list[dict]] = defaultdict(list)
    all_pageids: set[int] = set()
    with mentions_path.open() as f:
        for line in f:
            r = json.loads(line)
            by_term[r["ghost_term"]].append(r)
            all_pageids.add(r["pageid"])

    print(f"Ghost terms: {list(by_term.keys())}")
    print(f"Unique articles to categorize: {len(all_pageids)}")

    # Load or init cache
    cache: dict[str, list[str]] = {}
    if cache_path.exists():
        with cache_path.open() as f:
            cache = json.load(f)
        print(f"Cache loaded: {len(cache)} articles already fetched")

    # Fetch categories for uncached articles
    uncached = [pid for pid in all_pageids if str(pid) not in cache]
    print(f"Fetching categories for {len(uncached)} new articles...")
    for i, pageid in enumerate(uncached):
        try:
            cats = fetch_all_categories(pageid)
            cache[str(pageid)] = cats
            if i % 20 == 0:
                print(f"  {i}/{len(uncached)}")
                with cache_path.open("w") as f:
                    json.dump(cache, f)
            time.sleep(args.sleep)
        except Exception as e:
            print(f"  SKIP {pageid}: {e}")
            cache[str(pageid)] = []

    # Final cache save
    with cache_path.open("w") as f:
        json.dump(cache, f)
    print(f"Cache saved: {cache_path}")

    # Compute dispersal per ghost term
    dispersal: dict[str, dict] = {}

    print(f"\n{'Ghost term':<45} {'Articles':>8} {'Unique cats':>12}")
    print("-" * 68)

    for term, records in by_term.items():
        cat_freq: dict[str, int] = defaultdict(int)
        article_cat_counts = []

        for rec in records:
            pid = str(rec["pageid"])
            cats = cache.get(pid, [])
            for cat in cats:
                cat_freq[cat] += 1
            article_cat_counts.append({
                "pageid": rec["pageid"],
                "title": rec["title"],
                "mention_count": rec["mention_count"],
                "category_count": len(cats),
                "categories": cats,
            })

        unique_cats = len(cat_freq)
        top_cats = sorted(cat_freq.items(), key=lambda x: x[1], reverse=True)[:20]

        dispersal[term] = {
            "article_count": len(records),
            "unique_categories": unique_cats,
            "top_categories": [{"category": c, "article_count": n} for c, n in top_cats],
            "articles": sorted(article_cat_counts, key=lambda x: x["category_count"], reverse=True),
        }

        print(f"{term:<45} {len(records):>8} {unique_cats:>12}")

    with dispersal_path.open("w") as f:
        json.dump(dispersal, f, indent=2)

    print(f"\nDispersal written to {dispersal_path}")


if __name__ == "__main__":
    main()
