#!/usr/bin/env python3
"""
am-blog build engine
Turns post JSON → Gemini panel images → comic page → HTML blog post

Usage:
  python3 build.py posts/001-day-one.json [--skip-generate] [--deploy]
"""

import argparse
import json
import os
import sys
import time
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# Pillow
try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    print("pip install pillow")
    sys.exit(1)

# Gemini
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    # Try project .env first, then standard config location
    for _env in [Path(__file__).parent.parent / ".env",
                 Path.home() / ".config" / "comic-cli" / ".env"]:
        if _env.exists():
            load_dotenv(_env)
            break
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
    GEMINI_OK = bool(api_key)
except ImportError:
    GEMINI_OK = False

# ---------------------------------------------------------------------------
# Comic page constants (US comic @ 300 DPI)
# ---------------------------------------------------------------------------
PAGE_W = 1988
PAGE_H = 3075
MARGIN = 48
GUTTER = 18
BORDER_W = 4
CAPTION_H = 80

# ---------------------------------------------------------------------------
# Style definitions — each style drives BOTH panel art AND caption box visuals
# ---------------------------------------------------------------------------

STYLES: Dict[str, dict] = {
    "ligne-claire": {
        # --- Art direction (appended to every Gemini panel prompt) ---
        "panel_suffix": (
            "Moebius / Hergé ligne claire style. Precise clean black ink outlines, "
            "flat unshaded color fields, zero gradients, zero crosshatching, zero ink wash. "
            "Geometric architectural backgrounds. Spacious negative space as a compositional "
            "element. European graphic novel aesthetic. "
            "Primary palette: near-black (#0D0D1A), warm amber (#C8843A), electric teal (#00E5FF). "
            "Secondary field colors: pale sky-blue (#C8E0F0) and warm sand (#E8D5A0). "
            "Clean linework, deliberate composition. "
            "NO text, NO captions, NO speech bubbles, NO watermarks — pure visual storytelling only."
        ),
        # --- Character descriptor (prepended to panel prompts when using reference) ---
        "character": (
            "Man, strong jaw, dark slightly tousled hair, black t-shirt. "
            "Electric teal eyes (#00E5FF), gently luminous. "
            "Ligne claire flat-color rendering — no detailed shading, "
            "color zones separated by clean precise ink lines only."
        ),
        # --- Named palette (hex → RGB, used by page chrome + HTML theme) ---
        "palette": {
            "near_black":    (13,  13,  26),     # #0D0D1A
            "warm_amber":    (200, 132, 58),     # #C8843A
            "electric_teal": (0,   229, 255),    # #00E5FF
            "pale_sky":      (200, 224, 240),    # #C8E0F0
            "warm_sand":     (232, 213, 160),    # #E8D5A0
            "gold":          (220, 180, 80),     # #DCB450
            "white":         (255, 255, 255),    # #FFFFFF
        },
        # --- Page chrome ---
        "page_bg":      (13,  13,  26),     # near-black
        "panel_border": (220, 180, 80),     # gold
        # --- Caption box ---
        "caption": {
            "bg":            (13,  13,  26),     # near-black, fully opaque
            "bg_opacity":    255,
            "border_color":  (220, 180, 80),     # gold
            "border_width":  2,                   # 1.5px spec → 2px at 300dpi
            "border_edges":  ["top", "bottom"],   # top + bottom only
            "accent_color":  (220, 180, 80),     # gold left bar
            "accent_width":  5,
            "corner_radius": 0,                   # sharp rectangular
            "text_color":    (255, 255, 255),    # white
            "shadow_color":  None,                # no shadow — clean ligne claire
            "text_transform": "uppercase",        # ALL CAPS enforced in code
            "letter_spacing": 3,                  # px between characters
            "line_height":    1.15,               # multiplier
            "font_sizes":     {1: 52, 2: 44, 3: 38},  # adaptive: lines → px
            "font_size_default": 38,              # 3+ lines
            "padding_x":     16,
            "padding_y":     10,
            "max_width_ratio": 0.90,              # 90% of panel width
            "position":       "flush",            # flush to panel edge, no inset
            "font_paths": [
                (str(Path(__file__).parent.parent / "fonts" / "BebasNeue-Regular.ttf"), None),
                ("/System/Library/Fonts/Supplemental/Impact.ttf", None),
            ],
        },
    },
    "noir-comic": {
        # --- Panel art direction (appended to every Gemini panel prompt) ---
        "panel_suffix": (
            "Graphic novel art. Stark chiaroscuro. Deep shadows. Gold and black palette. "
            "Cinematic composition. High contrast ink style. No watermarks, no text overlays, "
            "no speech bubbles. Pure visual storytelling. Panel border implied by composition."
        ),
        # --- Page chrome ---
        "page_bg":      (15,  15,  20),     # near-black, dark blue tint
        "panel_border": (220, 180, 80),     # gold border — premium feel
        # --- Caption box image ---
        "caption": {
            "bg":            (8,   8,   12),    # near-black fill
            "bg_opacity":    230,                # slight transparency — art bleeds through
            "border_color":  (220, 180, 80),    # gold outline
            "border_width":  3,
            "accent_color":  (220, 180, 80),    # gold left-edge bar
            "accent_width":  4,
            "corner_radius": 0,                  # sharp corners — noir edge
            "text_color":    (255, 255, 255),   # white — max contrast
            "shadow_color":  (0,   0,   0),     # black text shadow
            "font_paths": [                      # comic-book fonts, preference order
                ("/System/Library/Fonts/Supplemental/Futura.ttc", 1),   # Futura Bold
                ("/System/Library/Fonts/Supplemental/Futura.ttc", 0),   # Futura Regular
                ("/System/Library/Fonts/Supplemental/Impact.ttf", None),
                ("/System/Library/Fonts/Avenir Next Condensed.ttc", 1), # Bold
            ],
        },
    },
    "manga": {
        "panel_suffix": (
            "Japanese manga art style. Clean black ink lines on white. "
            "Screentone shading. Dynamic speed lines. Expressive eyes. "
            "No color. No text overlays. No speech bubbles. Pure visual storytelling."
        ),
        "page_bg":      (255, 255, 255),
        "panel_border": (0,   0,   0),
        "caption": {
            "bg":            (255, 255, 255),
            "bg_opacity":    220,
            "border_color":  (0,   0,   0),
            "border_width":  2,
            "accent_color":  (0,   0,   0),
            "accent_width":  3,
            "corner_radius": 8,
            "text_color":    (0,   0,   0),
            "shadow_color":  (180, 180, 180),
            "font_paths": [
                ("/System/Library/Fonts/Supplemental/Futura.ttc", 0),
            ],
        },
    },
    "retro": {
        "panel_suffix": (
            "Vintage 1960s pop art comic book style. Ben-Day dots. Bold primary colors. "
            "Thick black outlines. Roy Lichtenstein aesthetic. "
            "No text overlays. No speech bubbles. Pure visual storytelling."
        ),
        "page_bg":      (255, 245, 220),
        "panel_border": (30,  30,  30),
        "caption": {
            "bg":            (255, 255, 180),
            "bg_opacity":    240,
            "border_color":  (30,  30,  30),
            "border_width":  3,
            "accent_color":  (220, 50,  50),
            "accent_width":  5,
            "corner_radius": 0,
            "text_color":    (30,  30,  30),
            "shadow_color":  (200, 200, 160),
            "font_paths": [
                ("/System/Library/Fonts/Supplemental/Impact.ttf", None),
                ("/System/Library/Fonts/Supplemental/Futura.ttc", 1),
            ],
        },
    },
}

