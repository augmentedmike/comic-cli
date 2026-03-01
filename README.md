# comic-cli

CLI toolchain for generating AI-powered comic book panels, pages, and blog posts. Art generation uses Google Gemini with reference-image likeness matching. Captions render in any language.

Part of the [AugmentedMike](https://github.com/augmentedmike) project family:

- [**am-blog**](https://github.com/augmentedmike/am-blog) — The comic strip blog itself
- [**MiniClaw**](https://miniclaw.bot) — AI assistant that runs on your computer
- [**Bonsai**](https://usebonsai.org) ([repo](https://github.com/augmentedmike/bonsai-app)) — AI-powered kanban for autonomous dev teams

---

## Example output

The "Lighthouse" test story rendered in two styles and two languages from the same [scene JSON](examples/locale-test.json):

| | noir-comic | ligne-claire |
|---|---|---|
| **English** | ![noir-comic EN](examples/lighthouse/noir-comic_en.png) | ![ligne-claire EN](examples/lighthouse/ligne-claire_en.png) |
| **Spanish** | ![noir-comic ES](examples/lighthouse/noir-comic_es.png) | ![ligne-claire ES](examples/lighthouse/ligne-claire_es.png) |

Same 3 panels, same reference photo, same layout. The only differences are the style config driving art direction + caption rendering, and the locale driving caption text.

Source files: [`examples/locale-test.json`](examples/locale-test.json) (scenes) / [`build_lighthouse_sample.py`](build_lighthouse_sample.py) (build script)

---

## How the pipeline works

```
                        ┌─────────────────────────┐
                        │  1. SCENE JSON           │
                        │  caption + prompt per     │
                        │  panel                    │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  2. PANEL GENERATION     │
                        │  reference photo          │
                        │  + style images           │
                        │  + character descriptor   │
                        │  + scene prompt           │
                        │  + art direction suffix   │
                        │  ──▶ Gemini API           │
                        │  ──▶ one PNG per panel    │
                        └────────────┬────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────▼──────────┐ ┌────────▼────────┐  ┌─────────▼─────────┐
   │  3a. EN CAPTIONS    │ │  3b. ES CAPTIONS │  │  3c. FR CAPTIONS  │
   │  (original)         │ │  (translated or  │  │  (translated or   │
   │                     │ │   manual override)│  │   manual override)│
   └──────────┬──────────┘ └────────┬────────┘  └─────────┬─────────┘
              │                     │                      │
   ┌──────────▼──────────┐ ┌───────▼─────────┐  ┌────────▼─────────┐
   │  4a. COMPOSITE      │ │  4b. COMPOSITE   │  │  4c. COMPOSITE   │
   │  panels + layout    │ │  same panels     │  │  same panels     │
   │  + EN caption boxes │ │  + ES caption    │  │  + FR caption    │
   │  ──▶ page_en.png    │ │  ──▶ page_es.png │  │  ──▶ page_fr.png │
   └─────────────────────┘ └──────────────────┘  └──────────────────┘
```

Art is generated **once**. Each locale gets its own composited page with translated captions burned into the same panels. The style config controls both the Gemini art direction prompt and the caption box rendering (font, colors, borders, positioning).

### What the style config controls

Each style in [`lib/am_blog_build.py`](lib/am_blog_build.py) is a dict that drives the entire visual pipeline:

| Field | What it does |
|-------|-------------|
| `panel_suffix` | Art direction appended to every Gemini prompt |
| `character` | Character descriptor prepended to prompts (used with reference photo) |
| `palette` | Named RGB colors for the style's visual language |
| `page_bg` | Page background color |
| `panel_border` | Panel border color |
| `caption.bg` / `bg_opacity` | Caption box fill and transparency |
| `caption.border_color` / `border_edges` | Border color and which edges to draw (all, or selective `["top", "bottom"]`) |
| `caption.accent_color` / `accent_width` | Left-edge accent bar |
| `caption.text_color` / `shadow_color` | Text and shadow colors (`None` to disable shadow) |
| `caption.text_transform` | `"uppercase"` to enforce ALL CAPS, or `None` |
| `caption.letter_spacing` | Per-character tracking in pixels |
| `caption.line_height` | Line height multiplier |
| `caption.font_sizes` | Adaptive sizing: `{1: 52, 2: 44, 3: 38}` maps line count to font size |
| `caption.position` | `"flush"` (edge-aligned) or `"inset"` (padded from panel edge) |
| `caption.max_width_ratio` | Max caption width as fraction of panel width |
| `caption.font_paths` | Font files in preference order with optional TTC index |

Built-in styles: `ligne-claire`, `noir-comic`, `manga`, `retro`

---

## Setup

```bash
git clone https://github.com/augmentedmike/comic-cli.git
cd comic-cli
pip install -r requirements.txt
```

Copy the example env file and add your API keys:

```bash
cp .env.example .env
# Edit .env with your keys
```

Create a config file for frame/page generation:

```bash
mkdir -p ~/.config/comic-cli
cp examples/config.example.json ~/.config/comic-cli/config.json
# Edit config.json with paths to your reference photo and style images
```

### API keys

| Key | Used by | Get it |
|-----|---------|--------|
| `GOOGLE_API_KEY` | comic-frame, comic-page, comic-qa, translation | [Google AI Studio](https://aistudio.google.com/apikey) |
| `KIE_API_KEY` | comic-blog (Nano Banana backend) | [kie.ai](https://kie.ai/api-key) |

### Config file

The config tells comic-frame and comic-page where to find your reference photo and art style images:

```json
{
  "reference": "/path/to/your/reference-photo.png",
  "styles": [
    "/path/to/style-image-1.jpeg",
    "/path/to/style-image-2.jpeg"
  ],
  "output_dir": "~/Desktop/comic-output",
  "env_file": "/path/to/.env",
  "generator_path": "/path/to/directory/containing/generate_portrait.py"
}
```

## Usage

### Unified `comic` command

```bash
comic frame happy              # generate a single expression frame
comic page --scenes story.json # build a comic page from scenes
comic blog --notes day.md      # full blog pipeline
comic qa page.png              # visual quality check
comic --help                   # list all subcommands
```

### Generate a frame

```bash
comic frame happy
comic frame --prompt "lightbulb moment, eyes wide"
comic frame --list                    # show all 57 expressions
```

### Build a comic page

```bash
comic page --scenes scenes.json --layout morning
comic page --notes day.md --frames 6 --title "Monday"
comic page --compose-only panels/ --layout spread-3
comic page --list-layouts
```

### Localized pages

Generate the same comic in multiple languages. Art is generated once, captions are translated via Gemini and composited per locale:

```bash
comic page --scenes scenes.json --locale en,es
comic page --scenes scenes.json --locale en,es,fr --source-locale en
comic blog --notes day.md --locale en,es --title "My Monday"
```

Output:

```
comic-2026-02-26-p1_en.png   # English captions
comic-2026-02-26-p1_es.png   # Spanish captions
index_en.html                 # English blog
index_es.html                 # Spanish blog
```

#### Manual translation overrides

You can provide manual translations in scene JSON instead of (or alongside) AI translation:

```json
{
  "caption": "The machine wakes up.",
  "caption_es": "La maquina despierta.",
  "prompt": "..."
}
```

Or as a nested object:

```json
{
  "caption": "The machine wakes up.",
  "captions": { "en": "The machine wakes up.", "es": "La maquina despierta." },
  "prompt": "..."
}
```

Or bulk at the post level (for am-blog format):

```json
{
  "panels": [...],
  "captions_es": ["Caption 1 in Spanish", "Caption 2 in Spanish"]
}
```

AI translation fills any gaps automatically.

### Generate a blog post

```bash
comic blog --notes day.md --title "My Monday" --style comic
comic blog --topic "shipping a feature at 2am" --pages 2
comic blog --scenes story.json --locale en,es
comic blog --list-styles         # comic, manga, noir, retro, watercolor, sketch, pop-art
comic blog --list-layouts
```

### QA a page

```bash
comic qa page.png
comic qa page1.png page2.png --fast
comic qa page.png --no-vision    # pixel checks only, no API call
comic qa page.png --json         # machine-readable metrics
```

### Run the lighthouse test

Regenerate the sample pages from scratch to test style + locale changes:

```bash
python3 build_lighthouse_sample.py
```

This generates 4 composite page images (2 styles x 2 locales) into `site/lighthouse/` using your reference photo and the scenes from [`examples/locale-test.json`](examples/locale-test.json). Existing panels are cached — delete `site/lighthouse/panels-*` to force regeneration.

## Scene JSON format

```json
[
  {
    "id": 1,
    "caption": "Caption text shown in the panel",
    "prompt": "Full scene description for image generation"
  }
]
```

Tips for good prompts:
- Describe the character explicitly in every panel (appearance, clothing, expression)
- Include the scene environment, camera angle, and lighting
- Reference your art style (the style images guide this too)
- See [`examples/locale-test.json`](examples/locale-test.json) for a working 3-panel example

## Page spec

Standard US comic book format: **6.625 x 10.25 in @ 300 DPI** = 1988 x 3075 px

## Layout presets

18 built-in layouts from splash pages to 9-panel grids. Layouts use weighted rows and columns for cinematic panel sizing:

```
splash-1    1 panel     morning     6 panels    story-7     7 panels
splash-2    2 panels    afternoon   7 panels    drama-8     8 panels
spread-3    3 panels    action-6    6 panels    grid-9      9 panels
classic-4   4 panels    feature-6   6 panels
feature-5   5 panels    dialogue-6  6 panels
```

Custom layouts via inline spec: `--layout "2:[1] | 1:[1,1] | 1:[1,2]"`

## Project structure

```
bin/
  comic              Unified dispatcher
  comic-frame        Single portrait frame generator
  comic-page         Multi-panel page compositor
  comic-blog         Full pipeline: input -> panels -> pages -> HTML
  comic-qa           Visual quality checker (pixel + Gemini vision)

lib/
  generate_portrait.py   Gemini image generation engine
  translate.py           Batch caption translation via Gemini
  am_blog_build.py       Blog build engine + style definitions
  portrait_tui.py        Interactive terminal UI
  comic_splitter.py      OpenCV panel detector

fonts/
  BebasNeue-Regular.ttf  Caption font for ligne-claire style

examples/
  config.example.json    Config file template
  001-day-one.json       Sample post JSON
  locale-test.json       Lighthouse test scenes (3 panels)
  lighthouse/            Generated sample pages (2 styles x 2 locales)

build_lighthouse_sample.py   Style + locale test runner

tests/
  test_comic_dispatcher.py   Dispatcher tests
  test_translate.py          Translation module tests
```

## Dependencies

```
Pillow              Image composition
google-generativeai Gemini API (art generation, translation, QA vision)
python-dotenv       .env file loading
rich                Terminal UI
InquirerPy          Interactive prompts
opencv-python       Panel detection (comic_splitter)
numpy               OpenCV dependency
```

## Tests

```bash
python -m pytest tests/ -v
```

## License

MIT
