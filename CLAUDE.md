# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Quick Start

**Install dependencies:**
```bash
uv sync
```

**Run the interactive web app:**
```bash
uv run uvicorn app:app --reload --port 8000
# Open http://localhost:8000
```

**Run the analysis pipeline:**
```bash
bash analysis/pipeline.sh
# Generates outputs in output/ directory
```

**Test a single analysis stage** (after generating outputs above):
```bash
# Test web app with existing data
uv run python -c "from app import ghost_index; print(f'Loaded {len(ghost_index)} terms')"
```

For detailed information, see sections below.

## Project Overview

**The Fetish of Structure** — an empirical analysis of Wikipedia's category hierarchy as institutional fetishism. The central finding: 51 of 88 searched categories return zero members from the Wikipedia API, yet reverse-hunting through article text finds those concepts everywhere. The hierarchy performs documentary completeness while making structural causality invisible.

This is a sub-project of `ner-paper` (parent directory: `../..`). It lives here because it shares the parent's corpus and Python environment but is a separate line of inquiry.

**Dependency note**: This project uses the parent project's `uv` environment. If running standalone, `uv sync` will install dependencies locally. The corpus file (`data/wwi_extended.jsonl`) must be available — it is typically symlinked from the parent project or provided separately (see "Data Files" section).

## Architecture & Data Flow

The analysis is a **three-stage pipeline** that progressively reveals the contradiction:

1. **Ghost Hunt** (`ghost_hunt.py`) — Find all mentions of officially-empty category terms in article text
   - Input: raw corpus wikitext or text (`../../data/wwi_extended.jsonl`)
   - Output: `output/ghost_mentions.jsonl` (every mention with position and context), `output/ghost_summary.json` (aggregated counts)
   - Purpose: Prove the concepts exist in the corpus despite empty API categories

2. **Dispersal Map** (`dispersal_map.py`) — Fetch the real Wikipedia categories for ghost-term articles
   - Input: `output/ghost_summary.json` (which articles mention ghost terms)
   - Fetches via Wikipedia API (with resumable caching in `output/category_cache.json`)
   - Output: `output/dispersal.json` (how many real categories scatter across ghost-term article set)
   - Purpose: Show these articles are scattered across unrelated real categories, never grouped together

3. **Collision Analysis** (`collision.py`) — Find articles mentioning multiple ghost terms
   - Input: `output/ghost_mentions.jsonl` (from stage 1)
   - Output: `output/collision.json` (co-occurrence matrix with character distances between mentions)
   - Purpose: Reveal whether different ghost narratives ever touch (they rarely do)

Each stage builds on outputs from previous stages. **Pipeline is idempotent** — re-running stages only recomputes that stage (stages 1 and 3 are fast; stage 2 uses cached API results when available).

## Running the Web App (v1)

Minimal FastHTML web app for interactive exploration of ghost category connections. Demonstrates the collision finding: when two ghost terms share articles, they appear in structurally separate narrative sections.

**Install dependencies:**
```bash
uv sync
```

