# comic-cli

CLI tools for generating comic book frames, pages, and blog posts.

## Unified `comic` command

A single entry point that dispatches to all tools:

```bash
comic frame happy              # → comic-frame happy
comic page --notes day.md      # → comic-page --notes day.md
comic blog --list-styles       # → comic-blog --list-styles
comic qa page.png              # → comic-qa page.png
comic --help                   # list available subcommands
```

The individual `comic-*` commands still work standalone.

## Tools

| Command | Description |
|---------|-------------|
| `comic frame` | Generate a single portrait frame with one of 57 expressions or a custom prompt |
| `comic page` | Compose multi-panel comic pages from scenes JSON or timestamped notes |
| `comic blog` | Full pipeline: notes/topic &rarr; AI panels &rarr; composited pages &rarr; HTML blog |
| `comic qa` | Visual quality check using pixel analysis + Gemini vision |

## Libraries

| Module | Description |
|--------|-------------|
| `generate_portrait.py` | Core Gemini portrait generation engine (used by frame + page) |
| `portrait_tui.py` | Interactive terminal UI for portrait generation |
| `comic_splitter.py` | OpenCV panel detection &mdash; split existing comic pages into individual panels |
| `am_blog_build.py` | Blog build engine with gold-bordered styling and HTML templates |

## Quick start

```bash
pip install -r requirements.txt
```

### Generate a frame

```bash
comic frame happy
comic frame --prompt "lightbulb moment, eyes wide"
comic frame --list          # show all 57 expressions
```

### Build a comic page

```bash
comic page --notes day.md --frames 6 --title "Monday"
comic page --scenes scenes.json --layout morning
comic page --list-layouts   # show all layout presets
```

### Generate a blog post

```bash
comic blog --notes day.md --title "My Monday" --style comic
comic blog --topic "shipping a feature at 2am" --pages 2
comic blog --list-styles    # comic, manga, noir, retro, watercolor, sketch, pop-art
```

### QA a page

```bash
comic qa page.png
comic qa page1.png page2.png --fast
comic qa page.png --no-vision   # pixel checks only
```

## Page spec

Standard US comic book format: **6.625 x 10.25 in @ 300 DPI** = 1988 x 3075 px

## Layout presets

18 built-in layouts from splash pages to 9-panel grids. Layouts use weighted rows and columns for cinematic panel sizing.

```
splash-1    1 panel     morning     6 panels    story-7     7 panels
splash-2    2 panels    afternoon   7 panels    drama-8     8 panels
spread-3    3 panels    action-6    6 panels    grid-9      9 panels
classic-4   4 panels    feature-6   6 panels
feature-5   5 panels    dialogue-6  6 panels
```

## Dependencies

- **Pillow** &mdash; image composition
- **google-generativeai** &mdash; Gemini for frame generation and QA vision
- **opencv-python** &mdash; panel detection (comic_splitter)
- **rich + InquirerPy** &mdash; terminal UI

## API keys

- `GOOGLE_API_KEY` &mdash; Gemini (frame generation, QA)
- `KIE_API_KEY` &mdash; kie.ai / Nano Banana (comic-blog panel generation)
