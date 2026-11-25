# packages/kara_kutu/tests/test_mission_lessons_prune.py
"""P1b — prune bounds the per-(stack, domain) lessons namespace.

Suppressed (founder-muted) rows are sacred: never pruned, never consume the
keep budget. capture() failure-mode auto-prunes to MAX_LESSONS_PER_DOMAIN.
"""
from __future__ import annotations
import pytest


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


async def _nonsupp(stack, domain):
    from dabidabi import get_db
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM mission_lessons WHERE stack=? AND domain=? AND suppressed=0",
        (stack, domain))
    return (await cur.fetchone())[0]


@pytest.mark.asyncio
async def test_prune_keeps_top_n(tmp_path, monkeypatch):
    await _fresh_db(tmp_path, monkeypatch)
    from kara_kutu import capture, error_domain_key, prune_mission_lessons
    from dabidabi import get_db

    S, D = "s", "d"
    key = error_domain_key(S, D)
    for i in range(6):                    # pattern i gets i+1 occurrences
        for _ in range(i + 1):
            await capture(key, task_id=1, pattern=f"pattern {i}", fix=f"f{i}",
                          severity="warning")

    deleted = await prune_mission_lessons(S, D, keep=3)
    assert deleted == 3
    assert await _nonsupp(S, D) == 3

    db = await get_db()
    cur = await db.execute(
        "SELECT pattern FROM mission_lessons WHERE stack=? AND domain=? AND suppressed=0 "
        "ORDER BY occurrences DESC", (S, D))
    kept = [r[0] for r in await cur.fetchall()]
    # all inserted ~now (age≈0) so recency-weighted score ∝ occurrences
    assert kept == ["pattern 5", "pattern 4", "pattern 3"]


@pytest.mark.asyncio
async def test_prune_never_touches_suppressed(tmp_path, monkeypatch):
    await _fresh_db(tmp_path, monkeypatch)
    from kara_kutu import capture, error_domain_key, prune_mission_lessons
    from dabidabi import get_db

    S, D = "s2", "d2"
    key = error_domain_key(S, D)
    for i in range(4):
        await capture(key, task_id=1, pattern=f"p{i}", fix="f", severity="warning")
    db = await get_db()
    await db.execute(
        "UPDATE mission_lessons SET suppressed=1 WHERE stack=? AND domain=? "
        "AND pattern IN ('p0','p1')", (S, D))
    await db.commit()

    await prune_mission_lessons(S, D, keep=1)
    assert await _nonsupp(S, D) == 1     # keep budget spent only on non-suppressed
    cur = await db.execute(
        "SELECT COUNT(*) FROM mission_lessons WHERE stack=? AND domain=? AND suppressed=1",
        (S, D))
    assert (await cur.fetchone())[0] == 2  # both muted rows survived


@pytest.mark.asyncio
async def test_capture_failure_auto_prunes_at_max(tmp_path, monkeypatch):
    await _fresh_db(tmp_path, monkeypatch)
    from kara_kutu import capture, error_domain_key
    from kara_kutu.mission_lessons import MAX_LESSONS_PER_DOMAIN as MAX

    S, D = "s3", "d3"
    key = error_domain_key(S, D)
    for i in range(MAX + 5):
        await capture(key, task_id=1, pattern=f"auto {i}", fix="f", severity="warning")
    assert await _nonsupp(S, D) == MAX
