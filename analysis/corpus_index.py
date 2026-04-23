"""Corpus Index — positional inverted index for ghost term discovery.

Build once, query fast. Two query modes:
  direct    — which articles mention a term, ranked by frequency
  proximity — what terms co-occur within N words (Manhattan distance on token
              positions), revealing the semantic neighbourhood of a ghost term

Usage:
    # Build index (run once; auto-builds on first query too)
    uv run python analysis/corpus_index.py build --corpus ../../data/wwi_extended.jsonl

    # Direct lookup
    uv run python analysis/corpus_index.py query Sazonov
    uv run python analysis/corpus_index.py query "July Crisis"

    # Proximity: what clusters near this term?
    uv run python analysis/corpus_index.py query Sazonov --radius 50
    uv run python analysis/corpus_index.py query Sazonov --radius 50 --top 40
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CORPUS = Path(__file__).parent.parent.parent.parent / "data" / "wwi_extended.jsonl"
DEFAULT_INDEX = Path(__file__).parent.parent / "output" / "corpus_index.pkl"
DEFAULT_RADIUS = 50
DEFAULT_TOP = 30

STOP_WORDS: frozenset[str] = frozenset("""
a about above after again against all also am an and any are aren't as at
be because been before being below between both but by can can't cannot
could couldn't did didn't do does doesn't doing don't down during each few
for from further get got had hadn't has hasn't have haven't having he he'd
he'll he's her here here's hers herself him himself his how how's i i'd
i'll i'm i've if in into is isn't it it's its itself let's me more most
mustn't my myself no nor not of off on once only or other ought our ours
ourselves out over own same shan't she she'd she'll she's should shouldn't
so some such than that that's the their theirs them themselves then there
there's therefore they they'd they'll they're they've this those through
to too under until up very was wasn't we we'd we'll we're we've were weren't
what what's when when's where where's which while who who's whom why why's
will with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves also though even still however thus hence
""".split())


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z][a-z'\-]*")


def tokenize(text: str) -> list[str]:
    """Lowercase, extract word-like tokens, drop single characters."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]


