# packages/kara_kutu/tests/test_experience_capture.py
"""P1 — capture(success) writes an exemplar row; mode guard is exactly-one."""
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_capture_success_writes_row(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import dabidabi as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", db_path)
    if _db_mod._db_connection is not None:
        await _db_mod._db_connection.close()
        _db_mod._db_connection = None
    from dabidabi import init_db, get_db
    await init_db()
    # C1: fresh DB lacks audit_log/task_traces that capture_exemplar SELECTs.
    from kara_kutu.audit import _ensure_table as _ensure_audit
    from kara_kutu.tracing import _ensure_table as _ensure_trace
    _db = await get_db(); await _ensure_audit(_db); await _ensure_trace(_db)

    from kara_kutu import capture, recall, i2p_step_key
    key = i2p_step_key("", "7.4a", "coder")
    ok = await capture(key, task_id=555, result="captured output", quality=0.8, mission_id=90)
    assert ok is True

    got = await recall(key, limit=3)
    assert len(got) == 1
    assert got[0].text == "captured output"
    assert got[0].quality == 0.8
    assert got[0].task_id == 555


@pytest.mark.asyncio
async def test_capture_rejects_both_modes(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import dabidabi as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", db_path)
    if _db_mod._db_connection is not None:
        await _db_mod._db_connection.close()
        _db_mod._db_connection = None
    from dabidabi import init_db, get_db
    await init_db()
    # C1 (harmless here; guard raises before any store write, kept for consistency).
    from kara_kutu.audit import _ensure_table as _ensure_audit
    from kara_kutu.tracing import _ensure_table as _ensure_trace
    _db = await get_db(); await _ensure_audit(_db); await _ensure_trace(_db)

    from kara_kutu import capture, i2p_step_key
    key = i2p_step_key("", "7.4a", "coder")
    # both success (result) AND failure (pattern/fix) → guard raises
    with pytest.raises(ValueError):
        await capture(key, task_id=1, result="r", pattern="p", fix="f")
    # neither mode → guard raises
    with pytest.raises(ValueError):
        await capture(key, task_id=1)


def test_error_domain_key_distinct_from_step_key():
    """A per-error-domain key never collides with a per-step key."""
    from kara_kutu import error_domain_key, i2p_step_key
    dk = error_domain_key("python-fastapi", "database_schema")
    sk = i2p_step_key("i2p", "7.4a", "coder")
    assert dk
    assert dk != sk
    # step key never begins with the domain prefix, so the two are dispatchable
    from kara_kutu.experience import _is_domain_key
    assert _is_domain_key(dk) is True
    assert _is_domain_key(sk) is False


async def _fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import dabidabi as _db_mod
    monkeypatch.setattr(_db_mod, "DB_PATH", db_path)
    if _db_mod._db_connection is not None:
        await _db_mod._db_connection.close()
        _db_mod._db_connection = None
    from dabidabi import init_db
    await init_db()  # creates mission_lessons (registered in dabidabi)


@pytest.mark.asyncio
async def test_capture_failure_writes_lesson_and_dedups(tmp_path, monkeypatch):
    await _fresh_db(tmp_path, monkeypatch)
    from kara_kutu import capture, error_domain_key
    from kara_kutu.mission_lessons import _dedup_key
    from dabidabi import get_db

    key = error_domain_key("python-fastapi", "database_schema")
    ok = await capture(
        key, task_id=111, mission_id=90,
        pattern="prisma migrate failed: env missing",
        fix="write .env before migrate", severity="blocker",
        source_kind="posthook_fail", source_ref={"attempts": 3},
    )
    assert ok is True

    db = await get_db()
    dk = _dedup_key("python-fastapi", "database_schema",
                    "prisma migrate failed: env missing")
    row = await (await db.execute(
        "SELECT occurrences, fix, severity, source_kind FROM mission_lessons "
        "WHERE dedup_key=?", (dk,))).fetchone()
    assert row is not None
    assert row[0] == 1           # occurrences
    assert row[1] == "write .env before migrate"
    assert row[2] == "blocker"
    assert row[3] == "posthook_fail"

    # re-capture same (stack, domain, pattern) bumps occurrences, keeps fix
    ok2 = await capture(
        key, task_id=222, mission_id=90,
        pattern="prisma migrate failed: env missing", fix="", severity="blocker",
    )
    assert ok2 is True
    row2 = await (await db.execute(
        "SELECT occurrences, fix FROM mission_lessons WHERE dedup_key=?",
        (dk,))).fetchone()
    assert row2[0] == 2
    assert row2[1] == "write .env before migrate"  # empty re-fix does not clobber


@pytest.mark.asyncio
async def test_capture_failure_unkeyable_returns_false(tmp_path, monkeypatch):
    await _fresh_db(tmp_path, monkeypatch)
    from kara_kutu import capture, error_domain_key
    # empty domain -> unkeyable -> False, never raises
    ok = await capture(error_domain_key("python-fastapi", ""),
                       task_id=1, pattern="x", fix="y")
    assert ok is False
