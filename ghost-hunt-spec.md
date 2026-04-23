# Ghost Hunt — Two-Term Category Search Tool

## Overview
Interactive web app to surface connections between two category terms in a document corpus via graph traversal. Built on FastHTML + HTMX, deployed on Oracle Cloud Always Free tier.

## Deployment

- **Host**: DigitalOcean App Platform ($5/month)
- **Runtime**: Uvicorn on port 8000
- **Setup**: Connect GitHub repo to DO App Platform, auto-deploy on push
- **Startup**: `uvicorn app:app --host 0.0.0.0 --port 8000`
- **URL**: Auto-generated subdomain (e.g., `ghost-hunt-abc123.ondigitalocean.app`) or custom domain (~$1/month extra)

## Data Source

- **Format**: JSONL (one JSON object per line)
- **Schema**: `{ pageid, title, wikitext }`
- **Load**: Read from local file on startup
- **Size**: Expand as needed; current sample ~1.4M

## Core Algorithm: Path-Finding Between Terms

**Input**: Two search terms (e.g., "Russian Empire", "Bolshevik")

**Output**: Ranked list of connection paths with:
1. Path sequence (term1 → article1 → article2 → ... → term2)
2. Strength score (co-mention frequency, link density)
3. Intermediate article titles/links
4. Hop count

**Algorithm**:
1. Parse wikitext for `[[Category:...]]` and `[[...]]` wiki links
2. Build inverted indices on load:
   - `term → [article_ids]` (which articles mention this term)
   - `article_id → [terms]` (which terms appear in this article)
3. At query time, BFS from term1's articles to term2's articles
4. Track paths, rank by: co-mention count, intermediate link density, article prominence
5. Return top 5–10 paths

## Stack

**Backend**: FastHTML (Starlette async, native HTMX)
- Single route: `@app.post("/search")`
- Accepts `term1`, `term2` from form
- Returns HTML fragment (no JSON serialization)
- Components defined as Python functions

**Frontend**: HTML + HTMX (embedded in FastHTML)
- Form with two text inputs, search button
- Button triggers `hx-post="/search"` with form data
- Results swap into `#results` container via HTMX
- No page reloads

**Files**:
- `app.py` — FastHTML server, data loading, path-finding logic, routes
- `requirements.txt` — FastHTML, uvicorn
- `data/russian_corpus.jsonl` — Corpus file (not in repo; copy locally)

## Data Loading & Indexing

**On startup** (`app.py` main block):
1. Read JSONL, parse each record
2. Extract wiki links and categories from wikitext via regex: `\[\[([^\]]+)\]\]` and `\[\[Category:([^\]]+)\]\]`
3. Normalize terms (lowercase, strip whitespace)
4. Build dicts:
   ```python
   term_to_articles = {term: [article_ids]}
   article_to_terms = {article_id: [terms]}
   article_titles = {article_id: title}
   ```
5. Cache in module-level globals for O(1) lookup

**Performance**: Load runs once on startup (~1–2s for 1.4M). Queries are instant (BFS over graph).

## Routes

### `GET /`
Return HTML page with:
- Form (two text inputs, search button)
- Empty results container (`#results`)
- Minimal CSS (inline or `<style>` tag)

### `POST /search`
**Input** (form data): `term1`, `term2`

**Output**: HTML fragment (no `<html>` tags, just the result block)

**Logic**:
1. Validate inputs (non-empty, not identical)
2. Look up `term1` and `term2` in indices
3. If either missing, return "Term not found" message
4. Run BFS to find top paths
5. If no paths found, return "Terms too far apart" message
6. Render results as ordered list of path blocks:
   ```
   Path 1: Russian Empire → Tsar → Bolshevik (2 hops, strength: 0.87)
     Via: Russian Revolution article (pgid: 25762)
     Via: February Revolution article (pgid: 45137597)
   ```

## Result Display

Each result block shows:
- **Path sequence**: Term1 → [articles] → Term2
- **Metadata**: Hop count, strength score (0–1)
- **Source articles**: Clickable links to titles that bridge the connection
- **Raw connection**: "Both mentioned in [Article Title]" for direct co-mentions

## Error Handling

- Empty input: Disable search button until both fields filled (client-side)
- Term not found: "No articles match '[term]'. Try another."
- No path exists: "Terms are disconnected (max 5 hops searched)."
- Invalid input (non-ASCII, >100 chars): Reject silently, show validation message

## FastHTML Specifics

Use FastHTML's component syntax:

```python
from fasthtml.common import *

app, rt = fast_app()

@rt("/")
def homepage():
    return Titled(
        "Ghost Hunt",
        Form(
            Input(name="term1", placeholder="First term"),
            Input(name="term2", placeholder="Second term"),
            Button("Search", hx_post="/search", hx_target="#results"),
            hx_post="/search"
        ),
        Div(id="results")
    )

@rt.post("/search")
async def search(term1: str, term2: str):
    # Logic here
    return Div(
        H3("Results"),
        *[render_path(p) for p in paths]
    )
```

No template files. Components = functions.

## Development Workflow

1. **Local testing**: `uvicorn app:app --reload --port 8000`
2. **Push to GitHub**: Include `requirements.txt` and `.gitignore` (exclude `data/`)
3. **DigitalOcean deployment**: 
   - Create DO App Platform app, connect GitHub repo
   - Set runtime: Python 3.10+, command: `uvicorn app:app --host 0.0.0.0 --port 8000`
   - Add `data/` folder to app (upload JSONL via DO or via git)
   - Deploy on push
4. **Access**: Live at auto-generated subdomain immediately after first deploy

## Requirements

```
fasthtml
uvicorn
python>=3.10
```

## Notes

- No external APIs. All graph traversal runs in-process.
- Wikitext parsing is regex-based (simple extraction). For production, use `mwclient` or `mediawiki` library.
- BFS depth limit: 5 hops (tune for corpus size and performance)
- Path ranking: `strength = (co_mentions / total_articles) * link_density`
- Results cached in memory; restart app to refresh index

---

**Handoff to Code**: Build FastHTML app. Load JSONL, parse wiki links, build indices on startup. Implement BFS path-finding. Wire up form + search route. Test with two arbitrary terms. Deploy to DigitalOcean App Platform.
