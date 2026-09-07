"""Tests for the LangGraph ReAct -> StreamResponse adapter."""

from __future__ import annotations

from typing import Any, Sequence

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from quantcell.agents.utils.langgraph_stream import stream_react_agent
from quantcell.core.types import StreamResponseEvent, TaskStatusEvent


class FakeToolCallingModel(GenericFakeChatModel):
    """Fake chat model usable inside create_react_agent (bind_tools -> self)."""

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any):
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        # GenericFakeChatModel cannot stream empty-content tool-call messages;
        # emit each scripted message as one complete chunk instead.
        import json

        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk

        result = self._generate(messages, stop=stop, **kwargs)
        message = result.generations[0].message
        tool_call_chunks = [
            {
                "name": tc["name"],
                "args": json.dumps(tc["args"]),
                "id": tc["id"],
                "index": i,
                "type": "tool_call_chunk",
            }
            for i, tc in enumerate(getattr(message, "tool_calls", []) or [])
        ]
        chunk = AIMessageChunk(
            content=message.content, tool_call_chunks=tool_call_chunks
        )
        if run_manager:
            run_manager.on_llm_new_token("", chunk=ChatGenerationChunk(message=chunk))
        yield ChatGenerationChunk(message=chunk)


def lookup_price(symbol: str) -> str:
    """Look up the latest price for a symbol."""
    return f"{symbol}: 123.45"


@pytest.mark.asyncio
async def test_react_stream_maps_tool_calls_and_content():
    model = FakeToolCallingModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup_price",
                            "args": {"symbol": "AAPL"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="AAPL trades at 123.45"),
            ]
        )
    )
    graph = create_react_agent(model, [lookup_price])

    responses = []
    async for resp in stream_react_agent(graph, [HumanMessage(content="price of AAPL?")]):
        responses.append(resp)

    events = [r.event for r in responses]
    assert StreamResponseEvent.TOOL_CALL_STARTED in events
    assert StreamResponseEvent.TOOL_CALL_COMPLETED in events
    assert StreamResponseEvent.MESSAGE_CHUNK in events
    # done() terminates the stream
    assert events[-1] == TaskStatusEvent.TASK_COMPLETED

    started = next(r for r in responses if r.event == StreamResponseEvent.TOOL_CALL_STARTED)
    assert started.metadata["tool_call_id"] == "call-1"
    assert started.metadata["tool_name"] == "lookup_price"

    completed = next(
        r for r in responses if r.event == StreamResponseEvent.TOOL_CALL_COMPLETED
    )
    assert completed.metadata["tool_result"] == "AAPL: 123.45"

    text = "".join(
        r.content or "" for r in responses if r.event == StreamResponseEvent.MESSAGE_CHUNK
    )
    assert "AAPL trades at 123.45" in text

    # started must precede completed
    assert events.index(StreamResponseEvent.TOOL_CALL_STARTED) < events.index(
        StreamResponseEvent.TOOL_CALL_COMPLETED
    )


@pytest.mark.asyncio
async def test_react_stream_plain_answer_without_tools():
    model = FakeToolCallingModel(messages=iter([AIMessage(content="Just an answer")]))
    graph = create_react_agent(model, [lookup_price])

    responses = [
        r async for r in stream_react_agent(graph, [HumanMessage(content="hi")])
    ]
    events = [r.event for r in responses]
    assert StreamResponseEvent.TOOL_CALL_STARTED not in events
    assert events[-1] == TaskStatusEvent.TASK_COMPLETED
    text = "".join(
        r.content or "" for r in responses if r.event == StreamResponseEvent.MESSAGE_CHUNK
    )
    assert "Just an answer" in text
