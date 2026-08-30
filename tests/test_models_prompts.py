"""Tests for model allowlist and prompt profiles."""

import pytest

from shared.models_catalog import (
    DEEPSEEK_FLASH,
    MINIMAX_M3,
    MUSE_GLIMMER,
    model_supports_tools,
    resolve_model_id,
)
from shared.prompts import load_system_prompt


def test_resolve_muse_alias():
    assert resolve_model_id("muse") == MUSE_GLIMMER
    assert resolve_model_id("meta/muse-glimmer-30b") == MUSE_GLIMMER


def test_resolve_deepseek():
    assert resolve_model_id("deepseek") == DEEPSEEK_FLASH
    assert resolve_model_id("deepseek-ai/deepseek-v4-flash-0731") == DEEPSEEK_FLASH


def test_resolve_minimax_still_allowed():
    assert resolve_model_id("minimax") == MINIMAX_M3


def test_tools_disabled_for_deepseek_and_minimax():
    assert model_supports_tools(DEEPSEEK_FLASH) is False
    assert model_supports_tools(MINIMAX_M3) is False
    assert model_supports_tools(MUSE_GLIMMER) is True


def test_reject_unknown_model():
    with pytest.raises(ValueError, match="not allowed"):
        resolve_model_id("openai/gpt-4")


def test_planet_taste_prompt_loaded():
    text = load_system_prompt("planet_taste")
    assert "planet-placement" in text.lower() or "Planet map" in text
    assert "star lord" in text.lower() or "Star lord" in text


def test_default_prompt_has_contract():
    text = load_system_prompt("default")
    assert "KP STRICT MODE" in text
