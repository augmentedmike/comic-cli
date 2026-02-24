"""Tests for the unified `comic` dispatcher."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

COMIC = str(Path(__file__).resolve().parent.parent / "bin" / "comic")


def run(args, **kwargs):
    """Run the comic dispatcher and return the CompletedProcess."""
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
    r = run(["--help"])
    assert r.returncode == 0
    assert "Available commands" in r.stdout


def test_help_short_flag():
    r = run(["-h"])
    assert r.returncode == 0
    assert "Available commands" in r.stdout


def test_help_word():
    r = run(["help"])
    assert r.returncode == 0
    assert "Available commands" in r.stdout


def test_no_args_shows_help():
    r = run([])
    assert r.returncode == 0
    assert "Available commands" in r.stdout


# ------------------------------------------------------------------
# Subcommand discovery
# ------------------------------------------------------------------

def test_discovers_sibling_tools():
    """--help should list blog, frame, page, qa (the tools in bin/)."""
    r = run(["--help"])
    for name in ("blog", "frame", "page", "qa"):
        assert name in r.stdout, f"Expected '{name}' in help output"


# ------------------------------------------------------------------
# Unknown subcommand
# ------------------------------------------------------------------

def test_unknown_subcommand():
    r = run(["nonexistent"])
    assert r.returncode != 0
    assert "unknown command" in r.stderr


# ------------------------------------------------------------------
# Dispatching to a real tool (list flags are safe — no API calls)
# ------------------------------------------------------------------

def test_dispatch_blog_list_styles():
    r = run(["blog", "--list-styles"])
    assert r.returncode == 0
    assert "comic" in r.stdout.lower()


def test_dispatch_blog_list_layouts():
    r = run(["blog", "--list-layouts"])
    assert r.returncode == 0
    assert "splash" in r.stdout.lower()


# ------------------------------------------------------------------
# Dispatcher with a fake tool (unit-level exec test)
# ------------------------------------------------------------------

def test_dispatch_to_custom_tool():
    """Create a fake comic-test tool and verify the dispatcher finds and runs it."""
    bin_dir = Path(COMIC).parent
    fake_tool = bin_dir / "comic-test"
    try:
        fake_tool.write_text('#!/bin/sh\necho "hello from comic-test $@"\n')
        fake_tool.chmod(0o755)
        r = run(["test", "arg1", "arg2"])
        assert r.returncode == 0
        assert "hello from comic-test" in r.stdout
        assert "arg1" in r.stdout
        assert "arg2" in r.stdout
    finally:
        fake_tool.unlink(missing_ok=True)
