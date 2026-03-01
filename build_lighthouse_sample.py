#!/usr/bin/env python3
"""Generate lighthouse sample pages — 2 styles × 2 locales = 4 composite images.

Captions are baked into the panel art by Gemini (no Pillow text overlays).
"""

import json, sys, os, time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "lib"))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from generate_portrait import PortraitGenerator
from am_blog_build import (
    composite_page, get_style, LAYOUTS,
    _strip_no_text, _build_caption_instructions,
)

CONFIG = json.loads(Path("~/Desktop/crabby/config.json").expanduser().read_text())
REFERENCE = CONFIG["reference"]
STYLES_IMG = CONFIG["styles"]
SCENES = json.loads((ROOT / "examples/locale-test.json").read_text())
LAYOUT = LAYOUTS["morning"]

OUT = ROOT / "site" / "lighthouse"

ES_CAPTIONS = [
    "El viejo farero sube la escalera de caracol por última vez.",
    "Prende el cerillo. La llama agarra. La luz vuelve al mar.",
    "Allá abajo, un barco encuentra el camino a casa.",
]
EN_CAPTIONS = [s["caption"] for s in SCENES]

gen = PortraitGenerator()

for style_name in ["noir-comic", "ligne-claire"]:
    style = get_style(style_name)
    character = style.get("character", "")
    suffix_raw = style["panel_suffix"]
    # Strip no-text directives — captions will be baked in by Gemini
    suffix = _strip_no_text(suffix_raw)

    # Generate panels per locale (captions are baked into art)
    for locale, captions in [("en", EN_CAPTIONS), ("es", ES_CAPTIONS)]:
        panels_dir = OUT / f"panels-{style_name}"
        panels_dir.mkdir(parents=True, exist_ok=True)
        gen.output_dir = panels_dir

        panel_paths = []
        for i, scene in enumerate(SCENES):
            pid = scene["id"]
            out_name = f"panel_{pid:02d}_{locale}.png"
            out_path = panels_dir / out_name

            if out_path.exists():
                print(f"  ↷ [{style_name}/{locale}] Panel {pid} exists, skipping")
                panel_paths.append(out_path)
                continue

            # Build prompt with caption instructions for Gemini
            caption_fragment = _build_caption_instructions(captions[i], i, style)
            parts = [p for p in [character, scene["prompt"], suffix] if p]
            full_prompt = "\n\n".join(parts) + caption_fragment

            print(f"  → [{style_name}/{locale}] Generating panel {pid}...")
            result = gen.generate_portrait(REFERENCE, STYLES_IMG, full_prompt, output_name=out_name)
            if result:
                panel_paths.append(Path(result))
                print(f"  ✓ [{style_name}/{locale}] Panel {pid} done")
            else:
                print(f"  ✗ [{style_name}/{locale}] Panel {pid} failed")
                panel_paths.append(out_path)
            time.sleep(2)

        # Composite page (no caption overlay — captions are in the panel art)
        page_path = OUT / f"{style_name}_{locale}.png"
        composite_page(panel_paths, LAYOUT, page_path, captions=[], style=style)

print(f"\n✓ Done → {OUT}")