**Start the app:**
```bash
uv run uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

**How it works:**
1. Enter two terms (e.g., "Lenin" and "Bolshevism")
2. App queries `output/ghost_mentions.jsonl` to find articles mentioning both terms simultaneously
3. Character distance between closest mentions is calculated and classified:
   - **Directly adjacent** (<300 chars) — in close proximity
   - **Same section** (<1000 chars) — same article section
   - **Structurally separate** (>1000 chars) — different narrative contexts with no causal link
4. Context windows (150 chars) shown for each mention
5. Click ghost term chips to pre-fill the search form

**Key test (the thesis finding):**
Search "Lenin" + "Assassination of Archduke Franz Ferdinand". Result: **Sergey Sazonov** article with distance ~2,684 chars (structurally separate). This demonstrates the core insight: the two central WWI narratives barely touch, connected only through a man who happened to be present at both moments.

### Web App Architecture (`app.py`)

The FastHTML app is a single-file implementation:

**Data loading** (lines 15–49):
- On startup, loads `output/ghost_mentions.jsonl` (pre-computed by `ghost_hunt.py`) into an in-memory index
- Index structure: `{term_lower: {pageid: {"title": str, "mentions": [...]}}}`
- Non-blocking: app starts even if the file is missing (displays warning)

**Search logic** (lines 51–115, `find_shared_articles()`):
- Takes two term strings, finds articles mentioning both
- Computes minimum character distance between any pair of mentions
- Classifies distances: <300 chars = "directly adjacent", <1000 = "same section", ≥1000 = "structurally separate"
- Returns sorted list of result dicts with title, distance, and both context windows

**Routes** (lines 313–445):
- `GET /` — renders the homepage with search form and clickable ghost term chips
- `POST /search` — processes form submissions, returns result cards via HTMX

**Styling** (lines 124–309):
- Inline CSS with a conservative serif/sans-serif palette
- Color-coded distance labels (green/yellow/red) for quick visual scanning
- Responsive to mobile (max-width 720px main container)

To modify the app: edit `app.py` directly, then restart uvicorn with `--reload` flag for hot reloading.

### Reading the Analysis Scripts

All analysis scripts share a common structure:

1. **Imports & constants** (top of file) — defines input/output paths, built-in ghost terms
2. **Core logic** — main functions that implement the stage (e.g., `find_mentions()` in ghost_hunt, `fetch_categories()` in dispersal)
3. **I/O handling** — JSON/JSONL read/write, error handling
4. **CLI entry point** (bottom) — `if __name__ == "__main__"` block with `argparse` for command-line arguments

Each script runs independently and can be imported for testing. They are designed to be idempotent: re-running a stage will recompute only that stage using the latest code, not rescan cached inputs from previous runs.

## Verifying Your Setup

After installing dependencies with `uv sync`, run these checks:

```bash
# 1. Check Python version
python --version  # Should be 3.11+

# 2. Verify dependencies
uv pip list | grep -E "fasthtml|uvicorn"

# 3. Check corpus file exists
ls -lh data/wwi_extended.jsonl  # Should be ~122 MB

# 4. Quick test: run ghost hunt on a small subset (or with custom terms)
uv run python analysis/ghost_hunt.py --terms "Lenin"

# 5. Quick test: start the web app (Ctrl+C to exit)
uv run uvicorn app:app --port 8000
# Then open http://localhost:8000 and test a search
```

If any of these fail, refer to the "Troubleshooting" section below.

## Platform & Environment Notes

**macOS/Linux**: All scripts run natively. The shell scripts use `bash` syntax.

**Windows**: 
- Python scripts (`.py`) run natively
- The `pipeline.sh` shell script requires WSL, Git Bash, or similar Unix environment
- Alternatively, run stages individually with Python: `uv run python analysis/ghost_hunt.py` etc.

**Dependencies** (from `pyproject.toml`):
- `python-fasthtml` — Web framework (used by `app.py` only)
- `uvicorn` — ASGI server (used by `app.py` only)
- No other dependencies; analysis scripts use only the standard library

The parent project's `uv` environment includes these. If working standalone, `uv sync` installs them.

## Running the Analysis Pipeline

To regenerate the analysis outputs:

### Setup & Verification

The corpus is self-contained in `./data/`. All scripts run via `uv`:

**Before running analysis, verify your setup:**
```bash
# Check dependencies are installed
uv sync

# Verify corpus file exists (required)
ls -lh data/wwi_extended.jsonl  # Must be ~122 MB

# Verify ghost mentions are loaded (optional, for web app)
ls -lh output/ghost_mentions.jsonl  # Will exist after first ghost hunt run
```

If the corpus file is missing, create a symlink from the parent project:
```bash
cd data/ && ln -s ../../../data/wwi_extended.jsonl . && cd ..
```

Then run any analysis script:
```bash
uv run python analysis/ghost_hunt.py
```

The `--corpus` flag overrides the default path if you need to work with a different corpus:

On Windows, `pipeline.sh` requires WSL or Git Bash.

## Analysis Scripts

### `analysis/ghost_hunt.py` — Ghost Term Search

Reverse-search: which corpus articles mention each officially-empty category term?

**Default behavior** (no arguments):
```bash
# When running from this project directory:
uv run python analysis/ghost_hunt.py

