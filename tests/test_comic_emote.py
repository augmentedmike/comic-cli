"""Tests for comic-emote — shaped emote generator."""

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

COMIC = str(Path(__file__).resolve().parent.parent / "bin" / "comic")
COMIC_EMOTE = str(Path(__file__).resolve().parent.parent / "bin" / "comic-emote")


def run_emote(args, **kwargs):
    """Run comic-emote directly and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, COMIC_EMOTE] + args,
        capture_output=True,
        text=True,
        **kwargs,
    )


def run_dispatcher(args, **kwargs):
    """Run via the comic dispatcher."""
    return subprocess.run(
        [sys.executable, COMIC] + args,
        capture_output=True,
        text=True,
        **kwargs,
    )


# ------------------------------------------------------------------
# Help output
# ------------------------------------------------------------------

def test_help_flag():
    r = run_emote(["--help"])
    assert r.returncode == 0
    assert "comic-emote" in r.stdout
    assert "Stream Deck" in r.stdout


def test_help_short_flag():
    r = run_emote(["-h"])
    assert r.returncode == 0
    assert "EXPRESSION" in r.stdout


# ------------------------------------------------------------------
# --list
# ------------------------------------------------------------------

def test_list_expressions():
    r = run_emote(["--list"])
    assert r.returncode == 0
    for expr in ("happy", "witty", "sarcastic", "dramatic", "thinking",
                 "facepalm", "celebrating", "shocked", "cool", "angry",
                 "laughing", "love"):
        assert expr in r.stdout, f"Expected '{expr}' in --list output"


def test_list_short_flag():
    r = run_emote(["-l"])
    assert r.returncode == 0
    assert "happy" in r.stdout


# ------------------------------------------------------------------
# --list-shapes
# ------------------------------------------------------------------

def test_list_shapes():
    r = run_emote(["--list-shapes"])
    assert r.returncode == 0
    for shape in ("circle", "diamond", "hexagon", "rounded-square",
                  "octagon", "shield", "star"):
        assert shape in r.stdout, f"Expected '{shape}' in --list-shapes output"


def test_list_shapes_shows_default():
    r = run_emote(["--list-shapes"])
    assert "(default)" in r.stdout


# ------------------------------------------------------------------
# Dispatcher discovers emote subcommand
# ------------------------------------------------------------------

def test_dispatcher_discovers_emote():
    r = run_dispatcher(["--help"])
    assert r.returncode == 0
    assert "emote" in r.stdout


def test_dispatcher_emote_list():
    r = run_dispatcher(["emote", "--list"])
    assert r.returncode == 0
    assert "happy" in r.stdout


def test_dispatcher_emote_list_shapes():
    r = run_dispatcher(["emote", "--list-shapes"])
    assert r.returncode == 0
    assert "circle" in r.stdout


# ------------------------------------------------------------------
# No args shows error
# ------------------------------------------------------------------

def test_no_args_shows_error():
    r = run_emote([])
    assert r.returncode != 0


# ------------------------------------------------------------------
# Shape mask unit tests (import directly)
# ------------------------------------------------------------------

def _import_mask_generators():
    """Import shape generators from comic-emote (extensionless script)."""
    emote_path = str(Path(__file__).resolve().parent.parent / "bin" / "comic-emote")
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("comic_emote", emote_path)
    spec = importlib.util.spec_from_loader("comic_emote", loader, origin=emote_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mask_circle_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("circle", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    # Center pixel should be opaque (white)
    assert mask.getpixel((128, 128)) == 255
    # Corner pixel should be transparent (black)
    assert mask.getpixel((0, 0)) == 0


def test_mask_diamond_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("diamond", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_mask_hexagon_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("hexagon", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_mask_rounded_square_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("rounded-square", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    # Deep corner should be transparent due to rounding
    assert mask.getpixel((0, 0)) == 0


def test_mask_octagon_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("octagon", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_mask_shield_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("shield", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    # Bottom-left corner transparent
    assert mask.getpixel((0, 255)) == 0


def test_mask_star_properties():
    mod = _import_mask_generators()
    mask = mod.generate_shape_mask("star", 256)
    assert mask.mode == "L"
    assert mask.size == (256, 256)
    assert mask.getpixel((128, 128)) == 255
    assert mask.getpixel((0, 0)) == 0


def test_all_shapes_generate():
    """Every listed shape should produce a valid mask without error."""
    mod = _import_mask_generators()
    for shape_name in mod.SHAPES:
        mask = mod.generate_shape_mask(shape_name, 64)
        assert mask.mode == "L"
        assert mask.size == (64, 64)
