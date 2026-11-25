# packages/kara_kutu/tests/test_experience_quality.py
"""P1 — quality derived from grade booleans, default-safe."""
from __future__ import annotations
import pytest


def test_all_true_is_high():
    from kara_kutu import quality_from_grade
    q = quality_from_grade({"relevant": True, "complete": True,
                            "well_formed": True, "coherent": True})
    assert q == pytest.approx(1.0)


def test_all_missing_is_mid_never_zero():
    from kara_kutu import quality_from_grade
    # short-circuit grade-pass builds raw without the axis booleans
    q = quality_from_grade({"passed": True})
    assert q == pytest.approx(0.7)
    assert q > 0.0


def test_none_axes_treated_as_pass():
    from kara_kutu import quality_from_grade
    q = quality_from_grade({"relevant": None, "complete": None,
                            "well_formed": None, "coherent": None})
    assert q == pytest.approx(0.7)


def test_explicit_false_lowers_but_never_zero():
    from kara_kutu import quality_from_grade
    q = quality_from_grade({"relevant": True, "complete": False,
                            "well_formed": True, "coherent": True})
    assert 0.0 < q < 1.0
    assert q < quality_from_grade({"relevant": True, "complete": True,
                                   "well_formed": True, "coherent": True})


def test_empty_or_non_dict_is_mid():
    from kara_kutu import quality_from_grade
    assert quality_from_grade({}) == pytest.approx(0.7)
    assert quality_from_grade(None) == pytest.approx(0.7)
