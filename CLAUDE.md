# comic-cli

CLI toolchain for generating AI-powered comic book frames, pages, and blog posts.

## Architecture Overview

```
bin/
  comic           # Unified dispatcher — routes `comic <subcmd>` to `comic-<subcmd>`
  comic-frame     # Single portrait frame generator (Gemini via generate_portrait.py)
  comic-page      # Multi-panel comic page compositor (Gemini via generate_portrait.py)
  comic-blog      # Full pipeline: notes/topic → AI panels → pages → HTML blog (Nano Banana / kie.ai)
  comic-qa        # Visual QA: pixel checks + Gemini vision analysis

lib/
  generate_portrait.py   # Core Gemini image generation engine (PortraitGenerator class + 57 EXPRESSIONS)
  portrait_tui.py        # Interactive terminal UI (Rich + InquirerPy) wrapping PortraitGenerator
  comic_splitter.py      # OpenCV panel detector — splits existing comic images into individual panels
  am_blog_build.py       # Blog build engine: post JSON → Gemini panels → composite page → HTML (gold/noir theme)

examples/
  001-day-one.json       # Sample post JSON for am_blog_build.py

tests/
  test_comic_dispatcher.py  # Tests for the `comic` dispatcher (pytest)
```

## Two Distinct Image Generation Backends

### 1. Gemini (Google) — used by `comic-frame`, `comic-page`, `comic-qa`, `am_blog_build.py`
- **API**: `google-generativeai` SDK
- **Model**: `gemini-3-pro-image-preview` (image generation), `gemini-2.0-flash` / `gemini-1.5-flash` (QA vision)
- **Auth**: `GOOGLE_API_KEY` env var (fallback: `~/Desktop/youtube-channel/.env`)
- **How it works**: Sends reference person image + style images + prompt → gets back generated portrait
- **Config**: `~/Desktop/crabby/config.json` (shared by comic-frame and comic-page)
  - `reference` — path to person reference photo
  - `styles` — array of paths to art style reference images
  - `output_dir` — where generated images go
  - `generator_path` — path to directory containing generate_portrait.py (added to sys.path)
  - `env_file` — path to .env file with GOOGLE_API_KEY

### 2. Nano Banana / kie.ai — used by `comic-blog`
- **API**: REST API at `https://api.kie.ai` (wraps Nano Banana = Gemini 2.5 Flash image model)
- **Auth**: `KIE_API_KEY` env var or `~/.config/comic-blog/config.json`
- **How it works**: Creates async task with prompt + image_size → polls until complete → downloads result URL
- **No reference photos needed** — pure text-to-image generation
- **Config**: `~/.config/comic-blog/config.json`
  - `character` — text description of the character (default: "Crabby, a sharp-witted tech entrepreneur...")
  - `style` — art style name (comic, manga, noir, retro, watercolor, sketch, pop-art)
  - `model` — `google/nano-banana`
  - `output_dir` — default `~/Desktop/comic-blog`

## Comic Page Spec

Standard US comic book format: **6.625 x 10.25 in @ 300 DPI** = 1988 x 3075 px

Constants (shared across comic-blog, comic-page, am_blog_build):
- `PAGE_W = 1988`, `PAGE_H = 3075`
- `MARGIN = 48`, `GUTTER = 18`, `BORDER_W = 4`, `CAPTION_H = 72` (80 in am_blog_build)

## Layout System

Layouts are `List[Tuple[int, List[int]]]` — each tuple is `(row_height_weight, [col_weights])`.
Weights are relative: a row weight of 2 gets twice the height of weight 1.

18 built-in presets across the tools:
```
splash-1    1 panel      morning     6 panels     story-7     7 panels
splash-2    2 panels     afternoon   7 panels     drama-8     8 panels
spread-3    3 panels     action-6    6 panels     grid-9      9 panels
grid-4      4 panels     feature-6   6 panels
classic-4   4 panels     dialogue-6  6 panels
feature-5   5 panels     grid-6      6 panels (comic-page only)
```

Auto-selection: `_CINEMATIC_DEFAULTS` maps panel count → best layout name.
For 2-page spreads, page 1 defaults to "morning", page 2 to "afternoon".

## Tool Details

### `comic` (bin/comic) — Dispatcher
- Discovers `comic-*` executables in the same directory
- Falls back to `shutil.which()` for PATH-installed tools
- Uses `os.execvp()` to hand off execution

### `comic-frame` (bin/comic-frame) — Single Frame Generator
- Wraps `PortraitGenerator` from `lib/generate_portrait.py`
- 57 predefined expressions (happy, angry, smirking, triumphant, etc.)
- Outputs a single PNG to the configured output_dir
- `--cache` skips regeneration if file exists
- `--list` shows all expressions
- `--prompt` for custom prompts (hashed filename)
- Requires `~/Desktop/crabby/config.json` with reference/styles/generator_path

### `comic-page` (bin/comic-page) — Multi-Panel Page Generator
- Input: `--scenes FILE.json` or `--notes FILE.md` or `--compose-only DIR`
- Notes format: `HH:MM | text` per line
- Auto-selects most story-worthy entries via tiered priority:
  1. First + last entries (narrative bookends)
  2. Business events: `[CLIENT CLOSED]`, `[PIPELINE]`, `[LEAD]`, `[POTENTIAL CLOSE]`
  3. Ideas: lines starting with `idea:`
  4. Fill from remaining entries
- Converts entries to scene prompts with mood detection (keywords → mood mapping)
- `--scaffold` creates a starter scenes JSON template
- `--compose-only DIR` skips generation, composites existing `panel_NN.png` files
- `--pages N` splits panels across multiple pages
- Supports inline layout specs: `'2:[1] | 1:[1,1] | 1:[1,2]'`
- Requires `~/Desktop/crabby/config.json`

