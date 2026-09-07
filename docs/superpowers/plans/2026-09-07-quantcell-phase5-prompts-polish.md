# QuantCell Phase 5: Prompt Rewrite + Orchestrator Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite all agent prompts in QuantCell's own voice (same behavioral contracts, fresh structure/wording) and replace the orchestrator's 100 ms planner polling loop with event-driven waiting.

**Architecture:** Prompts keep their constant names, JSON output contracts (field names, enum values), tool names/parameters, and behavioral rules (transparent proxy, schedule confirmation, A-share English report types, citation format) — but the organization, section structure, and prose are rewritten. The orchestrator gains a per-planning-run `asyncio.Event` set by the user-input callback; `_monitor_planning_task`/`_continue_planning` use `asyncio.wait(FIRST_COMPLETED)` over {planning task, event} instead of a sleep-poll loop.

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md` (Phase 5)

## Global Constraints

- Contracts frozen: `SuperAgentOutcome` / `PlannerResponse` JSON shapes, `TradePlanProposal`/`GridParamAdvice` semantics, tool signatures.
- Full pytest suite must stay green with no test edits except where tests assert prompt text (none known besides non-empty checks).

---

### Task 1: Prompt rewrites
- [ ] `core/super_agent/prompts.py` (instruction + expected output)
- [ ] `core/plan/prompts.py` (instruction + expected output, examples restructured)
- [ ] `agents/research_agent/prompts.py`
- [ ] `agents/news_agent/prompts.py`
- [ ] `agents/common/trading/decision/prompt_based/system_prompt.py` + grid advisor SYSTEM_PROMPT (reword prose, preserve every constraint literally)
- [ ] `uv run pytest -q` green; commit `refactor: rewrite agent prompts in quantcell voice`

### Task 2: Event-driven planner monitoring
- [ ] Orchestrator: `_create_context_aware_callback` returns (callback, event); monitor/continue use `asyncio.wait` on {planning_task, event.wait()} with no sleep loop; repeated prompts clear + re-await the event.
- [ ] Remove dead commented-out registry block in `core/agent/decorator.py`.
- [ ] `uv run pytest -q` green (orchestrator tests unchanged); commit `refactor: event-driven planner monitoring in orchestrator`

### Task 3: Push
- [ ] `git push`; mark plan complete.
