# Kara Kutu — Flight recorder

> **Standalone.** Split from the [KutAI](https://github.com/msakirc/kutai) monorepo (`packages/kara_kutu/`), where it is developed. It does not need the KutAI app; its test suite passes with only its declared dependencies installed.

> Turkish for "black box" — the aircraft flight recorder. This package keeps the
> durable, append-only history of what the agent system did, so it can be audited
> afterwards and so later runs can learn from earlier ones.

[English](#english) · [Türkçe](#türkçe)

<a id="english"></a>

## Purpose

KutAI has three observability pillars: `nerd_herd` (live system metrics), `yazbunu`
(log lines) and Kara Kutu (**history**). Kara Kutu owns every record that must
survive a restart and be queried later:

- **audit** — who did what, when (tool executions, model calls, state changes);
- **tracing** — what one task did step by step, at what cost and duration;
- **admission forensics** — tasks General Beckman admitted that a downstream gate
  then refused (evidence for offline tuning, not a live control signal);
- **experience** — the internal learning store: successful workflow-step outputs
  (*exemplars*, keyed per step) and cross-mission failure *lessons* (keyed per
  tech stack + failure domain).

**It does NOT** decide anything. It never selects models, retries tasks, grades
output or injects prompts by itself — callers capture into it and read from it.
Writes are best-effort: `audit`, `append_trace` and `record_admission_violation`
swallow their own errors so a recorder failure can never fail the task it records.

## Install

```bash
pip install "kara_kutu @ git+https://github.com/msakirc/kara-kutu.git"
```

Requires Python 3.10+. Sibling KutAI packages are installed from their own repositories.

## Quick start

Needs an absolute `DB_PATH` (env var or `dabidabi.configure()`).

```python
import asyncio

import dabidabi
from kara_kutu import (ACTION_TOOL_EXEC, ACTOR_AGENT, append_trace, audit,
                       format_trace, get_audit_log, get_trace)


async def main():
    await dabidabi.init_db()                  # schema for a fresh DB_PATH
    await audit(ACTOR_AGENT, ACTION_TOOL_EXEC, target="shell", details="ls", task_id=7)
    await append_trace(7, "tool_call", input_summary="ls", output_summary="3 files",
                       duration_ms=12.0)
    print(len(await get_audit_log(task_id=7)), "audit row(s)")
    print(format_trace(await get_trace(7)))
    await dabidabi.close_db()


asyncio.run(main())
```

## Public API

```python
from kara_kutu import (
    audit, ACTOR_AGENT, ACTION_TOOL_EXEC, get_audit_log, format_audit_log,
    append_trace, get_trace, format_trace,
    record_admission_violation,
    i2p_step_key, error_domain_key, lesson_stack_for,
    capture, recall, quality_from_grade, Experience,
    top_mission_lessons, suppress_mission_lesson,
)

# Audit trail (fire-and-forget).
await audit(ACTOR_AGENT, ACTION_TOOL_EXEC, target="shell", details="ls", task_id=7)
rows = await get_audit_log(task_id=7, limit=50)          # -> list[dict]
print(format_audit_log(rows))                            # -> markdown str

# Per-task trace (fire-and-forget).
await append_trace(7, "tool_call", input_summary="...", output_summary="...",
                   cost=0.0, duration_ms=120.0)
print(format_trace(await get_trace(7)))

# Experience: success mode (a graded-PASS workflow step).
key = i2p_step_key("i2p_v3", "4.6", "architect")          # -> str
await capture(key, task_id=7, mission_id=3, result=text,
              quality=quality_from_grade(grade_raw))     # -> bool
examples = await recall(key, limit=3)                    # -> list[Experience]

# Experience: failure mode (a cross-mission lesson).
stack = lesson_stack_for(mission_context)                # -> "i2p" | "<tech stack>" | "unknown"
await capture(error_domain_key(stack, "schema"), task_id=7,
              pattern="emits bare ADR", fix="wrap in envelope")
lessons = await top_mission_lessons(stack, "schema", limit=5)  # -> list[dict]
```

`capture` takes exactly one mode: success (`result=`) **or** failure (`pattern=` +
`fix=`). Passing neither or both raises `ValueError`.

## Key Modules

| module | role |
|---|---|
| `audit.py` | `audit_log` table: append + filtered query + markdown formatter |
| `tracing.py` | per-task trace entries + formatter |
| `admission_forensics.py` | `admission_violations` rows for post-admission refusals |
| `experience.py` | operation keys, `capture` / `recall`, grade → quality mapping |
| `workflow_exemplars.py` | per-step exemplar store (top 3 per key) used by `capture`/`recall` |
| `mission_lessons.py` | cross-mission lessons: upsert (dedup + bump), prune, top-N, mute |

## Dependencies

- `dabidabi` — every table lives in the shared SQLite DB through `dabidabi.get_db()`.
- `yazbunu` — logging.
- No `src.*` imports: Kara Kutu is a leaf package (enforced by
  `tests/test_package_layering.py`).

## Gotchas

- **One key builder per namespace, used on both sides.** The writer and the reader
  must build keys with `i2p_step_key` / `error_domain_key` / `lesson_stack_for`;
  never assemble keys by hand. `agent_type` must be the task's `agent_type`, not a
  prompt profile name. Step keys are `\x1f`-joined; domain keys carry a leading
  `\x1e` so the two namespaces can never collide.
- `recall` serves the **step** namespace only and returns at most 3 rows (the
  exemplar store keeps `MAX_PER_KEY = 3`; a larger `limit` does not raise the cap).
  Domain lessons are read with `top_mission_lessons`.
- `quality_from_grade` never returns 0 for a pass: axes that were not evaluated
  (`None`) are ignored, each explicit `False` costs 0.25, floor 0.1.
- Lessons are bounded per `(stack, domain)` by `prune_mission_lessons`; a lesson
  muted with `suppress_mission_lesson` is kept but never surfaces.

## Tests

```powershell
python -m pytest packages/kara_kutu/tests
```

## In KutAI

Coulson, Mr. Roboto and HaLLederiz Kadir write audit rows and traces; General Beckman captures experience when a workflow step passes grading, and Intersect recalls it the next time the same step runs. Source: [`packages/kara_kutu/`](https://github.com/msakirc/kutai/tree/main/packages/kara_kutu) in the [KutAI monorepo](https://github.com/msakirc/kutai), where this package is developed.

## Status and limitations

- Standalone: it does not import the KutAI app, and its tests pass with only its declared dependencies.
- Version 0.1.0, part of a personal research project. Developed and tested on Windows 11 with Python 3.10; other platforms are untested.
- Installing it pulls in [dabidabi](https://github.com/msakirc/dabidabi), which still declares `fatih_hoca` and `yalayut` for its schema bootstrap (tracked layering debt), so pip resolves most of the KutAI package set.

## License

MIT. See [LICENSE](https://github.com/msakirc/kutai/blob/main/LICENSE).

---
<a id="türkçe"></a>
## Türkçe

### Amaç

KutAI'nin üç gözlem ayağı var: `nerd_herd` (canlı sistem metrikleri), `yazbunu`
(log satırları) ve Kara Kutu (**geçmiş**). Kara Kutu, yeniden başlatmadan sonra da
kalması ve sonradan sorgulanması gereken her kaydın sahibidir:

- **audit** — kim, neyi, ne zaman yaptı (araç çalıştırmaları, model çağrıları, durum değişiklikleri);
- **tracing** — tek bir görevin adım adım ne yaptığı, maliyeti ve süresi;
- **admission forensics** — General Beckman'ın kabul ettiği ama sonraki bir kapının
  reddettiği görevler (çevrimdışı ayar için kanıt; canlı kontrol sinyali değil);
- **experience** — iç öğrenme deposu: başarılı iş akışı adımlarının çıktıları
  (adım başına anahtarlanan *örnekler*) ve görevler arası hata *dersleri*
  (teknoloji yığını + hata alanı başına anahtarlanır).

Kara Kutu **hiçbir karar vermez.** Model seçmez, görev yeniden denemez, çıktı
puanlamaz, kendi başına istem enjekte etmez — çağıranlar ona yazar ve ondan okur.
Yazmalar en iyi çabadır: `audit`, `append_trace` ve `record_admission_violation`
kendi hatalarını yutar; kaydedicinin hatası, kaydettiği görevi asla düşürmez.

### Kurulum

```bash
pip install "kara_kutu @ git+https://github.com/msakirc/kara-kutu.git"
```

Python 3.10+ gerekir. Kardeş KutAI paketleri kendi depolarından kurulur.

### Hızlı başlangıç

Mutlak bir `DB_PATH` gerekir (ortam değişkeni ya da `dabidabi.configure()`).

```python
import asyncio

import dabidabi
from kara_kutu import (ACTION_TOOL_EXEC, ACTOR_AGENT, append_trace, audit,
                       format_trace, get_audit_log, get_trace)


async def main():
    await dabidabi.init_db()                  # schema for a fresh DB_PATH
    await audit(ACTOR_AGENT, ACTION_TOOL_EXEC, target="shell", details="ls", task_id=7)
    await append_trace(7, "tool_call", input_summary="ls", output_summary="3 files",
                       duration_ms=12.0)
    print(len(await get_audit_log(task_id=7)), "audit row(s)")
    print(format_trace(await get_trace(7)))
    await dabidabi.close_db()


asyncio.run(main())
```

### Genel API

```python
from kara_kutu import (
    audit, ACTOR_AGENT, ACTION_TOOL_EXEC, get_audit_log, format_audit_log,
    append_trace, get_trace, format_trace,
    record_admission_violation,
    i2p_step_key, error_domain_key, lesson_stack_for,
    capture, recall, quality_from_grade, Experience,
    top_mission_lessons, suppress_mission_lesson,
)

# Denetim kaydı (at ve unut).
await audit(ACTOR_AGENT, ACTION_TOOL_EXEC, target="shell", details="ls", task_id=7)
rows = await get_audit_log(task_id=7, limit=50)          # -> list[dict]
print(format_audit_log(rows))                            # -> markdown str

# Görev izi (at ve unut).
await append_trace(7, "tool_call", input_summary="...", output_summary="...",
                   cost=0.0, duration_ms=120.0)
print(format_trace(await get_trace(7)))

# Deneyim: başarı kipi (puanlaması geçen bir iş akışı adımı).
key = i2p_step_key("i2p_v3", "4.6", "architect")          # -> str
await capture(key, task_id=7, mission_id=3, result=text,
              quality=quality_from_grade(grade_raw))     # -> bool
examples = await recall(key, limit=3)                    # -> list[Experience]

# Deneyim: hata kipi (görevler arası ders).
stack = lesson_stack_for(mission_context)                # -> "i2p" | "<yığın>" | "unknown"
await capture(error_domain_key(stack, "schema"), task_id=7,
              pattern="emits bare ADR", fix="wrap in envelope")
lessons = await top_mission_lessons(stack, "schema", limit=5)  # -> list[dict]
```

`capture` tam olarak bir kip alır: başarı (`result=`) **ya da** hata (`pattern=` +
`fix=`). İkisi birden ya da hiçbiri verilirse `ValueError` fırlatır.

### Dikkat Edilecekler

- **Her ad alanı için tek anahtar üretici, iki tarafta da.** Yazan ve okuyan
  anahtarları `i2p_step_key` / `error_domain_key` / `lesson_stack_for` ile kurmalı;
  anahtar elle birleştirilmez. `agent_type`, istem profili adı değil görevin
  `agent_type` değeridir. Adım anahtarları `\x1f` ile birleşir; alan anahtarları
  başta `\x1e` taşır, böylece iki ad alanı asla çakışmaz.
- `recall` yalnızca **adım** ad alanına hizmet eder ve en fazla 3 satır döner.
  Alan dersleri `top_mission_lessons` ile okunur.
- `quality_from_grade` geçen bir puanlama için asla 0 dönmez: değerlendirilmemiş
  (`None`) eksenler yok sayılır, her açık `False` 0,25 düşürür, taban 0,1.

### Testler

```powershell
python -m pytest packages/kara_kutu/tests
```

### KutAI içindeki yeri

Coulson, Mr. Roboto ve HaLLederiz Kadir denetim satırları ve izler yazar; General Beckman bir iş akışı adımı puanlamayı geçtiğinde deneyimi kaydeder, Intersect aynı adım yeniden çalıştığında onu geri çağırır. Kaynak: [KutAI monorepo](https://github.com/msakirc/kutai) içinde [`packages/kara_kutu/`](https://github.com/msakirc/kutai/tree/main/packages/kara_kutu); paket orada geliştirilir.

### Durum ve sınırlamalar

- Bağımsız: KutAI uygulamasını import etmez; testleri yalnızca bildirilen bağımlılıklarla geçer.
- Sürüm 0.1.0, kişisel bir araştırma projesinin parçası. Windows 11 ve Python 3.10 üzerinde geliştirilip test edildi; diğer platformlar denenmedi.
- Kurulum [dabidabi](https://github.com/msakirc/dabidabi)'yi de getirir; dabidabi şema kurulumu için hâlâ `fatih_hoca` ve `yalayut`'u bildiriyor (kayıtlı katman borcu), bu yüzden pip KutAI paketlerinin çoğunu kurar.

### Lisans

MIT. [LICENSE](https://github.com/msakirc/kutai/blob/main/LICENSE) dosyasına bakın.
