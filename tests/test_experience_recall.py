# packages/kara_kutu/tests/test_experience_recall.py
"""P1 — recall reads exemplars for the exact key, best-first."""
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_recall_returns_seeded_row(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import dabidabi as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", db_path)
    if _db_mod._db_connection is not None:
        await _db_mod._db_connection.close()
        _db_mod._db_connection = None

    from dabidabi import init_db, get_db
    await init_db()

    # Seed one exemplar directly via the store's ensure+insert path.
    from kara_kutu.workflow_exemplars import _ensure_table
    await _ensure_table()
    db = await get_db()
    await db.execute(
        "INSERT INTO workflow_exemplars "
        "(workflow, step_id, agent_type, result, tool_recipe, quality_score, task_id, mission_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("", "7.4a", "coder", "the passing output", "[]", 0.95, 4242, 90),
    )
    await db.commit()

    from kara_kutu import recall, i2p_step_key, Experience
    key = i2p_step_key("", "7.4a", "coder")
    out = await recall(key, limit=3)
    assert len(out) == 1
    exp = out[0]
    assert isinstance(exp, Experience)
    assert exp.kind == "step_success"
    assert exp.key == key
    assert exp.text == "the passing output"
    assert exp.quality == 0.95
    assert exp.task_id == 4242


@pytest.mark.asyncio
async def test_recall_empty_key_returns_nothing(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import dabidabi as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", db_path)
    if _db_mod._db_connection is not None:
        await _db_mod._db_connection.close()
        _db_mod._db_connection = None
    from dabidabi import init_db
    await init_db()

    from kara_kutu import recall, i2p_step_key
    from kara_kutu.workflow_exemplars import _ensure_table
    await _ensure_table()
    out = await recall(i2p_step_key("", "9.9z", "nobody"), limit=3)
    assert out == []
