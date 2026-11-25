"""P2b — single-source stack key for i2p mission_lessons (pure fn of ctx)."""
from __future__ import annotations


def test_returns_tech_stack_when_present():
    from kara_kutu import lesson_stack_for
    assert lesson_stack_for({"tech_stack_detected": "fastapi+react", "workflow_name": "i2p_v3"}) == "fastapi+react"
    assert lesson_stack_for({"tech_stack": "django"}) == "django"


def test_base_i2p_from_workflow_name():
    from kara_kutu import lesson_stack_for, I2P_BASE_STACK
    assert lesson_stack_for({"workflow_name": "i2p_v3"}) == I2P_BASE_STACK
    assert lesson_stack_for({"workflow": "i2p"}) == I2P_BASE_STACK
    assert I2P_BASE_STACK == "i2p"


def test_unknown_when_not_i2p_and_no_stack():
    from kara_kutu import lesson_stack_for
    assert lesson_stack_for({}) == "unknown"
    assert lesson_stack_for(None) == "unknown"
    assert lesson_stack_for({"workflow_name": "launch_playbook"}) == "unknown"


def test_normalizes_whitespace():
    from kara_kutu import lesson_stack_for
    assert lesson_stack_for({"tech_stack_detected": "  fastapi  "}) == "fastapi"