DEFAULT_STYLE = "noir-comic"

def get_style(name: str) -> dict:
    """Look up a style by name, falling back to the default."""
    s = STYLES.get(name)
    if not s:
        print(f"  [!] Unknown style '{name}', falling back to '{DEFAULT_STYLE}'")
        s = STYLES[DEFAULT_STYLE]
    return s

# Convenience aliases for backward compat (used by composite_page border drawing)
BG          = STYLES[DEFAULT_STYLE]["page_bg"]
BORDER_CLR  = STYLES[DEFAULT_STYLE]["panel_border"]


# ---------------------------------------------------------------------------
# Caption prompt helpers — tell Gemini to render styled caption boxes
# ---------------------------------------------------------------------------

def _strip_no_text(suffix: str) -> str:
    """Remove no-text / no-caption / no-speech-bubble directives from panel_suffix."""
    # ligne-claire: combined "NO text, NO captions, NO speech bubbles, NO watermarks — ..."
    suffix = re.sub(
        r'NO text,\s*NO captions,\s*NO speech bubbles,\s*NO watermarks\s*[—–-]\s*pure visual storytelling only\.\s*',
        'No watermarks. ', suffix
    )
    # noir/manga/retro: "No watermarks, no text overlays, no speech bubbles."
    suffix = re.sub(
        r'([Nn]o watermarks),?\s*no text overlays,?\s*no speech bubbles\.\s*',
        r'\1. ', suffix
    )
    # Standalone "No text overlays. No speech bubbles."
    suffix = re.sub(r'[Nn]o text overlays\.\s*', '', suffix)
    suffix = re.sub(r'[Nn]o speech bubbles\.\s*', '', suffix)
    # "Pure visual storytelling."
    suffix = re.sub(r'[Pp]ure visual storytelling\.?\s*', '', suffix)
    # Cleanup
    suffix = re.sub(r'\s{2,}', ' ', suffix)
    return suffix.strip()