def query_tokens(phrase: str) -> list[str]:
    """Tokenize a multi-word query phrase the same way the index was built."""
    return tokenize(phrase)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_index(corpus_path: Path, index_path: Path) -> dict:
    if not corpus_path.exists():
        sys.exit(f"Corpus not found: {corpus_path}")

    print(f"Building index from {corpus_path} ...")
    inv: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    fwd: dict[int, list[str]] = {}
    docs: dict[int, dict] = {}

    n_articles = n_tokens = 0
    with corpus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            pageid: int = article["pageid"]
            title: str = article.get("title", "")
            text: str = article.get("text") or article.get("wikitext") or ""

            tokens = tokenize(text)
            fwd[pageid] = tokens
            docs[pageid] = {"title": title, "pageid": pageid, "token_count": len(tokens)}

            for pos, tok in enumerate(tokens):
                inv[tok][pageid].append(pos)

            n_articles += 1
            n_tokens += len(tokens)
            if n_articles % 500 == 0:
                print(f"  {n_articles} articles …")

    # Convert nested defaultdicts to plain dicts for pickling
    inv_plain = {tok: dict(docs_map) for tok, docs_map in inv.items()}

    bundle = {
        "meta": {
            "corpus": str(corpus_path),
            "built_at": datetime.now().isoformat(),
            "article_count": n_articles,
            "token_count": n_tokens,
            "vocab_size": len(inv_plain),
        },
        "docs": docs,
        "index": inv_plain,
        "forward": fwd,
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("wb") as f:
        pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\nIndex saved → {index_path}")
    print(f"  Articles : {n_articles:,}")
    print(f"  Tokens   : {n_tokens:,}")
    print(f"  Vocab    : {len(inv_plain):,}")
    return bundle


def load_index(index_path: Path, corpus_path: Path) -> dict:
    if not index_path.exists():
        print(f"No index at {index_path} — building now …\n")
        return build_index(corpus_path, index_path)
    with index_path.open("rb") as f:
        bundle = pickle.load(f)
    m = bundle["meta"]
    print(f"Index loaded  ({m['article_count']:,} articles, {m['vocab_size']:,} vocab terms)")
    return bundle


# ---------------------------------------------------------------------------
# Query — direct
# ---------------------------------------------------------------------------

def query_direct(phrase: str, bundle: dict, top: int) -> None:
    index = bundle["index"]
    docs  = bundle["docs"]
    tokens = query_tokens(phrase)

    if len(tokens) == 1:
        # Single token: fast path
        tok = tokens[0]
        hits = index.get(tok, {})
        if not hits:
            print(f'No mentions of "{phrase}" found.')
            return
        ranked = sorted(hits.items(), key=lambda x: -len(x[1]))
        total_articles = len(ranked)
        total_mentions = sum(len(v) for v in hits.values())
        print(f'\n"{phrase}" — {total_mentions:,} mentions across {total_articles:,} articles\n')
        print(f"  {'Mentions':>8}  Article")
        print(f"  {'-'*8}  {'-'*50}")
        for pageid, positions in ranked[:top]:
            title = docs.get(pageid, {}).get("title", str(pageid))
            print(f"  {len(positions):>8}  {title}")
        if total_articles > top:
            print(f"  … and {total_articles - top} more")

    else:
        # Multi-token phrase: intersect docs and find co-occurring positions
        doc_sets = [set(index.get(t, {}).keys()) for t in tokens]
        common_docs = doc_sets[0].intersection(*doc_sets[1:])
        if not common_docs:
            print(f'No articles contain all tokens of "{phrase}".')
            return

        # Score by number of times all tokens appear within 10 words of each other
        scored: list[tuple[int, int]] = []
        for pageid in common_docs:
            fwd_doc = bundle["forward"][pageid]
            positions_per_tok = [index[t].get(pageid, []) for t in tokens]
            # Count anchor positions (first token) where all others are within 10 words
            count = 0
            for anchor in positions_per_tok[0]:
                if all(
                    any(abs(p - anchor) <= 10 for p in positions_per_tok[i])
                    for i in range(1, len(tokens))
                ):
                    count += 1
            if count > 0:
                scored.append((pageid, count))

        scored.sort(key=lambda x: -x[1])
        total = len(scored)
        print(f'\n"{phrase}" — phrase hits in {total:,} articles\n')
        print(f"  {'Hits':>6}  Article")
        print(f"  {'-'*6}  {'-'*50}")
        for pageid, count in scored[:top]:
            title = docs.get(pageid, {}).get("title", str(pageid))
            print(f"  {count:>6}  {title}")
        if total > top:
            print(f"  … and {total - top} more")


# ---------------------------------------------------------------------------
# Query — proximity
# ---------------------------------------------------------------------------

def query_proximity(phrase: str, bundle: dict, radius: int, top: int) -> None:
    index   = bundle["index"]
    forward = bundle["forward"]
    docs    = bundle["docs"]
    tokens  = query_tokens(phrase)

    # For proximity we use only the first token of a multi-word phrase as anchor
    anchor_tok = tokens[0]
    anchor_docs = index.get(anchor_tok, {})
    if not anchor_docs:
        print(f'"{phrase}" not found in index.')
        return

    cooccur: dict[str, dict] = defaultdict(lambda: {"count": 0, "dist_sum": 0})

    for pageid, anchor_positions in anchor_docs.items():
        doc_tokens = forward[pageid]
        doc_len = len(doc_tokens)
        for qpos in anchor_positions:
            lo = max(0, qpos - radius)
            hi = min(doc_len, qpos + radius + 1)
            for npos in range(lo, hi):
                if npos == qpos:
                    continue
                neighbour = doc_tokens[npos]
                if neighbour in STOP_WORDS or len(neighbour) < 3:
                    continue
                dist = abs(npos - qpos)
                cooccur[neighbour]["count"] += 1
                cooccur[neighbour]["dist_sum"] += dist

    # Drop the query token itself and its sub-tokens
    for t in tokens:
        cooccur.pop(t, None)

    if not cooccur:
        print(f'No neighbours found within radius {radius} of "{phrase}".')
        return

    ranked = sorted(
        cooccur.items(),
        key=lambda x: (-x[1]["count"], x[1]["dist_sum"] / x[1]["count"]),
    )

    total_anchor_mentions = sum(len(v) for v in anchor_docs.values())
    print(f'\nProximity neighbourhood of "{phrase}"')
    print(f'  radius={radius} words | anchor mentions={total_anchor_mentions:,} | '
          f'articles={len(anchor_docs):,}\n')
    print(f"  {'Co-occ':>7}  {'Avg dist':>8}  Term")
    print(f"  {'-'*7}  {'-'*8}  {'-'*40}")
    for term, stats in ranked[:top]:
        avg_dist = stats["dist_sum"] / stats["count"]
        print(f"  {stats['count']:>7,}  {avg_dist:>8.1f}  {term}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Positional corpus index — ghost term discovery")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--index",  type=Path, default=DEFAULT_INDEX)

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("build", help="Build and persist the index")

    q = sub.add_parser("query", help="Query the index")
    q.add_argument("term", nargs="+", help="Term or phrase to search for")
    q.add_argument("--radius", type=int, default=0,
                   help="Proximity radius in tokens (0 = direct lookup only)")
    q.add_argument("--top",    type=int, default=DEFAULT_TOP)

    args = parser.parse_args()

    if args.cmd == "build":
        build_index(args.corpus, args.index)

    elif args.cmd == "query":
        bundle = load_index(args.index, args.corpus)
        phrase = " ".join(args.term)
        print()
        query_direct(phrase, bundle, args.top)
        if args.radius > 0:
            print()
            query_proximity(phrase, bundle, args.radius, args.top)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
