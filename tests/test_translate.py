"""Tests for lib/translate.py — caption translation module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure lib/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from translate import (
    SUPPORTED_LOCALES,
    _extract_manual_caption,
    resolve_captions,
    translate_captions,
)


# ------------------------------------------------------------------
# SUPPORTED_LOCALES
# ------------------------------------------------------------------

def test_supported_locales_has_en_and_es():
    assert "en" in SUPPORTED_LOCALES
    assert "es" in SUPPORTED_LOCALES


def test_supported_locales_values_are_strings():
    for code, name in SUPPORTED_LOCALES.items():
        assert isinstance(code, str)
        assert isinstance(name, str)


# ------------------------------------------------------------------
# Manual caption extraction
# ------------------------------------------------------------------

def test_extract_flat_format():
    scene = {"caption": "The machine wakes up.", "caption_es": "La maquina despierta."}
    assert _extract_manual_caption(scene, "es") == "La maquina despierta."


def test_extract_nested_format():
    scene = {"caption": "The machine wakes up.", "captions": {"es": "La maquina despierta."}}
    assert _extract_manual_caption(scene, "es") == "La maquina despierta."


def test_extract_returns_none_when_missing():
    scene = {"caption": "The machine wakes up."}
    assert _extract_manual_caption(scene, "es") is None


def test_extract_flat_takes_priority_over_nested():
    """Flat format is checked first."""
    scene = {
        "caption": "Original",
        "caption_es": "Flat override",
        "captions": {"es": "Nested override"},
    }
    assert _extract_manual_caption(scene, "es") == "Flat override"


def test_extract_different_locales():
    scene = {
        "caption": "Hello",
        "caption_fr": "Bonjour",
        "caption_de": "Hallo",
    }
    assert _extract_manual_caption(scene, "fr") == "Bonjour"
    assert _extract_manual_caption(scene, "de") == "Hallo"
    assert _extract_manual_caption(scene, "es") is None


# ------------------------------------------------------------------
# translate_captions — pass-through when source == target
# ------------------------------------------------------------------

def test_passthrough_same_locale():
    captions = ["Hello", "World"]
    result = translate_captions(captions, "en", "en")
    assert result == ["Hello", "World"]


def test_passthrough_empty_list():
    result = translate_captions([], "en", "es")
    assert result == []


# ------------------------------------------------------------------
# translate_captions — mocked Gemini call
# ------------------------------------------------------------------

@patch("translate.genai")
def test_batch_translate_calls_gemini(mock_genai):
    """Mock Gemini to return a translated JSON array."""
    captions = ["The machine wakes up.", "Code is the job."]
    translated = ["La maquina despierta.", "El codigo es el trabajo."]

    mock_response = MagicMock()
    mock_response.text = json.dumps(translated)
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model

    result = translate_captions(captions, "en", "es", api_key="fake-key")

    assert result == translated
    mock_genai.configure.assert_called_once_with(api_key="fake-key")
    mock_genai.GenerativeModel.assert_called_once_with("gemini-3.1-pro-preview")
    mock_model.generate_content.assert_called_once()

    # Verify the prompt mentions Spanish
    call_args = mock_model.generate_content.call_args[0][0]
    assert "Spanish" in call_args
    assert "English" in call_args


@patch("translate.genai")
def test_batch_translate_handles_markdown_fences(mock_genai):
    """Gemini sometimes wraps output in ```json ... ``` fences."""
    captions = ["Hello"]
    translated = ["Hola"]

    mock_response = MagicMock()
    mock_response.text = f"```json\n{json.dumps(translated)}\n```"
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model

    result = translate_captions(captions, "en", "es", api_key="fake-key")
    assert result == ["Hola"]


@patch("translate.genai")
def test_batch_translate_wrong_count_falls_back(mock_genai):
    """If Gemini returns wrong number of items, fall back to originals."""
    captions = ["Hello", "World"]

    mock_response = MagicMock()
    mock_response.text = json.dumps(["Hola"])  # wrong count
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model

    result = translate_captions(captions, "en", "es", api_key="fake-key")
    assert result == ["Hello", "World"]


@patch("translate.genai")
def test_batch_translate_exception_falls_back(mock_genai):
    """If Gemini raises an exception, fall back to originals."""
    captions = ["Hello"]

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("API error")
    mock_genai.GenerativeModel.return_value = mock_model

    result = translate_captions(captions, "en", "es", api_key="fake-key")
    assert result == ["Hello"]


# ------------------------------------------------------------------
# resolve_captions — integration (with mocked translate)
# ------------------------------------------------------------------

def test_resolve_same_locale_returns_originals():
    scenes = [
        {"caption": "Panel one"},
        {"caption": "Panel two"},
    ]
    result = resolve_captions(scenes, "en", "en")
    assert result == ["Panel one", "Panel two"]


@patch("translate.translate_captions")
def test_resolve_uses_manual_overrides(mock_translate):
    """Manual overrides should be used; only gaps get AI-translated."""
    scenes = [
        {"caption": "Panel one", "caption_es": "Panel uno"},
        {"caption": "Panel two"},
        {"caption": "Panel three", "captions": {"es": "Panel tres"}},
    ]

    mock_translate.return_value = ["Panel dos"]

    result = resolve_captions(scenes, "es", "en", api_key="fake-key")

    assert result == ["Panel uno", "Panel dos", "Panel tres"]
    # Only scene[1] should have been sent for translation
    mock_translate.assert_called_once_with(["Panel two"], "en", "es", "fake-key")


@patch("translate.translate_captions")
def test_resolve_all_manual_skips_api(mock_translate):
    """When all captions have manual overrides, no API call needed."""
    scenes = [
        {"caption": "Panel one", "caption_es": "Panel uno"},
        {"caption": "Panel two", "caption_es": "Panel dos"},
    ]

    result = resolve_captions(scenes, "es", "en")

    assert result == ["Panel uno", "Panel dos"]
    mock_translate.assert_not_called()


def test_resolve_handles_missing_captions():
    """Scenes without a caption key should produce empty strings."""
    scenes = [{}]
    result = resolve_captions(scenes, "en", "en")
    assert result == [""]
