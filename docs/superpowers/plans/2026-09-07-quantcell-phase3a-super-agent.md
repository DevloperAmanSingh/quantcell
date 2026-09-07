# QuantCell Phase 3a: Super Agent → LangGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reimplement `SuperAgent` on LangGraph, preserving its public contract (`run(user_input) -> AsyncIterator[str | SuperAgentOutcome]`) so the orchestrator is untouched.

**Architecture:** A one-node `StateGraph` (state: `messages` via `add_messages` + `outcome`) compiled with `InMemorySaver`, `thread_id` = conversation_id (parity with Agno's `InMemoryDb` history). The `triage` node prompts with `SUPER_AGENT_INSTRUCTION + SUPER_AGENT_EXPECTED_OUTPUT`, invokes the chat model from `get_chat_model_for_agent("super_agent")`, and parses the JSON reply into `SuperAgentOutcome` (fence-stripping; malformed → ANSWER-with-error outcome, mirroring current behavior). `run()` streams via `stream_mode="messages"` (yields token strings), then reads the final state's outcome. Model-change detection rebuilds the graph when the configured model changes (parity with existing restart logic). Provider-agnostic: no `response_format` binding, the prompt carries the JSON contract, so Ollama/Gemini/OpenAI all work.

**Tech Stack:** langgraph, langchain-core; pytest with `GenericFakeChatModel`.

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md` (Phase 3)

## Global Constraints

- Public contract frozen: `SuperAgentDecision`, `SuperAgentOutcome`, `SuperAgent.name`, `run()` yield types, `SuperAgentService` facade.
- Fallback behaviors preserved exactly: no model → HANDOFF outcome with reason; malformed output → ANSWER outcome describing the problem; runtime error → ANSWER outcome with error reason.
- No network in tests.

---

### Task 1: Add langgraph dependency

- [ ] **Step 1:** `cd python && uv add langgraph`
- [ ] **Step 2:** `uv run python -c "from langgraph.graph import StateGraph; from langgraph.checkpoint.memory import InMemorySaver; print('ok')"`
- [ ] **Step 3:** Commit: `git add pyproject.toml uv.lock && git commit -m "feat: add langgraph dependency"`

### Task 2: Rewrite SuperAgent core on LangGraph (TDD)

**Files:**
- Rewrite: `python/quantcell/core/super_agent/core.py`
- Rewrite: `python/quantcell/core/super_agent/tests/test_super_agent.py`
- Delete: `python/quantcell/core/super_agent/tests/test_model_consistency_restart.py` (Agno restart internals; replaced by graph-rebuild test)

**Interfaces:**
- Consumes: `quantcell.utils.model.get_chat_model_for_agent("super_agent")`, `SUPER_AGENT_INSTRUCTION`, `SUPER_AGENT_EXPECTED_OUTPUT`.
- Produces: unchanged `SuperAgent` public API; internal `_get_or_init_graph()` returning compiled graph or None; `_parse_outcome(text) -> SuperAgentOutcome`.

- [ ] **Step 1:** Write new tests (fake chat model via `GenericFakeChatModel` subclass capturing prompts; monkeypatch `super_agent_mod.model_utils_mod.get_chat_model_for_agent`):
  1. ANSWER path: JSON reply → yields str chunk(s) then `SuperAgentOutcome(decision=ANSWER, answer_content=...)`
  2. HANDOFF path: enriched_query preserved
  3. Malformed reply → ANSWER outcome containing "malformed"
  4. `get_chat_model_for_agent` raising → HANDOFF fallback outcome with "unavailable" reason
  5. Conversation memory: second `run()` on same conversation_id sees prior Human+AI messages in the prompt
  6. Model change rebuilds graph; same model reuses graph
  7. Keep prompts-non-empty test
- [ ] **Step 2:** Run → FAIL (old implementation).
- [ ] **Step 3:** Implement the LangGraph rewrite per Architecture.
- [ ] **Step 4:** `uv run pytest quantcell/core/super_agent -q` → PASS.
- [ ] **Step 5:** Commit: `git commit -am "feat: migrate super agent to langgraph"`

### Task 3: Full verification + push

- [ ] **Step 1:** `uv run pytest -q` full suite → green (orchestrator/e2e tests unchanged).
- [ ] **Step 2:** `uv run python -c "import quantcell.server.main"` → clean.
- [ ] **Step 3:** `git push`