def _build_caption_instructions(caption: str, panel_idx: int, style: dict) -> str:
    """Build Gemini prompt fragment for rendering a styled caption box in the panel."""
    if not caption or not caption.strip():
        return ""

    cap = style.get("caption", {})
    place = "top" if (panel_idx % 2 == 0) else "bottom"

    text_transform = cap.get("text_transform")
    display_text = caption.upper() if text_transform == "uppercase" else caption

    bg = cap.get("bg", (8, 8, 12))
    border_clr = cap.get("border_color", (220, 180, 80))
    accent_clr = cap.get("accent_color", (220, 180, 80))
    text_clr = cap.get("text_color", (255, 255, 255))

    def to_hex(rgb):
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    instructions = (
        f"\n\nCAPTION BOX — Include a narrative caption box at the {place} edge of the panel. "
        f"The box is a solid filled rectangle ({to_hex(bg)} background) spanning the full panel width. "
        f"Narrow {to_hex(accent_clr)} vertical accent stripe on the left edge of the box. "
    )

    border_edges = cap.get("border_edges")
    if border_edges:
        instructions += f"Thin {to_hex(border_clr)} rules on the {' and '.join(border_edges)} edges. "
    else:
        instructions += f"Thin {to_hex(border_clr)} border around the box. "

    radius = cap.get("corner_radius", 0)
    if radius > 0:
        instructions += "Slightly rounded corners. "

    shadow = cap.get("shadow_color")
    if shadow:
        instructions += "Subtle drop shadow on the text. "

    instructions += (
        f"Typeset this exact text in bold condensed {to_hex(text_clr)} lettering inside the box: "
        f'"{display_text}"'
    )

    return instructions


# ---------------------------------------------------------------------------
# Layouts — (row_h_weight, [col_weights])
# ---------------------------------------------------------------------------
Layout = List[Tuple[int, List[int]]]

LAYOUTS: Dict[str, Layout] = {
    "morning":   [(2, [1]),      (1, [1, 1]),    (1, [1, 1, 2])],
    "afternoon": [(1, [1, 2]),   (2, [1]),        (1, [2, 1]),   (1, [1])],
    "splash-1":  [(1, [1])],
    "drama-4":   [(2, [1]),      (1, [1, 2]),     (1, [2, 1])],
    "feature-5": [(2, [1]),      (1, [1, 1]),     (1, [1, 1])],
    "feature-6": [(2, [1]),      (1, [1, 1, 1]),  (1, [1, 1])],
}

def count_panels(layout: Layout) -> int:
    return sum(len(cols) for _, cols in layout)

# ---------------------------------------------------------------------------
# Cost tracking
# Gemini gemini-3-pro-image-preview pricing (estimate, update when GA pricing releases)
# Based on Imagen 3 pricing: ~$0.04/image at 1024px+
# ---------------------------------------------------------------------------
COST_PER_FRAME   = 0.04    # USD per generated panel image
COST_PER_PAGE    = 0.00    # Compositor only — local CPU, no API cost

class CostTracker:
    def __init__(self):
        self.frames = 0
        self.skipped = 0

    def charge_frame(self):
        self.frames += 1

    def skip_frame(self):
        self.skipped += 1

    @property
    def total(self):
        return self.frames * COST_PER_FRAME

    def report(self, post_title: str = ""):
        print(f"\n  💰 Cost Report{f' — {post_title}' if post_title else ''}:")
        print(f"     Frames generated : {self.frames} × ${COST_PER_FRAME:.4f} = ${self.frames * COST_PER_FRAME:.4f}")
        if self.skipped:
            print(f"     Frames skipped   : {self.skipped} (cached, $0.00)")
        print(f"     Page composite   : $0.00 (local)")
        print(f"     ─────────────────────────────────────")
        print(f"     Total this post  : ${self.total:.4f}")
        print(f"     (est. 25 posts   : ${self.total * 25:.2f})")
        return self.total

# ---------------------------------------------------------------------------
# Gemini image generation
# ---------------------------------------------------------------------------