### `comic-blog` (bin/comic-blog) — Full Blog Pipeline
- Input: `--notes FILE.md` or `--topic "text"` or `--scenes FILE.json`
- Uses Nano Banana API (not Gemini directly) — no reference photos needed
- 7 art styles: comic, manga, noir, retro, watercolor, sketch, pop-art
- Pipeline: parse input → build prompts → generate panels via kie.ai → composite pages → generate HTML
- Panel aspect ratio auto-detected from layout rect dimensions
- HTML output: dark theme, Comic Sans font, style tag badge
- `--no-html` skips HTML generation
- Config: `~/.config/comic-blog/config.json`

### `comic-qa` (bin/comic-qa) — Quality Checker
- **Pixel checks** (no API): aspect ratio, resolution, color variance
- **Vision QA** (Gemini): panel layout, stretching, character consistency, art style, text readability
- Multi-page comparison support
- `--fast` for short 2-3 sentence report
- `--no-vision` for pixel-only checks
- `--json` for machine-readable pixel metrics
- Scores: PASS / WARN / FAIL per category, overall 1-10

### `am_blog_build.py` (lib/am_blog_build.py) — Blog Build Engine
- Input: post JSON files (see `examples/001-day-one.json`)
- Uses Gemini `gemini-3-pro-image-preview` directly (not kie.ai)
- Gold/noir visual theme (gold borders, near-black background)
- Caption boxes: Spawn/Vertigo lettering style — solid dark fill, white text, gold accent bar
- Alternating top/bottom caption placement (odd/even panel index)
- HTML template: "AugmentedMike" branded, Google Fonts (Bangers, Special Elite, Space Mono)
- Generates both individual post pages and an index page with card grid
- Cost tracking: ~$0.04/frame estimate
- `--deploy` flag: git add + commit + push + GitHub Pages API
- `--skip-generate` reuses existing panel images

### `comic_splitter.py` (lib/comic_splitter.py) — Panel Splitter
- **Reverse operation**: takes existing comic images → splits into individual panels
- Uses OpenCV: grayscale → Gaussian blur → adaptive threshold → contour detection
- Filters by area (`min_panel_size`), aspect ratio (0.1-10), and size vs full image
- Reading order sort: groups by row (vertical proximity), then left-to-right within row
- Enhancement modes: none (copy), basic (sharpen kernel), advanced (Real-ESRGAN placeholder)
- Pipeline: source/ → split/ (individual panels) + processed/ (enhanced)
- `--debug` saves intermediate images (gray, threshold, detected) to debug/

### `generate_portrait.py` (lib/generate_portrait.py) — Core Generation Engine
- `PortraitGenerator` class — initializes Gemini model, manages output dir
- `generate_portrait()`: person image + style images + prompt → generated portrait PNG
- Auto-increments filename if output exists
- `EXPRESSIONS` dict: 57 predefined expression prompts (e.g., 'happy', 'triumphant', 'mischievous')
- Standalone CLI: `--person`, `--style`, `--expression`/`--prompt`, `--model`
- `batch_generate()`: multiple prompts against same reference images

### `portrait_tui.py` (lib/portrait_tui.py) — Interactive TUI
- Rich console UI with InquirerPy prompts
- 3-step flow: select person image → select style images → choose expression/prompt
- Aspect ratio selection (1:1, 4:3, 3:4, 16:9, 9:16) with flip option
- Saves preferences to `.portrait_prefs.json` for quick-generate mode
- Quick mode: skip image selection, just pick expression and go

## Post JSON Format (am_blog_build.py)

```json
{
  "id": "001",
  "slug": "day-one",
  "title": "Day One",
  "subtitle": "The Machine Wakes Up",
  "date": "2026-02-22",
  "author": "AugmentedMike",
  "tags": ["origin", "identity"],
  "layout": "morning",
  "style": "noir-comic",
  "panels": [
    {
      "id": 1,
      "caption": "Caption text shown in the panel box",
      "prompt": "Full Gemini prompt for image generation"
    }
  ]
}
```

## Notes File Format (comic-page, comic-blog)

```
08:30 | Morning standup with the team
09:15 | Deep work session on auth module
10:00 | [CLIENT CLOSED — enterprise deal] Signed the contract!
12:00 | Lunch break, coffee run
14:30 | Idea: what if we added real-time collaboration?
16:00 | Shipped v2.1 to production
```

## Key Design Patterns

- **stdout = output paths only** — all tools print generated file paths to stdout, logging goes to stderr
- **Crop-to-fill compositing** — `ImageOps.fit()` preserves aspect ratio, no stretching
- **Two config systems**: `~/Desktop/crabby/config.json` (frame/page) vs `~/.config/comic-blog/config.json` (blog)
- **Duplicate code**: comic-page and comic-blog share layout definitions, compositor logic, and notes parsing but are independent implementations (not DRY)
- **No package install** — tools are standalone scripts, lib/ modules imported via sys.path manipulation

## Dependencies

```
Pillow>=10.2.0          # Image composition, all tools
google-generativeai>=0.8.0  # Gemini API (frame, page, qa, blog-build)
python-dotenv>=1.0.0    # .env file loading
rich>=13.7.0            # Terminal UI
InquirerPy>=0.3.4       # Interactive prompts (TUI)
opencv-python>=4.9.0    # Panel detection (splitter)
numpy>=1.26.0           # OpenCV dependency
```

## Running Tests

```bash
cd comic-cli && python -m pytest tests/ -v
```

Tests cover: help flags, subcommand discovery, unknown commands, dispatching to real tools (--list-styles, --list-layouts), and dispatching to a custom fake tool.
