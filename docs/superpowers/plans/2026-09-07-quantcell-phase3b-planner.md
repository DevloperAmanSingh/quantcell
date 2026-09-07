# QuantCell Phase 3b: Planner → LangGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reimplement `ExecutionPlanner` on LangGraph with `interrupt()`-based human-in-the-loop clarification, preserving the public contract (`create_plan(user_input, user_input_callback, thread_id) -> ExecutionPlan`) so `PlanService`, the orchestrator, and the UI are untouched.

**Architecture:** A 3-node `StateGraph` (state: `messages` via `add_messages`, `planner_response`, `invalid_agents` flag, `clarify_count`):
- `generate`: system prompt = `PLANNER_INSTRUCTION` + live agent catalog (rendered from `get_planable_agent_cards()` at run time, replacing the two Agno LLM tools) + `PLANNER_EXPECTED_OUTPUT`; invokes the chat model from `get_chat_model_for_agent("super_agent")` (parity: planner shares the super_agent model config); parses JSON into `PlannerResponse` (fence-stripping; malformed → inadequate response with guidance, parity text).
- `validate`: hallucination guard — task agent names checked against planable cards; invalid → inadequate response with the "Maybe the chosen model hallucinated" guidance, flag `invalid_agents`, END.
- `clarify`: calls `interrupt(guidance_message)`; on resume the answer is appended as a `HumanMessage` and control loops back to `generate`. Entered only when `adequate == false` with guidance, no invalid agents, and `clarify_count < 3`; cap exhausted → END with guidance plan (old turn-ending behavior as fallback).

`create_plan()` drives the graph with `thread_id = conversation_id` (`InMemorySaver`); when `ainvoke` returns `__interrupt__`, it creates a `UserInputRequest(prompt)`, calls `user_input_callback` (orchestrator registers it → conversation enters REQUIRE_USER_INPUT), awaits `wait_for_response()`, then resumes with `Command(resume=answer)`. Task construction (`_create_task`, handoff conversation-id rules) is unchanged. Failure modes preserved: no model → "Planner is unavailable" guidance; malformed → "malformed response" guidance; runtime error → "encountered an error" guidance.

**Tech Stack:** langgraph (`interrupt`, `Command`, `InMemorySaver`), pytest with fake chat models.

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md` (Phase 3)

## Global Constraints

- Frozen: `ExecutionPlanner.__init__(agent_connections)`, `create_plan` signature/return, `UserInputRequest`, `_create_task` semantics, `agentcard_to_prompt`, `PlanService`/`UserInputRegistry`.
- `quantcell/core/plan/tests/test_planner_thread_id.py` and `test_service.py` must pass UNCHANGED.
- Prompt edits limited to replacing Agno tool references with the injected agent catalog (full rewrite is Phase 5).
- No network in tests.

---

### Task 1: Rewrite planner tests (TDD red)

**Files:**
- Rewrite: `python/quantcell/core/plan/tests/test_planner.py`

- [x] **Step 1:** New tests with `RecordingFakeChatModel` (same pattern as super agent tests) + stub connections exposing `get_planable_agent_cards()`:
  1. Adequate single-task reply → `ExecutionPlan` with correct Task fields (agent_name, query, title, thread_id, conversation_id)
  2. Agent catalog appears in the system prompt sent to the model (card name + description)
  3. Invalid agent name → empty tasks + guidance containing "hallucinated"
  4. `adequate:false` + guidance → `user_input_callback` receives `UserInputRequest` with the guidance prompt; after `provide_response("confirm")`, model is called again with the answer in context and the final adequate plan is returned
  5. Clarification cap: model returns inadequate 4× → callback invoked at most 3×, returns guidance plan
  6. Malformed reply → guidance containing "malformed"
  7. Model factory raising → guidance containing "unavailable"
- [x] **Step 2:** `uv run pytest quantcell/core/plan/tests/test_planner.py -q` → FAIL against old implementation.

### Task 2: Rewrite planner on LangGraph (TDD green)

**Files:**
- Rewrite: `python/quantcell/core/plan/planner.py` (keep `UserInputRequest`, `_create_task`, `agentcard_to_prompt`; replace Agno agent + tools with the graph)
- Modify: `python/quantcell/core/plan/prompts.py` (tool references → "Available Agents catalog in your context")

- [x] **Step 1:** Implement per Architecture.
- [x] **Step 2:** `uv run pytest quantcell/core/plan -q` → all planner + thread-id + service tests PASS.
- [x] **Step 3:** Commit: `git commit -am "feat: migrate planner to langgraph with interrupt-based HITL"`

### Task 3: Full verification + push

- [x] **Step 1:** `uv run pytest -q` full suite green; `uv run python -c "import quantcell.server.main"` clean.
- [x] **Step 2:** `git push`
