# packages/kara_kutu/src/kara_kutu/experience.py
"""kara_kutu — per-step SUCCESS experience (P1).

Single source of truth for the operation key + the capture/recall verbs over
the workflow-step exemplar store. P1 wires ONLY the success round-trip; the
failure mode (pattern/fix) is stubbed and raises NotImplementedError.

DB access follows kara_kutu convention: dabidabi / yazbunu, not src.infra.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from yazbunu import get_logger

logger = get_logger("kara_kutu.experience")

# key component separator — a control char that cannot appear in a step id,
# workflow name, or agent_type, so the key is unambiguous and reversible.
_KEY_SEP = "\x1f"

# per-error-domain keys are tagged with a leading RS (\x1e) so recall/capture
# can tell a `(stack, domain)` key apart from a step `(workflow, step_id,
# agent_type)` key WITHOUT changing the step-key format (which is already
# shipped + round-trip-proven). A step key never begins with this byte.
_DOMAIN_PREFIX = "\x1e"


def i2p_step_key(workflow: str | None, step_id: str, agent_type: str) -> str:
    """Build the per-step operation key `(workflow, step_id, agent_type)`.

    SINGLE source of truth: capture (apply.py grade-pass) AND the live reader
    (coulson.context) both build their lookup key with this helper so the two
    sides can never drift. ``agent_type`` MUST be ``task['agent_type']`` (NOT
    ``profile.name``) on both sides. ``workflow`` MUST be read the same way on
    both sides (``SELECT workflow FROM missions``) — do NOT hardcode 'i2p'.
    """
    wf = (workflow or "").strip()
    sid = (step_id or "").strip()
    ag = (agent_type or "").strip()
    return _KEY_SEP.join((wf, sid, ag))


def error_domain_key(stack: str, domain: str) -> str:
    """Build the per-error-domain operation key `(stack, domain)`.

    The SECOND kara_kutu namespace: cross-mission failure lessons keyed by the
    tech stack + failure domain (the posthook `kind`/`error_category`). Tagged
    with ``_DOMAIN_PREFIX`` so it is unambiguously distinct from a step key on
    both the capture and (P2) recall sides.
    """
    st = (stack or "").strip()
    dom = (domain or "").strip()
    return _DOMAIN_PREFIX + _KEY_SEP.join((st, dom))


# Workflow-stable base stack for i2p process-lessons — available at phase_0,
# used when the mission has not yet decided a concrete tech stack.
I2P_BASE_STACK = "i2p"


def lesson_stack_for(mission_ctx: "dict | None") -> str:
    """Canonical stack key for a mission's process-lessons — SINGLE source.

    PURE function of the mission context. Writer (apply.py posthook-fail) AND
    reader (inject_lessons executor) both call this with the SAME
    ``missions.context`` so a lesson's save-stack always equals its lookup-stack
    — no caller-supplied flag that could diverge.

    - concrete tech stack decided (`tech_stack_detected`/`tech_stack`) → that stack;
    - else an i2p mission (`workflow_name`/`workflow` starts with ``"i2p"``) →
      the workflow-stable base ``"i2p"`` (available from phase_0 — m90 carries
      ``workflow_name="i2p_v3"`` even though ``missions.workflow==""``);
    - else (non-i2p, no stack) → legacy ``"unknown"`` (launch/ad-hoc unaffected).
    """
    ctx = mission_ctx or {}
    ts = str(ctx.get("tech_stack_detected") or ctx.get("tech_stack") or "").strip()
    if ts:
        return ts
    wf = str(ctx.get("workflow_name") or ctx.get("workflow") or "").strip().lower()
    if wf.startswith("i2p"):
        return I2P_BASE_STACK
    return "unknown"


@dataclass(frozen=True)
class Experience:
    """One retrieved unit of internal experience.

    P1 populates only the success-mode fields. ``fix`` stays None
    for step_success; ``occurrences``/``severity``/``suppressed`` default to the
    success-mode neutrals and are carried for the P2 mission_lessons path.
    """
    kind: str
    key: str
    text: str
    tool_recipe: list = field(default_factory=list)
    quality: float = 0.0
    task_id: int = 0
    created_at: str = ""
    fix: "str | None" = None
    occurrences: int = 1
    severity: str = "info"
    suppressed: bool = False


def _parse_key(key: str) -> tuple[str, str, str]:
    """Reverse i2p_step_key back to (workflow, step_id, agent_type)."""
    parts = (key or "").split(_KEY_SEP)
    if len(parts) != 3:
        return ("", "", "")
    return (parts[0], parts[1], parts[2])


def _is_domain_key(key: str) -> bool:
    """True iff ``key`` is a per-error-domain key (error_domain_key output)."""
    return (key or "").startswith(_DOMAIN_PREFIX)


def _parse_domain_key(key: str) -> tuple[str, str]:
    """Reverse error_domain_key back to (stack, domain)."""
    body = (key or "")[len(_DOMAIN_PREFIX):] if _is_domain_key(key) else ""
    parts = body.split(_KEY_SEP)
    if len(parts) != 2:
        return ("", "")
    return (parts[0], parts[1])


async def recall(key: str, *, limit: int = 3) -> "list[Experience]":
    """Per-step exact-key recall: top-N by quality, best first.

    P1: dispatches only the step-success namespace (the per-step exemplar
    store). The per-error-domain namespace is P2.

    NOTE: ``limit`` is capped by the store's ``MAX_PER_KEY`` (=3) — the
    underlying ``lookup_exemplars`` applies ``LIMIT MAX_PER_KEY`` in SQL, so
    passing ``limit`` > MAX_PER_KEY returns at most MAX_PER_KEY rows. Raising
    the effective cap requires threading ``limit`` into the store (a P2 change).
    """
    # NOTE (identity): kara_kutu.workflow_exemplars uses `dabidabi.get_db` — the
    # SAME object the rest of kara_kutu uses — which is why capture-writes and
    # this recall share ONE DB. Never give that module a different get_db.
    from kara_kutu.workflow_exemplars import lookup_exemplars

    workflow, step_id, agent_type = _parse_key(key)
    if not step_id or not agent_type:
        return []
    rows = await lookup_exemplars(
        workflow=workflow, step_id=step_id, agent_type=agent_type,
    )
    out: list[Experience] = []
    for r in rows[:limit]:
        out.append(Experience(
            kind="step_success",
            key=key,
            text=r.get("result", "") or "",
            tool_recipe=r.get("tool_recipe") or [],
            quality=float(r.get("quality_score") or 0.0),
            task_id=int(r.get("task_id") or 0),
        ))
    return out


# Grade axes carried in the grade verdict raw dict (posthook_continuations._grade_raw_dict).
_GRADE_AXES = ("relevant", "complete", "well_formed", "coherent")

# A grade-PASS with no axis evidence is worth this much: not perfect, never 0.
_QUALITY_DEFAULT = 0.7


async def capture(
    key: str,
    *,
    task_id: int,
    mission_id: "int | None" = None,
    result: "str | None" = None,
    quality: "float | None" = None,           # success mode
    pattern: "str | None" = None,
    fix: "str | None" = None,
    severity: str = "info",                     # failure mode
    source_kind: str = "capture_fail",          # failure mode (provenance)
    source_ref: "dict | None" = None,           # failure mode (provenance)
) -> bool:
    """Capture one unit of experience under ``key``.

    GUARD exactly one mode: success == (result is not None); failure ==
    (pattern is not None and fix is not None). Neither / both → ValueError.

    - **success** (per-step exemplar store): the tool-recipe is reconstructed
      from ``task_id`` internally (capture_exemplar → _tool_recipe_for_task).
    - **failure** (per-error-domain lessons): reuses ``upsert_mission_lesson``
      — the SINGLE lessons writer (no double-write). ``key`` must come from
      ``error_domain_key``; ``source_kind``/``source_ref`` carry provenance.
    """
    is_success = result is not None
    is_failure = pattern is not None and fix is not None
    if is_success == is_failure:
        raise ValueError(
            "capture: exactly one mode required — success(result=...) XOR "
            "failure(pattern=..., fix=...)"
        )

    if is_failure:
        # Per-error-domain namespace: route through the ONE lessons writer.
        from kara_kutu.mission_lessons import upsert_mission_lesson
        stack, domain = _parse_domain_key(key)
        if not domain:
            logger.debug("capture: unkeyable failure drop key=%r", key)
            return False
        pat = (pattern or "").strip()[:120] or f"{domain} failure"
        fx = (fix or "").strip()[:300]
        ref = dict(source_ref or {})
        ref.setdefault("task_id", int(task_id))
        if mission_id is not None:
            ref.setdefault("mission_id", int(mission_id))
        await upsert_mission_lesson(
            stack=stack or "unknown",
            domain=domain,
            pattern=pat,
            fix=fx,
            severity=severity,
            source_kind=source_kind,
            source_ref=ref,
        )
        # Bound the per-(stack, domain) namespace. Best-effort: a prune failure
        # must never turn a successful lesson-write into a failure.
        try:
            from kara_kutu.mission_lessons import prune_mission_lessons
            await prune_mission_lessons(stack or "unknown", domain)
        except Exception as _exc:  # noqa: BLE001
            logger.debug("capture: prune skipped domain=%r err=%s", domain, _exc)
        return True

    # Success mode.
    from kara_kutu.workflow_exemplars import capture_exemplar
    workflow, step_id, agent_type = _parse_key(key)
    if not step_id or not agent_type:
        logger.debug("capture: unkeyable success drop key=%r", key)
        return False
    return await capture_exemplar(
        workflow=workflow,
        step_id=step_id,
        agent_type=agent_type,
        result=result or "",
        quality_score=float(quality if quality is not None else 0.0),
        task_id=int(task_id),
        mission_id=mission_id,
    )


def quality_from_grade(raw: "dict | None") -> float:
    """Map grade booleans → quality in (0, 1].

    Each grade axis is Optional[bool]. None means "not evaluated" and is
    IGNORED — it neither raises nor lowers the score (a short-circuit grade-pass
    builds ``raw`` without axis evidence).

    - real True evidence and zero explicit False → 1.0
    - no real evidence (axes absent, all None, empty / non-dict raw) →
      ``_QUALITY_DEFAULT`` (mid; a grade-PASS is never worthless, never 0)
    - each explicit False subtracts a fixed penalty, floored so a grade-PASS
      never reads as 0
    """
    if not isinstance(raw, dict):
        return _QUALITY_DEFAULT
    present = [raw.get(a) for a in _GRADE_AXES if a in raw]
    falses = sum(1 for v in present if v is False)
    trues = sum(1 for v in present if v is True)
    if falses == 0:
        # No failures: 1.0 only with real positive evidence; otherwise
        # (no axes, or all None) fall back to the mid default.
        return 1.0 if trues else _QUALITY_DEFAULT
    # 0.25 penalty per explicit False, floored at 0.1 (never 0 on a pass).
    return max(0.1, 1.0 - 0.25 * falses)