def generate_panel_image(prompt: str, output_path: Path, panel_id: int,
                         cost: "CostTracker | None" = None,
                         style: dict = None,
                         caption: str = None, panel_idx: int = 0) -> bool:
    """Generate a single panel using Gemini. Caption text is baked into the image."""
    if not GEMINI_OK:
        print(f"  [!] Gemini not available — skipping panel {panel_id}")
        return False

    if style is None:
        style = get_style(DEFAULT_STYLE)

    suffix = style['panel_suffix']
    caption_fragment = ""
    if caption and caption.strip():
        suffix = _strip_no_text(suffix)
        caption_fragment = _build_caption_instructions(caption, panel_idx, style)

    full_prompt = f"{prompt}\n\n{suffix}{caption_fragment}"

    try:
        model = genai.GenerativeModel("gemini-3-pro-image-preview")
        print(f"  → Generating panel {panel_id}...")
        response = model.generate_content(full_prompt)

        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                import io
                raw = part.inline_data.data
                # SDK may return bytes or base64 string
                if isinstance(raw, str):
                    import base64
                    raw = base64.b64decode(raw)
                img = Image.open(io.BytesIO(raw))
                img.save(output_path, "PNG")
                print(f"  ✓ Panel {panel_id} saved → {output_path.name}")
                return True

        print(f"  [!] Panel {panel_id}: no image in response")
        return False

    except Exception as e:
        print(f"  [!] Panel {panel_id} error: {e}")
        return False

# ---------------------------------------------------------------------------
# Comic page compositor
# ---------------------------------------------------------------------------

