# packages/kara_kutu/tests/test_experience_key.py
"""P1 — pure key-builder for the per-step operation key."""
from __future__ import annotations


def test_i2p_step_key_roundtrip_deterministic():
    from kara_kutu import i2p_step_key
    k1 = i2p_step_key("", "7.4a", "coder")
    k2 = i2p_step_key("", "7.4a", "coder")
    assert k1 == k2
    assert isinstance(k1, str)


def test_i2p_step_key_components_distinguish():
    from kara_kutu import i2p_step_key
    base = i2p_step_key("", "7.4a", "coder")
    assert i2p_step_key("i2p", "7.4a", "coder") != base   # workflow matters
    assert i2p_step_key("", "7.4b", "coder") != base       # step matters
    assert i2p_step_key("", "7.4a", "writer") != base      # agent matters


def test_i2p_step_key_normalizes_none_and_whitespace():
    from kara_kutu import i2p_step_key
    # None workflow == "" workflow; agent/step stripped.
    assert i2p_step_key(None, "7.4a", "coder") == i2p_step_key("", "7.4a", "coder")
    assert i2p_step_key("", " 7.4a ", " coder ") == i2p_step_key("", "7.4a", "coder")
