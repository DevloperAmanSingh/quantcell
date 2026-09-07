"""Tests for the LangGraph-based SuperAgent."""

from __future__ import annotations

import json
from typing import Any, List, Optional

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult

import quantcell.core.super_agent.core as super_agent_mod
from quantcell.core.super_agent.core import (
    SuperAgent,
    SuperAgentDecision,
    SuperAgentOutcome,
)
from quantcell.core.super_agent.service import SuperAgentService
from quantcell.core.types import UserInput, UserInputMetadata


class RecordingFakeChatModel(GenericFakeChatModel):
    """Fake chat model that records every prompt it receives."""

    seen_prompts: List[list] = []

    def _generate(
        self,
        messages: list,
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        type(self).seen_prompts.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def make_fake_model(replies: list[str]) -> RecordingFakeChatModel:
    RecordingFakeChatModel.seen_prompts = []
    return RecordingFakeChatModel(
        messages=iter([AIMessage(content=reply) for reply in replies])
    )


def make_user_input(query: str, conversation_id: str = "conv-1") -> UserInput:
    return UserInput(
        query=query,
        target_agent_name="QuantCellAgent",
        meta=UserInputMetadata(conversation_id=conversation_id, user_id="user-1"),
    )


async def collect_run(agent: SuperAgent, user_input: UserInput):
    chunks: list[str] = []
    outcome: SuperAgentOutcome | None = None
    async for item in agent.run(user_input):
        if isinstance(item, SuperAgentOutcome):
            outcome = item
        else:
            chunks.append(item)
    return chunks, outcome


ANSWER_REPLY = json.dumps(
    {
        "decision": "answer",
        "answer_content": "4",
        "reason": "Simple arithmetic.",
    }
)

HANDOFF_REPLY = json.dumps(
    {
        "decision": "handoff_to_planner",
        "enriched_query": "Compare AAPL and MSFT valuation over the last quarter",
        "reason": "Needs specialist tools.",
    }
)


@pytest.fixture
def patch_model(monkeypatch: pytest.MonkeyPatch):
    def _patch(model):
        monkeypatch.setattr(
            super_agent_mod.model_utils_mod,
            "get_chat_model_for_agent",
            lambda agent_name, **kwargs: model,
        )

    return _patch


@pytest.mark.asyncio
async def test_answer_path_yields_chunks_then_outcome(patch_model):
    patch_model(make_fake_model([ANSWER_REPLY]))
    chunks, outcome = await collect_run(SuperAgent(), make_user_input("What is 2+2?"))

    assert outcome is not None
    assert outcome.decision == SuperAgentDecision.ANSWER
    assert outcome.answer_content == "4"
    # Streamed content is the model reply (chunking granularity may vary)
    assert "answer" in "".join(chunks)


@pytest.mark.asyncio
async def test_handoff_path_preserves_enriched_query(patch_model):
    patch_model(make_fake_model([HANDOFF_REPLY]))
    chunks, outcome = await collect_run(
        SuperAgent(), make_user_input("Compare AAPL vs MSFT")
    )

    assert outcome is not None
    assert outcome.decision == SuperAgentDecision.HANDOFF_TO_PLANNER
    assert outcome.enriched_query == (
        "Compare AAPL and MSFT valuation over the last quarter"
    )


@pytest.mark.asyncio
async def test_code_fenced_json_is_parsed(patch_model):
    patch_model(make_fake_model([f"```json\n{ANSWER_REPLY}\n```"]))
    _, outcome = await collect_run(SuperAgent(), make_user_input("What is 2+2?"))

    assert outcome is not None
    assert outcome.decision == SuperAgentDecision.ANSWER


@pytest.mark.asyncio
async def test_malformed_reply_produces_answer_with_error(patch_model):
    patch_model(make_fake_model(["this is not json at all"]))
    _, outcome = await collect_run(SuperAgent(), make_user_input("hello"))

    assert outcome is not None
    assert outcome.decision == SuperAgentDecision.ANSWER
    assert "malformed" in (outcome.answer_content or "").lower()


@pytest.mark.asyncio
async def test_model_unavailable_falls_back_to_handoff(monkeypatch):
    def _raise(agent_name, **kwargs):
        raise ValueError("no provider configured")

    monkeypatch.setattr(
        super_agent_mod.model_utils_mod, "get_chat_model_for_agent", _raise
    )
    _, outcome = await collect_run(SuperAgent(), make_user_input("hello"))

    assert outcome is not None
    assert outcome.decision == SuperAgentDecision.HANDOFF_TO_PLANNER
    assert outcome.enriched_query == "hello"
    assert "unavailable" in (outcome.reason or "").lower()


@pytest.mark.asyncio
async def test_conversation_memory_across_runs(patch_model):
    model = make_fake_model([ANSWER_REPLY, ANSWER_REPLY])
    patch_model(model)
    agent = SuperAgent()

    await collect_run(agent, make_user_input("first question", "conv-mem"))
    await collect_run(agent, make_user_input("second question", "conv-mem"))

    assert len(RecordingFakeChatModel.seen_prompts) == 2
    second_prompt_text = " ".join(
        str(getattr(m, "content", "")) for m in RecordingFakeChatModel.seen_prompts[1]
    )
    # Second turn must include the first turn's exchange (checkpointed history)
    assert "first question" in second_prompt_text


@pytest.mark.asyncio
async def test_separate_conversations_do_not_share_history(patch_model):
    model = make_fake_model([ANSWER_REPLY, ANSWER_REPLY])
    patch_model(model)
    agent = SuperAgent()

    await collect_run(agent, make_user_input("secret alpha", "conv-a"))
    await collect_run(agent, make_user_input("other topic", "conv-b"))

    second_prompt_text = " ".join(
        str(getattr(m, "content", "")) for m in RecordingFakeChatModel.seen_prompts[1]
    )
    assert "secret alpha" not in second_prompt_text


@pytest.mark.asyncio
async def test_model_change_rebuilds_graph(monkeypatch):
    model_a = make_fake_model([ANSWER_REPLY])
    agent = SuperAgent()

    monkeypatch.setattr(
        super_agent_mod.model_utils_mod,
        "get_chat_model_for_agent",
        lambda agent_name, **kwargs: model_a,
    )
    await collect_run(agent, make_user_input("q1"))
    graph_first = agent._graph

    # Same model -> same compiled graph
    await collect_run(agent, make_user_input("q2"))
    assert agent._graph is graph_first

    # Different model identity (different class name) -> rebuilt graph
    class OtherFakeChatModel(RecordingFakeChatModel):
        pass

    model_b = OtherFakeChatModel(messages=iter([AIMessage(content=ANSWER_REPLY)]))
    monkeypatch.setattr(
        super_agent_mod.model_utils_mod,
        "get_chat_model_for_agent",
        lambda agent_name, **kwargs: model_b,
    )
    await collect_run(agent, make_user_input("q3"))
    assert agent._graph is not graph_first


@pytest.mark.asyncio
async def test_service_facade_passthrough(patch_model):
    patch_model(make_fake_model([ANSWER_REPLY]))
    service = SuperAgentService()
    outcome = None
    async for item in service.run(make_user_input("What is 2+2?")):
        if isinstance(item, SuperAgentOutcome):
            outcome = item
    assert outcome is not None
    assert service.name == SuperAgent.name


def test_super_agent_prompts_are_non_empty():
    from quantcell.core.super_agent.prompts import (
        SUPER_AGENT_EXPECTED_OUTPUT,
        SUPER_AGENT_INSTRUCTION,
    )

    assert SUPER_AGENT_INSTRUCTION.strip()
    assert SUPER_AGENT_EXPECTED_OUTPUT.strip()