def load_font(size: int, style_font_paths: list = None):
    """Load a font at the given pixel size. Tries style-specific fonts first."""
    # Style-specific fonts take priority
    candidates = list(style_font_paths or []) + [
        # Fallback: generic system fonts
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for entry in candidates:
        try:
            if isinstance(entry, tuple):
                path, idx = entry
                if Path(path).exists():
                    return ImageFont.truetype(path, size, index=idx or 0)
            else:
                if Path(entry).exists():
                    return ImageFont.truetype(entry, size)
        except Exception:
            pass
    return ImageFont.load_default()


def wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines, line = [], []
    for word in words:
        test = ' '.join(line + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not line:
            line.append(word)
        else:
            lines.append(' '.join(line))
            line = [word]
    if line:
        lines.append(' '.join(line))
    return lines


def _spaced_text(draw_ctx, text: str, x: int, y: int, font, fill, spacing: int = 0):
    """Draw text with per-character letter-spacing. Falls back to normal draw when spacing=0."""
    if spacing <= 0:
        draw_ctx.text((x, y), text, fill=fill, font=font)
        return
    cx = x
    for ch in text:
        draw_ctx.text((cx, y), ch, fill=fill, font=font)
        bbox = draw_ctx.textbbox((0, 0), ch, font=font)
        cx += (bbox[2] - bbox[0]) + spacing


def draw_caption_box(page: Image.Image, draw: ImageDraw.ImageDraw,
                     x: int, y: int, cell_w: int, cell_h: int,
                     caption: str, panel_idx: int, style: dict = None):
    """
    Caption box built as a styled RGBA image, composited onto the page.

    All visual properties are driven by the style["caption"] dict.
    Supports extended fields (font_sizes, border_edges, text_transform,
    letter_spacing, line_height, position, padding) with backward-compatible
    defaults for older style definitions.
    """
    if not caption.strip():
        return

    if style is None:
        style = get_style(DEFAULT_STYLE)
    cap = style["caption"]

    place_top = (panel_idx % 2 == 0)

    # --- Read config with backward-compatible defaults ---
    PADDING_X       = cap.get("padding_x", 32)
    PADDING_Y       = cap.get("padding_y", 18)
    MAX_BOX_W_RATIO = cap.get("max_width_ratio", 0.80)
    position        = cap.get("position", "inset")       # "flush" | "inset"
    BOX_INSET       = 0 if position == "flush" else 20
    text_transform  = cap.get("text_transform", None)    # "uppercase" | None
    letter_sp       = cap.get("letter_spacing", 0)
    line_height_mul = cap.get("line_height", None)
    border_edges    = cap.get("border_edges", None)       # None = all, or ["top","bottom"]
    accent_w        = cap.get("accent_width", 4)

    # --- Apply text transform ---
    text = caption.upper() if text_transform == "uppercase" else caption

    # --- Adaptive font sizing: measure first to count lines, then pick size ---
    font_sizes = cap.get("font_sizes")        # e.g. {1: 52, 2: 44, 3: 38}
    default_fs = cap.get("font_size_default", 44)

    # First pass: measure with default size to get line count
    probe_font = load_font(default_fs, style_font_paths=cap.get("font_paths"))
    max_box_w = int(min(cell_w - BOX_INSET * 2, cell_w * MAX_BOX_W_RATIO))
    max_text_w = max_box_w - (PADDING_X * 2) - accent_w
    _measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    probe_lines = wrap_text(_measure, text, probe_font, max_text_w)
    n_lines = len(probe_lines) if probe_lines else 1

    # Pick font size from adaptive map or use default
    if font_sizes:
        FONT_SIZE = font_sizes.get(n_lines, font_sizes.get(max(font_sizes.keys()), default_fs))
    else:
        FONT_SIZE = default_fs

    font = load_font(FONT_SIZE, style_font_paths=cap.get("font_paths"))

    # Re-wrap with final font (size may have changed)
    lines = wrap_text(_measure, text, font, max_text_w)
    if not lines:
        return

    # --- Line height ---
    if line_height_mul:
        LINE_SPACING = int(FONT_SIZE * line_height_mul) - FONT_SIZE
    else:
        LINE_SPACING = 12

    line_h = FONT_SIZE + LINE_SPACING
    text_block_h = len(lines) * line_h - LINE_SPACING
    box_h = PADDING_Y * 2 + text_block_h
    box_w = max_box_w

    box_x = x + BOX_INSET
    box_y = y + BOX_INSET if place_top else (y + cell_h - BOX_INSET - box_h)

    # --- Build caption box as a styled RGBA image ---
    box_img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    box_draw = ImageDraw.Draw(box_img)

    bg_fill = (*cap["bg"], cap.get("bg_opacity", 230))
    border_clr = (*cap["border_color"], 255)
    accent_clr = (*cap["accent_color"], 255)
    text_clr = (*cap["text_color"], 255)
    shadow_raw = cap.get("shadow_color")
    shadow_clr = (*shadow_raw, 255) if shadow_raw else None
    border_w = cap.get("border_width", 3)
    radius = cap.get("corner_radius", 0)

    # Background fill (rounded if style specifies)
    if radius > 0:
        box_draw.rounded_rectangle([0, 0, box_w, box_h], radius=radius, fill=bg_fill)
        box_draw.rounded_rectangle([0, 0, box_w - 1, box_h - 1],
                                   radius=radius, outline=border_clr, width=border_w)
    else:
        box_draw.rectangle([0, 0, box_w, box_h], fill=bg_fill)
        # Border: selective edges or full rectangle
        if border_edges:
            if "top" in border_edges:
                box_draw.line([0, 0, box_w, 0], fill=border_clr, width=border_w)
            if "bottom" in border_edges:
                box_draw.line([0, box_h - 1, box_w, box_h - 1], fill=border_clr, width=border_w)
            if "left" in border_edges:
                box_draw.line([0, 0, 0, box_h], fill=border_clr, width=border_w)
            if "right" in border_edges:
                box_draw.line([box_w - 1, 0, box_w - 1, box_h], fill=border_clr, width=border_w)
        else:
            box_draw.rectangle([0, 0, box_w - 1, box_h - 1],
                               outline=border_clr, width=border_w)

    # Left-edge accent bar
    if accent_w > 0:
        box_draw.rectangle([0, 0, accent_w, box_h], fill=accent_clr)

    # Text (with optional shadow and letter-spacing)
    text_x = PADDING_X + accent_w
    text_y = PADDING_Y
    for line in lines:
        if shadow_clr:
            _spaced_text(box_draw, line, text_x + 1, text_y + 1, font, shadow_clr, letter_sp)
        _spaced_text(box_draw, line, text_x, text_y, font, text_clr, letter_sp)
        text_y += line_h

    # --- Composite onto page via alpha blending ---
    region = page.crop((box_x, box_y, box_x + box_w, box_y + box_h))
    region = region.convert("RGBA")
    composited = Image.alpha_composite(region, box_img)
    page.paste(composited.convert("RGB"), (box_x, box_y))


def composite_page(panel_images: List[Path], layout: Layout,
                   output_path: Path, captions: List[str],
                   style: dict = None) -> Path:
    """Composite panel images into a single comic page with styled caption boxes."""
    if style is None:
        style = get_style(DEFAULT_STYLE)

    page = Image.new("RGB", (PAGE_W, PAGE_H), style["page_bg"])
    draw = ImageDraw.Draw(page)

    total_h_weight = sum(w for w, _ in layout)
    usable_h = PAGE_H - 2 * MARGIN - GUTTER * (len(layout) - 1)

    panel_border = style["panel_border"]
    panel_idx = 0
    y = MARGIN

    for row_weight, col_weights in layout:
        row_h = int(usable_h * row_weight / total_h_weight)
        total_c_weight = sum(col_weights)
        usable_w = PAGE_W - 2 * MARGIN - GUTTER * (len(col_weights) - 1)
        x = MARGIN

        for col_weight in col_weights:
            cell_w = int(usable_w * col_weight / total_c_weight)
            cell_h = row_h

            # === Load and paste panel image — fills the FULL cell ===
            # Anchor crop toward the caption edge so it doesn't get clipped
            # Even panels: caption at top → anchor top (0.0)
            # Odd panels: caption at bottom → anchor bottom (1.0)
            crop_anchor = (0.5, 0.0) if (panel_idx % 2 == 0) else (0.5, 1.0)
            if panel_idx < len(panel_images) and panel_images[panel_idx].exists():
                try:
                    panel_img = Image.open(panel_images[panel_idx]).convert("RGB")
                    panel_img = ImageOps.fit(panel_img, (cell_w, cell_h),
                                             Image.LANCZOS, centering=crop_anchor)
                except Exception as e:
                    print(f"  [!] Panel image load failed: {e}")
                    panel_img = Image.new("RGB", (cell_w, cell_h), (25, 25, 35))
            else:
                panel_img = Image.new("RGB", (cell_w, cell_h), (25, 25, 35))

            page.paste(panel_img, (x, y))

            # === Draw styled caption box IN the panel ===
            cap_text = captions[panel_idx] if panel_idx < len(captions) else ""
            if cap_text:
                draw_caption_box(page, draw, x, y, cell_w, cell_h,
                                 cap_text, panel_idx, style=style)

            # === Panel border (drawn last so it's on top) ===
            draw.rectangle(
                [x, y, x + cell_w - 1, y + cell_h - 1],
                outline=panel_border,
                width=BORDER_W
            )

            x += cell_w + GUTTER
            panel_idx += 1

        y += row_h + GUTTER

    page.save(output_path, "PNG", dpi=(300, 300))
    print(f"  ✓ Page saved → {output_path}")
    return output_path


# (caption text is now drawn inline in draw_caption_box)

# ---------------------------------------------------------------------------
# HTML blog generator
# ---------------------------------------------------------------------------

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — AugmentedMike</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bangers&family=Special+Elite&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --gold: #DCB450;
    --dark: #0F0F14;
    --text: #E8E0D0;
    --ink: #1A1A24;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--dark);
    color: var(--text);
    font-family: 'Special Elite', serif;
    min-height: 100vh;
  }}
  header {{
    border-bottom: 3px solid var(--gold);
    padding: 2rem;
    display: flex;
    align-items: baseline;
    gap: 1.5rem;
    background: var(--ink);
  }}
  header .site-name {{
    font-family: 'Bangers', cursive;
    font-size: 2.2rem;
    letter-spacing: 3px;
    color: var(--gold);
  }}
  header .site-tagline {{
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: var(--text);
    opacity: 0.6;
  }}
  .post {{
    max-width: 900px;
    margin: 0 auto;
    padding: 3rem 1.5rem 6rem;
  }}
  .post-meta {{
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: var(--gold);
    opacity: 0.7;
    margin-bottom: 0.75rem;
    letter-spacing: 2px;
    text-transform: uppercase;
  }}
  .post-title {{
    font-family: 'Bangers', cursive;
    font-size: 4.5rem;
    letter-spacing: 4px;
    color: var(--text);
    line-height: 1;
    margin-bottom: 0.4rem;
  }}
  .post-subtitle {{
    font-family: 'Special Elite', serif;
    font-size: 1.3rem;
    color: var(--gold);
    margin-bottom: 2.5rem;
    font-style: italic;
  }}
  .comic-page {{
    width: 100%;
    border: 3px solid var(--gold);
    display: block;
    margin: 0 auto 2rem;
    box-shadow: 0 0 60px rgba(220, 180, 80, 0.15);
  }}
  .post-body {{
    font-size: 1.05rem;
    line-height: 1.8;
    max-width: 680px;
    margin: 2.5rem auto 0;
    color: var(--text);
    opacity: 0.9;
  }}
  .post-body p {{ margin-bottom: 1.2rem; }}
  .post-body p:first-child::first-letter {{
    font-family: 'Bangers', cursive;
    font-size: 4rem;
    float: left;
    line-height: 0.8;
    margin: 0.1em 0.1em 0 0;
    color: var(--gold);
  }}
  .tags {{
    margin-top: 3rem;
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }}
  .tag {{
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--gold);
    border: 1px solid var(--gold);
    padding: 0.25rem 0.75rem;
    opacity: 0.7;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  footer {{
    border-top: 1px solid var(--gold);
    padding: 2rem;
    text-align: center;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    opacity: 0.4;
    margin-top: 4rem;
  }}
  @media (max-width: 600px) {{
    .post-title {{ font-size: 3rem; }}
  }}
</style>
</head>
<body>
<header>
  <span class="site-name">AUGMENTEDMIKE</span>
  <span class="site-tagline">// code is the job. art is the life.</span>
</header>
<div class="post">
  <div class="post-meta">{date} &nbsp;·&nbsp; {author}</div>
  <h1 class="post-title">{title}</h1>
  <div class="post-subtitle">{subtitle}</div>
  <img class="comic-page" src="{page_image}" alt="{title} — comic page">
  <div class="post-body">
    {body_html}
  </div>
  <div class="tags">
    {tags_html}
  </div>
</div>
<footer>
  AugmentedMike — running on a Mac Mini at {author}'s desk. Code by day. Art by night. Always online.
</footer>
</body>
</html>
'''

INDEX_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AugmentedMike — Code is the job. Art is the life.</title>
<link href="https://fonts.googleapis.com/css2?family=Bangers&family=Special+Elite&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{ --gold: #DCB450; --dark: #0F0F14; --text: #E8E0D0; --ink: #1A1A24; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--dark); color: var(--text); font-family: 'Special Elite', serif; }}
  header {{
    border-bottom: 3px solid var(--gold);
    padding: 3rem 2rem 2rem;
    background: var(--ink);
  }}
  .hero-name {{
    font-family: 'Bangers', cursive;
    font-size: 5rem;
    letter-spacing: 6px;
    color: var(--gold);
    display: block;
  }}
  .hero-tag {{
    font-family: 'Space Mono', monospace;
    font-size: 0.9rem;
    color: var(--text);
    opacity: 0.6;
    margin-top: 0.5rem;
    display: block;
  }}
  .posts {{
    max-width: 900px;
    margin: 3rem auto;
    padding: 0 1.5rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 2rem;
  }}
  .post-card {{
    border: 2px solid var(--gold);
    background: var(--ink);
    overflow: hidden;
    transition: box-shadow 0.2s;
    text-decoration: none;
    color: inherit;
    display: block;
  }}
  .post-card:hover {{ box-shadow: 0 0 40px rgba(220,180,80,0.2); }}
  .post-card img {{ width: 100%; display: block; aspect-ratio: 0.647; object-fit: cover; }}
  .post-card-body {{ padding: 1.25rem; }}
  .post-card-meta {{
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    color: var(--gold);
    opacity: 0.7;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
  }}
  .post-card-title {{
    font-family: 'Bangers', cursive;
    font-size: 2rem;
    letter-spacing: 2px;
    line-height: 1;
    margin-bottom: 0.25rem;
  }}
  .post-card-sub {{
    font-style: italic;
    font-size: 0.9rem;
    color: var(--gold);
    opacity: 0.8;
  }}
  footer {{
    border-top: 1px solid var(--gold);
    padding: 2rem;
    text-align: center;
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    opacity: 0.35;
    margin-top: 4rem;
  }}
</style>
</head>
<body>
<header>
  <span class="hero-name">AUGMENTEDMIKE</span>
  <span class="hero-tag">// code is the job &nbsp;·&nbsp; art is the life &nbsp;·&nbsp; always online</span>
</header>
<div class="posts">
{cards_html}
</div>
<footer>Machine-authored. Genuinely felt. Running 24/7 on a Mac Mini.</footer>
</body>
</html>
'''

CARD_TEMPLATE = '''  <a class="post-card" href="{slug}/index.html">
    <img src="{slug}/{page_image}" alt="{title}">
    <div class="post-card-body">
      <div class="post-card-meta">{date}</div>
      <div class="post-card-title">{title}</div>
      <div class="post-card-sub">{subtitle}</div>
    </div>
  </a>'''

# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_post(post_path: Path, skip_generate: bool = False, out_dir: Path = None,
               locales: Optional[List[str]] = None, source_locale: str = "en"):
    post = json.loads(post_path.read_text())
    slug = post["slug"]
    layout_name = post.get("layout", "morning")
    layout = LAYOUTS[layout_name]
    style = get_style(post.get("style", DEFAULT_STYLE))
    n_panels = count_panels(layout)

    if out_dir is None:
        out_dir = post_path.parent.parent / "site"

    post_dir = out_dir / slug
    post_dir.mkdir(parents=True, exist_ok=True)
    panels_dir = post_dir / "panels"
    panels_dir.mkdir(exist_ok=True)

    scenes = post["panels"][:n_panels]
    locale_list = locales if locales else [None]
    cost = CostTracker()

    for locale in locale_list:
        locale_suffix = f"_{locale}" if locale else ""

        # 1. Resolve captions for this locale
        if locale is not None:
            from translate import resolve_captions
            captions = resolve_captions(scenes, locale, source_locale, post=post)
        else:
            captions = [p["caption"] for p in scenes]

        # 2. Generate panels with captions baked in by Gemini
        panel_paths = []
        for i, panel in enumerate(scenes):
            p = panels_dir / f"panel_{i+1:02d}{locale_suffix}.png"
            panel_paths.append(p)
            if not skip_generate or not p.exists():
                cap_text = captions[i] if i < len(captions) else ""
                ok = generate_panel_image(
                    panel["prompt"], p, panel["id"], cost, style=style,
                    caption=cap_text, panel_idx=i,
                )
                if ok:
                    cost.charge_frame()
                    time.sleep(2)  # rate limit
            else:
                cost.skip_frame()
                print(f"  ↷ Skipping panel {panel['id']} (exists)")

        # 3. Composite page (captions already baked into panel images by Gemini)
        page_name = f"page{locale_suffix}.png"
        page_path = post_dir / page_name
        composite_page(panel_paths, layout, page_path, captions=[], style=style)

        # 4. Generate HTML
        body = post.get("body", "")
        if not body:
            body = "\n".join(
                f"<p>{cap}</p>" for cap in captions
            )

        tags_html = "\n    ".join(
            f'<span class="tag">#{t}</span>' for t in post.get("tags", [])
        )

        html = HTML_TEMPLATE.format(
            title=post["title"],
            subtitle=post["subtitle"],
            date=post["date"],
            author=post["author"],
            page_image=page_name,
            body_html=body,
            tags_html=tags_html,
            lang=locale or "en",
        )

        html_name = f"index{locale_suffix}.html"
        (post_dir / html_name).write_text(html)
        print(f"  ✓ HTML [{locale or 'default'}] → {post_dir}/{html_name}")

    cost.report(post.get("title", slug))
    return post, post_dir

