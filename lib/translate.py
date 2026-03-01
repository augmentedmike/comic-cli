"""
translate — Batch caption translation via Gemini.

Translates comic panel captions to target locales, with support for
manual overrides in scene JSON (caption_es, captions.es, etc.).
"""

import json
import logging
import os
from typing import Dict, List, Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported locales
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES: Dict[str, str] = {
    "en": "English",
    "es": "Mexican Spanish",
}

# ---------------------------------------------------------------------------
# API key loader
# ---------------------------------------------------------------------------

def _get_api_key(api_key: Optional[str] = None) -> str:
    """Return an API key from arg, env, or dotenv."""
    if api_key:
        return api_key
    key = os.getenv("GOOGLE_API_KEY", "")
    if key:
        return key
    # Try loading from project .env
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
        key = os.getenv("GOOGLE_API_KEY", "")
    except ImportError:
        pass
    return key


# ---------------------------------------------------------------------------
# Gemini batch translation
# ---------------------------------------------------------------------------

def translate_captions(
    captions: List[str],
    source_locale: str,
    target_locale: str,
    api_key: Optional[str] = None,
) -> List[str]:
    """
    Batch-translate a list of captions from source_locale to target_locale
    using Gemini in a single API call for tone consistency.

    Returns a list of translated strings, same length as input.
    """
    if source_locale == target_locale:
        return list(captions)

    if not captions:
        return []

    key = _get_api_key(api_key)
    if not key:
        logger.warning("No GOOGLE_API_KEY — returning original captions")
        return list(captions)

    if genai is None:
        logger.warning("google-generativeai not installed — returning original captions")
        return list(captions)

    source_name = SUPPORTED_LOCALES.get(source_locale, source_locale)
    target_name = SUPPORTED_LOCALES.get(target_locale, target_locale)

    genai.configure(api_key=key)

    # Build a single prompt for batch translation — keeps tone consistent
    captions_json = json.dumps(captions, ensure_ascii=False)
    prompt = (
        f"You are a native {target_name} speaker translating comic book captions.\n\n"
        f"Translate from {source_name} to {target_name}.\n\n"
        "RULES — THIS IS NOT A TEXTBOOK TRANSLATION:\n"
        "- Write EXACTLY how a native speaker would say it out loud at home.\n"
        "- Do NOT translate word-by-word. Rewrite the sentence the way it would naturally be said.\n"
        "- Use the verbs, phrasings, and sentence structures that native speakers actually use in daily life.\n"
        "- If a phrase has no natural equivalent, say what a native speaker would say in that situation instead.\n"
        "- Keep the emotion and drama. Short punchy lines stay short and punchy.\n"
        "- NEVER use formal or literary language unless the original is formal/literary.\n\n"
        "Return ONLY a JSON array of translated strings, same order and count as the input. "
        "No explanation, no markdown fences, just the JSON array.\n\n"
        f"Input:\n{captions_json}"
    )

    try:
        model = genai.GenerativeModel("gemini-3.1-pro-preview")
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()

        translated = json.loads(text)

        if not isinstance(translated, list) or len(translated) != len(captions):
            logger.warning(
                f"Translation returned {len(translated) if isinstance(translated, list) else 'non-list'} "
                f"items, expected {len(captions)} — falling back to originals"
            )
            return list(captions)

        logger.info(f"Translated {len(captions)} captions: {source_locale} -> {target_locale}")
        return translated

    except Exception as e:
        logger.warning(f"Translation failed ({source_locale} -> {target_locale}): {e}")
        return list(captions)


# ---------------------------------------------------------------------------
# High-level resolver — manual overrides first, AI fills gaps
# ---------------------------------------------------------------------------

def _extract_manual_caption(scene: Dict, locale: str) -> Optional[str]:
    """
    Check scene JSON for a manual translation override.

    Supports two formats:
      1. Flat: {"caption_es": "La maquina despierta."}
      2. Nested: {"captions": {"es": "La maquina despierta."}}
    """
    # Flat format: caption_es, caption_fr, etc.
    flat_key = f"caption_{locale}"
    if flat_key in scene:
        return scene[flat_key]

    # Nested format: captions.es
    nested = scene.get("captions")
    if isinstance(nested, dict) and locale in nested:
        return nested[locale]

    return None


def _extract_bulk_captions(post: Dict, locale: str, count: int) -> Optional[List[str]]:
    """
    Check for bulk caption overrides at the post/root level.

    Supports: {"captions_es": ["caption1", "caption2", ...]}
    Returns the list if present and correct length, else None.
    """
    key = f"captions_{locale}"
    bulk = post.get(key)
    if isinstance(bulk, list) and len(bulk) >= count:
        return bulk[:count]
    return None


def resolve_captions(
    scenes: List[Dict],
    locale: str,
    source_locale: str = "en",
    api_key: Optional[str] = None,
    post: Optional[Dict] = None,
) -> List[str]:
    """
    Resolve captions for a target locale.

    1. If locale == source_locale, return original captions directly.
    2. Check for bulk overrides at post level (captions_es array).
    3. Check each scene for per-panel overrides (caption_XX or captions.XX).
    4. AI-translate any remaining gaps in a single batch call.

    Returns a list of caption strings, one per scene.
    """
    if locale == source_locale:
        return [s.get("caption", "") for s in scenes]

    # Check for bulk captions at the post/root level
    if post is not None:
        bulk = _extract_bulk_captions(post, locale, len(scenes))
        if bulk is not None:
            return bulk

    resolved: List[Optional[str]] = []
    gaps: List[int] = []  # indices needing AI translation

    for i, scene in enumerate(scenes):
        manual = _extract_manual_caption(scene, locale)
        if manual is not None:
            resolved.append(manual)
        else:
            resolved.append(None)
            gaps.append(i)

    # If all captions had manual overrides, we're done
    if not gaps:
        return resolved  # type: ignore  (all are str at this point)

    # Batch-translate the gaps
    source_captions = [scenes[i].get("caption", "") for i in gaps]
    translated = translate_captions(source_captions, source_locale, locale, api_key)

    for idx, gap_i in enumerate(gaps):
        resolved[gap_i] = translated[idx]

    return [c or "" for c in resolved]
