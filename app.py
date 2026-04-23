"""WIF v1 — Wikipedia Institutional Fetishism
Interactive exploration of ghost category connections.

Two-term connection explorer: enter two terms, see which articles mention both,
with character distance between mentions. Demonstrates the collision finding.
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
from fasthtml.common import *

# ============================================================================
# Data Loading
# ============================================================================

GHOST_MENTIONS_PATH = Path(__file__).parent / "output" / "ghost_mentions.jsonl"
CORPUS_PATH = Path(__file__).parent / "data" / "wwi_extended.jsonl"

# Index: {term_lower: {pageid: {"title": str, "mentions": [...]}}}
ghost_index: dict[str, dict[int, dict]] = defaultdict(lambda: defaultdict(dict))


def load_ghost_mentions() -> None:
    """Load pre-computed ghost mentions into memory."""
    if not GHOST_MENTIONS_PATH.exists():
        print(f"⚠️  {GHOST_MENTIONS_PATH} not found. Ghost term search will be unavailable.")
        return

    with open(GHOST_MENTIONS_PATH) as f:
        for line in f:
            record = json.loads(line.strip())
            term = record["ghost_term"].lower()
            pageid = record["pageid"]
            title = record["title"]
            mentions = record["positions"]

            if pageid not in ghost_index[term]:
                ghost_index[term][pageid] = {
                    "title": title,
                    "mentions": mentions,
                }

    print(f"✓ Loaded {len(ghost_index)} ghost terms from {GHOST_MENTIONS_PATH}")
    for term, pages in ghost_index.items():
        print(f"  {term}: {len(pages)} articles")


def find_shared_articles(term1: str, term2: str) -> list[dict]:
    """Find articles mentioning both terms, with distance analysis.

    Returns list of {
        "title": str,
        "pageid": int,
        "distance": int (chars between closest mentions),
        "distance_label": "directly adjacent" | "same section" | "structurally separate",
        "mentions": [{"term": str, "context": str, "pos": int}, ...]
    }
    """
    term1_lower = term1.lower()
    term2_lower = term2.lower()

    if term1_lower not in ghost_index or term2_lower not in ghost_index:
        return []

    # Find shared pageids
    pages1 = set(ghost_index[term1_lower].keys())
    pages2 = set(ghost_index[term2_lower].keys())
    shared = pages1 & pages2

    results = []
    for pageid in shared:
        mentions1 = ghost_index[term1_lower][pageid]["mentions"]
        mentions2 = ghost_index[term2_lower][pageid]["mentions"]
        title = ghost_index[term1_lower][pageid]["title"]

        # Find closest pair of mentions (min distance)
        min_distance = float("inf")
        best_pair = None

        for m1 in mentions1:
            for m2 in mentions2:
                distance = abs(m1["start"] - m2["start"])
                if distance < min_distance:
                    min_distance = distance
                    best_pair = (m1, m2)

        if best_pair is None:
            continue

        m1, m2 = best_pair
        distance = abs(m1["start"] - m2["start"])

        # Classify distance
        if distance < 300:
            label = "directly adjacent"
        elif distance < 1000:
            label = "same section"
        else:
            label = "structurally separate"

        results.append({
            "title": title,
            "pageid": pageid,
            "distance": distance,
            "distance_label": label,
            "mention1": {"context": m1["context"], "term": term1},
            "mention2": {"context": m2["context"], "term": term2},
        })

    # Sort by distance (closest first)
    results.sort(key=lambda r: r["distance"])
    return results


# ============================================================================
# FastHTML App
# ============================================================================

app, rt = fast_app(
    title="WIF — Ghost Categories Explorer",
    css="""
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: #f7f5f0;
            color: #1a1a1a;
            line-height: 1.6;
            padding: 2rem 1rem;
        }
        main {
            max-width: 720px;
            margin: 0 auto;
        }
        h1 {
            font-family: Georgia, serif;
            font-size: 2.2rem;
            font-weight: normal;
            margin-bottom: 0.5rem;
            letter-spacing: -0.01em;
        }
        h1 small {
            display: block;
            font-size: 0.5em;
            font-weight: normal;
            color: #666;
            margin-top: 0.2rem;
        }
        .intro {
            color: #555;
            margin-bottom: 2rem;
            font-size: 0.95rem;
        }
        form {
            background: white;
            padding: 1.5rem;
            border: 1px solid #ddd;
            margin-bottom: 2rem;
        }
        .form-group {
            margin-bottom: 1.2rem;
        }
        .form-group:last-child {
            margin-bottom: 0;
        }
        label {
            display: block;
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 0.4rem;
            color: #333;
        }
        input[type="text"] {
            width: 100%;
            padding: 0.8rem;
            font-size: 1rem;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-family: inherit;
        }
        input[type="text"]:focus {
            outline: none;
            border-color: #2d3a8c;
            box-shadow: 0 0 0 3px rgba(45, 58, 140, 0.1);
        }
        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.8rem;
        }
        .chip {
            background: #e8e6e0;
            padding: 0.4rem 0.8rem;
            border: 1px solid #d0cdc4;
            border-radius: 20px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .chip:hover {
            background: #2d3a8c;
            color: white;
            border-color: #2d3a8c;
        }
        button {
            background: #2d3a8c;
            color: white;
            padding: 0.8rem 1.5rem;
            font-size: 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover {
            background: #1f2557;
        }
        .ghost-terms {
            margin-bottom: 2rem;
            padding: 1.2rem;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .ghost-terms h3 {
            font-size: 0.9rem;
            font-weight: 600;
            color: #666;
            margin-bottom: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        #results {
            min-height: 0;
        }
        .result-card {
            background: white;
            padding: 1.5rem;
            border-left: 4px solid #2d3a8c;
            margin-bottom: 1.5rem;
            border-radius: 4px;
        }
        .result-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .distance-label {
            display: inline-block;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 0.3rem 0.8rem;
            border-radius: 3px;
            margin-bottom: 1rem;
        }
        .distance-adjacent {
            background: #d4edda;
            color: #155724;
        }
        .distance-section {
            background: #fff3cd;
            color: #856404;
        }
        .distance-separate {
            background: #f8d7da;
            color: #721c24;
        }
        .context-block {
            background: #f9f7f4;
            padding: 0.8rem;
            border-radius: 3px;
            margin-bottom: 0.8rem;
            font-size: 0.9rem;
            font-family: 'Courier New', monospace;
            line-height: 1.5;
            color: #333;
        }
        .context-block strong {
            color: #2d3a8c;
            font-weight: 600;
        }
        .no-results {
            padding: 2rem;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            text-align: center;
            color: #666;
        }
        .error {
            padding: 1.2rem;
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 4px;
            color: #721c24;
            margin-bottom: 2rem;
        }
        footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #ddd;
            font-size: 0.85rem;
            color: #666;
            text-align: center;
        }
    """,
)


@rt("/")
def homepage():
    """Homepage with search form and ghost term chips."""
    ghost_terms = sorted(list(ghost_index.keys()))

    return Main(
        H1(
            "Ghost Categories Explorer",
            Small("Wikipedia's empty official categories revealed"),
        ),
        Div(
            P(
                "Wikipedia has official categories for central WWI concepts that return "
                "<strong>zero members</strong> from the API. Yet these concepts are "
                "widespread in the corpus. Enter two terms to see which articles mention "
                "both simultaneously — and measure how structurally separate they appear."
            ),
            cls="intro",
        ),
        Form(
            Div(
                Label("First term", For="term1"),
                Input(
                    type="text",
                    id="term1",
                    name="term1",
                    placeholder="e.g., Lenin",
                    autocomplete="off",
                ),
                cls="form-group",
            ),
            Div(
                Label("Second term", For="term2"),
                Input(
                    type="text",
                    id="term2",
                    name="term2",
                    placeholder="e.g., Assassination of Archduke Franz Ferdinand",
                    autocomplete="off",
                ),
                cls="form-group",
            ),
            Button("Search", type="submit", hx_post="/search", hx_target="#results"),
            hx_post="/search",
        ),
        Div(
            H3("Ghost Terms (indexed)"),
            Div(
                *[
                    Span(
                        term.title(),
                        cls="chip",
                        onclick=f"""
                            document.getElementById('term1').value = '{term.replace("'", "\\'")}';
                            document.getElementById('term1').focus();
                        """,
                    )
                    for term in ghost_terms
                ],
                cls="chips",
            ),
            cls="ghost-terms",
        ) if ghost_terms else None,
        Div(id="results"),
        Footer(
            P(
                Span("See ", cls=""),
                A("CLAUDE.md", href="https://github.com/darthcoder/wif/blob/master/CLAUDE.md"),
                Span(" for developer documentation and analysis details.", cls=""),
            ),
        ),
    )


@rt.post("/search")
def search(term1: str = "", term2: str = ""):
    """Search for shared articles between two terms."""
    term1 = term1.strip()
    term2 = term2.strip()

    if not term1 or not term2:
        return Div(
            "Please enter both terms.",
            cls="error",
        )

    if term1.lower() == term2.lower():
        return Div(
            "Please enter two different terms.",
            cls="error",
        )

    results = find_shared_articles(term1, term2)

    if not results:
        return Div(
            f"No articles mention both <strong>{term1}</strong> and <strong>{term2}</strong> simultaneously.",
            cls="no-results",
        )

    cards = []
    for r in results:
        distance_class = {
            "directly adjacent": "distance-adjacent",
            "same section": "distance-section",
            "structurally separate": "distance-separate",
        }[r["distance_label"]]

        card = Div(
            Div(r["title"], cls="result-title"),
            Span(
                f"{r['distance']} chars — {r['distance_label']}",
                cls=f"distance-label {distance_class}",
            ),
            Div(
                Span(
                    Strong(f"{r['mention1']['term']}: "),
                    f'"{r["mention1"]["context"]}"',
                ),
                cls="context-block",
            ),
            Div(
                Span(
                    Strong(f"{r['mention2']['term']}: "),
                    f'"{r["mention2"]["context"]}"',
                ),
                cls="context-block",
            ),
            cls="result-card",
        )
        cards.append(card)

    return Div(*cards)


def main():
    """Entry point for CLI."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    load_ghost_mentions()
    main()
