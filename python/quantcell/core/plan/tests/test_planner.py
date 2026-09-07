"""Tests for the LangGraph-based ExecutionPlanner."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, List, Optional

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult

import quantcell.core.plan.planner as planner_mod
from quantcell.core.plan.planner import ExecutionPlanner
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


class StubConnections:
    def __init__(self, cards: dict):
        self._cards = cards

    def get_planable_agent_cards(self) -> dict:
        return self._cards

    def get_agent_card(self, name: str):
        return self._cards.get(name)


def make_card(name: str, description: str):
    return SimpleNamespace(name=name, description=description, skills=[])


RESEARCH_CARDS = {
    "ResearchAgent": make_card("ResearchAgent", "Analyzes SEC filings")
}


def make_user_input(
    query: str, conversation_id: str = "conv-1", target_agent: str = "ResearchAgent"
) -> UserInput:
    return UserInput(
        query=query,
        target_agent_name=target_agent,
        meta=UserInputMetadata(conversation_id=conversation_id, user_id="user-1"),
    )


ADEQUATE_REPLY = json.dumps(
    {
        "tasks": [
            {
                "title": "Research Apple filings",
                "query": "Analyze AAPL 10-K",
                "agent_name": "ResearchAgent",
                "pattern": "once",
                "schedule_config": None,
            }
        ],
        "adequate": True,
        "reason": "Clear request.",
        "guidance_message": None,
    }
)

INADEQUATE_REPLY = json.dumps(
    {
        "tasks": [],
        "adequate": False,
        "reason": "Schedule needs confirmation.",
        "guidance_message": "Please confirm the daily 09:00 schedule.",
    }
)

HALLUCINATED_REPLY = json.dumps(
    {
        "tasks": [
            {
                "title": "Do something",
                "query": "q",
                "agent_name": "ImaginaryAgent",
                "pattern": "once",
                "schedule_config": None,
            }
        ],
        "adequate": True,
        "reason": "ok",
        "guidance_message": None,
    }
)


def patch_model(monkeypatch: pytest.MonkeyPatch, model) -> None:
    monkeypatch.setattr(
        planner_mod.model_utils_mod,
        "get_chat_model_for_agent",
        lambda agent_name, **kwargs: model,
    )


async def noop_callback(request) -> None:
    """Callback that never answers; used where no clarification is expected."""


@pytest.mark.asyncio
async def test_adequate_reply_produces_task_plan(monkeypatch):
    patch_model(monkeypatch, make_fake_model([ADEQUATE_REPLY]))
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    plan = await planner.create_plan(
        make_user_input("Analyze AAPL 10-K"), noop_callback, "thread-1"
    )

    assert plan.guidance_message is None
    assert len(plan.tasks) == 1
    task = plan.tasks[0]
    assert task.agent_name == "ResearchAgent"
    assert task.query == "Analyze AAPL 10-K"
    assert task.title == "Research Apple filings"
    assert task.thread_id == "thread-1"
    assert plan.conversation_id == "conv-1"


@pytest.mark.asyncio
async def test_agent_catalog_is_injected_into_prompt(monkeypatch):
    patch_model(monkeypatch, make_fake_model([ADEQUATE_REPLY]))
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    await planner.create_plan(make_user_input("do it"), noop_callback, "t")

    prompt_text = " ".join(
        str(getattr(m, "content", "")) for m in RecordingFakeChatModel.seen_prompts[0]
    )
    assert "ResearchAgent" in prompt_text
    assert "Analyzes SEC filings" in prompt_text


@pytest.mark.asyncio
async def test_hallucinated_agent_rejected_with_guidance(monkeypatch):
    patch_model(monkeypatch, make_fake_model([HALLUCINATED_REPLY]))
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    plan = await planner.create_plan(make_user_input("do it"), noop_callback, "t")

    assert plan.tasks == []
    assert "hallucinated" in (plan.guidance_message or "")


@pytest.mark.asyncio
async def test_inadequate_reply_interrupts_then_resumes(monkeypatch):
    model = make_fake_model([INADEQUATE_REPLY, ADEQUATE_REPLY])
    patch_model(monkeypatch, model)
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    prompts_seen: list[str] = []

    async def answering_callback(request) -> None:
        prompts_seen.append(request.prompt)
        # Answer asynchronously, as the orchestrator does via the registry.
        asyncio.get_event_loop().call_soon(request.provide_response, "confirmed 09:00")

    plan = await planner.create_plan(
        make_user_input("monitor TSLA daily"), answering_callback, "t"
    )

    assert prompts_seen == ["Please confirm the daily 09:00 schedule."]
    assert len(plan.tasks) == 1
    # The resumed generation must see the user's confirmation
    second_prompt_text = " ".join(
        str(getattr(m, "content", "")) for m in RecordingFakeChatModel.seen_prompts[1]
    )
    assert "confirmed 09:00" in second_prompt_text


@pytest.mark.asyncio
async def test_clarification_capped_at_three_rounds(monkeypatch):
    model = make_fake_model([INADEQUATE_REPLY] * 5)
    patch_model(monkeypatch, model)
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    callback_count = 0

    async def answering_callback(request) -> None:
        nonlocal callback_count
        callback_count += 1
        asyncio.get_event_loop().call_soon(request.provide_response, "still unclear")

    plan = await planner.create_plan(
        make_user_input("monitor something"), answering_callback, "t"
    )

    assert callback_count <= 3
    assert plan.tasks == []
    assert plan.guidance_message == "Please confirm the daily 09:00 schedule."


@pytest.mark.asyncio
async def test_malformed_reply_returns_guidance(monkeypatch):
    patch_model(monkeypatch, make_fake_model(["not json"]))
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    plan = await planner.create_plan(make_user_input("hello"), noop_callback, "t")

    assert plan.tasks == []
    assert "malformed" in (plan.guidance_message or "").lower()


@pytest.mark.asyncio
async def test_model_unavailable_returns_guidance(monkeypatch):
    def _raise(agent_name, **kwargs):
        raise ValueError("no provider")

    monkeypatch.setattr(
        planner_mod.model_utils_mod, "get_chat_model_for_agent", _raise
    )
    planner = ExecutionPlanner(StubConnections(RESEARCH_CARDS))

    plan = await planner.create_plan(make_user_input("hello"), noop_callback, "t")

    assert plan.tasks == []
    assert "unavailable" in (plan.guidance_message or "").lower()