# Or with explicit project reference from parent:
uv run --project ../../ python analysis/ghost_hunt.py
```
Uses default corpus (`../../data/wwi_extended.jsonl`) and built-in ghost terms. The `--project ../../` flag is only needed if you're running from the parent directory.

**Custom corpus:**
```bash
uv run python analysis/ghost_hunt.py --corpus /path/to/corpus.jsonl
```

**Custom output directory:**
```bash
uv run python analysis/ghost_hunt.py --output-dir /path/to/output
```

**Custom ghost terms** (quote multi-word terms):
```bash
uv run python analysis/ghost_hunt.py --terms Persia Sazonov "July Crisis" Kurdistan
```

**Input corpus schema**: Accepts JSONL with either `wikitext` or `text` field. Must include `pageid` and `title`:
```json
{"pageid": 123, "title": "Article Title", "wikitext": "..."}
```

**Output: `ghost_mentions.jsonl`**
One record per (term, article) pair with mention positions:
```json
{
  "ghost_term": "Bolshevism",
  "pageid": 12345,
  "title": "Russian Revolution",
  "mention_count": 3,
  "positions": [
    {
      "start": 150,
      "end": 161,
      "context": "...The rise of Bolshevism in Eastern Europe was... (150 chars around mention)"
    }
  ]
}
```

**Output: `ghost_summary.json`**
Aggregated stats per ghost term:
```json
{
  "Bolshevism": {
    "article_count": 42,
    "total_mentions": 156
  },
  "Lenin": {
    "article_count": 18,
    "total_mentions": 67
  }
}
```

### `analysis/corpus_index.py` — Inverted Index + Proximity Search

Positional inverted index for fast lookup and semantic neighbourhood discovery. Build once, query repeatedly.

```bash
# Build index (run once, ~30s for 3,230 articles)
uv run python analysis/corpus_index.py build --corpus data/wwi_extended.jsonl

# Direct lookup — which articles mention a term?
uv run python analysis/corpus_index.py query Sazonov
uv run python analysis/corpus_index.py query "July Crisis"

# Proximity — what terms cluster within N words of this term?
uv run python analysis/corpus_index.py query Sazonov --radius 50
uv run python analysis/corpus_index.py query Persia --radius 30 --top 40
```

Index persists to `output/corpus_index.pkl`. Auto-builds on first query if missing.

The proximity mode uses Manhattan distance on token positions: for every mention of the query term, it collects all tokens within `--radius` words and ranks them by co-occurrence frequency × average proximity. This reveals the semantic neighbourhood of ghost terms without embeddings.

### `analysis/dispersal_map.py` — Category Scatter

For every article mentioning a ghost term, fetches all its actual Wikipedia categories and measures how widely the ghost-term article set disperses across the real category hierarchy.

```bash
uv run --project ../../ python analysis/dispersal_map.py
```

Output: `output/dispersal.json`, `output/category_cache.json` (API cache, resumable)

### `analysis/collision.py` — Co-occurrence and Narrative Distance

Finds articles mentioning two or more ghost terms simultaneously. Measures the minimum character distance between any mention of term A and any mention of term B. Distances > 1,000 characters are flagged as "structurally separate."

Key finding: Sergey Sazonov is the only article mentioning both the Assassination narrative and the Bolshevik narrative — with 2,684 characters between the two mentions and no causal link drawn.

```bash
uv run --project ../../ python analysis/collision.py
```

Output: `output/collision.json`

### `analysis/pipeline.sh` — Full Pipeline

Runs ghost hunt → dispersal → collision in sequence, then validates results against documented claims.

```bash
bash analysis/pipeline.sh
```

Or with custom corpus:
```bash
bash analysis/pipeline.sh /path/to/corpus.jsonl
```

The script includes a reconciliation step at the end that compares actual results against vault claims (documented expected values), useful for validation.

## Key Findings (as of April 2026)

- 51/88 categories return zero members (58%) — pattern maps onto event nodes vs. structural nodes
- Default ghost terms: `Assassination of Archduke Franz Ferdinand`, `Western Front`, `Bolshevism`, `Bolshevik`, `Lenin`, `Revolution`
- `Revolution`: 850 articles, 4,364 mentions — most pervasive ghost
- `Persia`: 190 articles, 939 mentions — structurally invisible despite being a real WWI theater
- 94% of corpus articles appear in exactly one of the 88 searched categories — near-total absence of structural overlap

## Project Structure

```
.
├── app.py                      # FastHTML web app (interactive search interface)
├── pyproject.toml              # Project metadata and dependencies
├── analysis/
│   ├── ghost_hunt.py          # Stage 1: Find mentions of ghost terms in corpus
│   ├── dispersal_map.py        # Stage 2: Fetch real categories for ghost-term articles
│   ├── collision.py            # Stage 3: Find co-occurrence patterns
│   ├── corpus_index.py         # Utility: Build positional inverted index
│   └── pipeline.sh             # Orchestrate all three stages + validation
├── data/
│   ├── wwi_extended.jsonl     # Input corpus (3,230 articles, ~122 MB)
│   └── 88_categories.json      # Reference: official 88-category map
└── output/ (gitignored)
    ├── ghost_mentions.jsonl    # Output of stage 1: all term mentions with positions
    ├── ghost_summary.json      # Output of stage 1: aggregated counts per term
    ├── dispersal.json          # Output of stage 2: category scatter analysis
    ├── collision.json          # Output of stage 3: co-occurrence matrix
    ├── category_cache.json     # Stage 2: Wikipedia API cache (resumable)
    └── corpus_index.pkl        # Utility: pickled inverted index