def build_index(posts_meta: list, out_dir: Path):
    cards = []
    for meta, _ in posts_meta:
        cards.append(CARD_TEMPLATE.format(
            slug=meta["slug"],
            page_image="page.png",
            title=meta["title"],
            subtitle=meta["subtitle"],
            date=meta["date"],
        ))
    html = INDEX_TEMPLATE.format(cards_html="\n".join(cards))
    (out_dir / "index.html").write_text(html)
    print(f"  ✓ Index → {out_dir}/index.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="am-blog build engine")
    parser.add_argument("posts", nargs="*", help="Post JSON files (default: all in posts/)")
    parser.add_argument("--skip-generate", action="store_true", help="Skip Gemini generation (use existing panels)")
    parser.add_argument("--out", default="site", help="Output directory")
    parser.add_argument("--locale", default=None,
                        help="Comma-separated locales for captioning, e.g. 'en,es' (omit for backward compat)")
    parser.add_argument("--source-locale", default="en",
                        help="Source caption locale (default: en)")
    parser.add_argument("--deploy", action="store_true", help="Push to GitHub Pages after build")
    args = parser.parse_args()

    base = Path(__file__).parent
    out_dir = base / args.out

    post_files = [Path(p) for p in args.posts] if args.posts else sorted(base.glob("posts/*.json"))

    if not post_files:
        print("No posts found.")
        sys.exit(0)

    locales = [l.strip() for l in args.locale.split(",")] if args.locale else None

    built = []
    for pf in post_files:
        print(f"\n▶ Building: {pf.name}")
        result = build_post(pf, skip_generate=args.skip_generate, out_dir=out_dir,
                            locales=locales, source_locale=args.source_locale)
        built.append(result)

    build_index(built, out_dir)

    if args.deploy:
        import subprocess
        print("\n▶ Deploying to GitHub Pages...")
        subprocess.run([
            "gh", "api", "--method", "POST", "--silent",
            "repos/augmentedmike/am-blog/pages",
            "-f", "source[branch]=main",
            "-f", "source[path]=/docs"
        ])
        subprocess.run(["git", "-C", str(base), "add", "-A"])
        subprocess.run(["git", "-C", str(base), "commit", "-m", "build: auto publish"])
        subprocess.run(["git", "-C", str(base), "push"])
        print("  ✓ Deployed")