```

## Data Files

### Local Data

The `data/` directory contains:
- `wwi_extended.jsonl` — Complete WWI corpus (3,230 articles, 122 MB)
  - **Schema**: `{pageid, title, wikitext}` — raw wikitext (not cleaned)
  - **Format**: JSONL (one JSON object per line)
  - Ghost hunt also accepts a `text` field as an alternative to `wikitext`
- `88_categories.json` — Reference: the official 88-category map from Wikipedia (1,462 unique articles)

The corpus is self-contained here for independence; analysis scripts reference `./data/wwi_extended.jsonl` by default.

All analysis scripts accept a `--corpus` flag to override the default path if you need to work with a different corpus.

### Generated Outputs

Analysis scripts produce outputs in `output/` (gitignored):
- `ghost_mentions.jsonl` — All mentions of ghost terms with character positions
- `ghost_summary.json` — Aggregated stats per ghost term
- `dispersal.json` — Category scatter analysis
- `collision.json` — Co-occurrence matrix
- `category_cache.json` — Wikipedia API cache (resumable)
- `corpus_index.pkl` — Inverted index for the corpus (~50–100 MB, auto-generated)

## Design Patterns & Key Decisions

### Wikipedia API Caching & Resumability
`dispersal_map.py` fetches real categories for each ghost-term article via Wikipedia API. This is expensive (network calls) and rate-limited. The script caches results in `output/category_cache.json` and resumes from there if interrupted.

**If a run fails mid-way**: Re-run `dispersal_map.py` — it will pick up from where it left off in the cache file.

**If you want to re-fetch from scratch**: Delete `output/category_cache.json` before re-running (this will reset the API requests).

### Inverted Index & Proximity Semantics
`corpus_index.py` builds a positional inverted index: for each token, it stores which articles mention it and at what positions (token offsets, not character positions).

Proximity mode uses **Manhattan distance** on token positions: for a query term, it collects all tokens within `--radius` words and ranks them by co-occurrence frequency × average distance. This reveals semantic neighbourhoods without embeddings.

Example: `query Sazonov --radius 50` finds terms appearing within 50 tokens of "Sazonov" across all articles, ranked by how often they co-occur with Sazonov nearby.

### Why Three Stages vs. One Script?
- **Modularity**: Each stage asks a different question and produces a consumable output
- **Debuggability**: If stage 2 fails (API), you don't re-run stage 1
- **Reproducibility**: Each stage's output is a point in time; easy to compare old vs. new runs
- **Publication**: Each output file is a self-contained finding (ghost mentions, dispersal stats, collisions)

### Input Flexibility (wikitext vs. text)
Ghost hunt accepts corpus with either `wikitext` or `text` field. This allows working with both raw Wikipedia dumps and cleaned/preprocessed versions. The script gracefully degrades to empty string if neither field exists.

## Common Development Tasks

### Run the Full Pipeline
```bash
bash analysis/pipeline.sh
```

Or with a custom corpus:
```bash
bash analysis/pipeline.sh /path/to/my_corpus.jsonl
```

### Run a Single Stage
```bash
# Just ghost hunt (fast, ~5s for 3,230 articles)
uv run python analysis/ghost_hunt.py

# Just dispersal (calls Wikipedia API, respects cache)
uv run python analysis/dispersal_map.py

# Just collision (fast)
uv run python analysis/collision.py
```

### Resume Interrupted Dispersal (Stage 2)
If `dispersal_map.py` fails midway through API calls, the cache is preserved. Just re-run:
```bash
uv run python analysis/dispersal_map.py
```
It will skip already-cached articles and continue from where it left off.

### Clear Outputs & Re-run from Scratch
```bash
rm -rf output/
bash analysis/pipeline.sh
```

Or selectively clear one stage:
```bash
rm output/ghost_mentions.jsonl output/ghost_summary.json
uv run python analysis/ghost_hunt.py  # Re-runs stage 1 only
```

To completely reset dispersal caching:
```bash
rm output/category_cache.json output/dispersal.json
uv run python analysis/dispersal_map.py
```

### Query the Corpus Index
```bash
# Build index if missing (auto-builds on first query)
uv run python analysis/corpus_index.py build --corpus data/wwi_extended.jsonl

# Direct lookup (which articles mention a term?)
uv run python analysis/corpus_index.py query Sazonov
uv run python analysis/corpus_index.py query "July Crisis"

# Proximity search (what terms cluster near this term?)
uv run python analysis/corpus_index.py query Sazonov --radius 50
uv run python analysis/corpus_index.py query Sazonov --radius 50 --top 40
```

### Custom Ghost Terms
Edit the `GHOST_TERMS` list in `analysis/ghost_hunt.py`, then re-run:
```bash
uv run python analysis/ghost_hunt.py
```

Or pass via CLI (temporary override):
```bash
uv run python analysis/ghost_hunt.py \
    --terms "Your Term" "Another Term" "Multi-word Term"
```

### Change Output Directory
By default, all outputs go to `output/`. Override with `--output-dir`:
```bash
uv run python analysis/ghost_hunt.py --output-dir /tmp/results
```

## Troubleshooting

### Dispersal Run Hangs or Fails
The Wikipedia API has rate limits. If `dispersal_map.py` fails mid-run:
1. Wait a minute (API backoff)
2. Re-run: `uv run python analysis/dispersal_map.py`
3. It will resume from the cache (`output/category_cache.json`)

If it fails repeatedly, check `output/category_cache.json` exists and is readable. If corrupted, delete it:
```bash
rm output/category_cache.json
uv run python analysis/dispersal_map.py  # Re-fetches from scratch
```

### Corpus File Not Found
All scripts default to `data/wwi_extended.jsonl` (in this project directory). If it's elsewhere:
```bash
uv run python analysis/ghost_hunt.py --corpus /path/to/corpus.jsonl
```

Check the file exists: `ls -lh data/wwi_extended.jsonl` (should be ~122 MB). If missing and the parent project has it, create a symlink:
```bash
cd data/ && ln -s ../../../data/wwi_extended.jsonl . && cd ..
```

### Index Build Takes Forever
`corpus_index.py build` tokenizes 3,230 articles and builds a postings list (~30 seconds on typical hardware). This happens once; subsequent queries are instant.

If it hangs: 
- Check disk space (index pickle is ~50–100 MB)
- Verify `output/corpus_index.pkl` is being written
- Monitor process: `ls -lh output/corpus_index.pkl` in another terminal

### Output Files Missing or Incomplete
Check each stage completed successfully:
- **Stage 1**: `ghost_mentions.jsonl` and `ghost_summary.json` present
- **Stage 2**: `category_cache.json` and `dispersal.json` present (cache persists even if output write fails)
- **Stage 3**: `collision.json` present

If only `category_cache.json` exists but no `dispersal.json`, the API fetch completed but the summary didn't write. Re-run stage 2.

### Ghost Hunt Finds Zero Mentions
Check:
1. Corpus file exists and is readable: `ls -lh data/wwi_extended.jsonl` (should be ~122 MB)
2. Ghost terms match actual corpus text (case-insensitive search, but exact substring matching)
3. Corpus has `wikitext` or `text` field: `head -1 data/wwi_extended.jsonl | jq keys`

Try with a built-in term first:
```bash
uv run python analysis/ghost_hunt.py --terms "Lenin"
```

### Pipeline Validation Shows Discrepancies
`pipeline.sh` runs a reconciliation step comparing actual results to documented claims. Small differences are expected if corpus has been updated. Check the output summary:
```bash
bash analysis/pipeline.sh 2>&1 | tail -20
```
