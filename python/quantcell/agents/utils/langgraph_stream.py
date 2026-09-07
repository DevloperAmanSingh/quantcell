"""Adapter from LangGraph ReAct agent streams to QuantCell StreamResponses.

Maps `graph.astream(..., stream_mode="messages")` output onto the streaming
contract consumed by the A2A executor:

- AI content tokens        -> streaming.message_chunk
- tool call initiation     -> streaming.tool_call_started (deduped by id)
- ToolMessage results      -> streaming.tool_call_completed
- stream end               -> streaming.done()

Used by every ReAct-style agent (research, news) so the `BaseAgent.stream()`
contract stays identical across the Agno -> LangGraph migration.
"""

from typing import AsyncGenerator, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage

from quantcell.core.agent.responses import streaming
from quantcell.core.types import StreamResponse


def _text_content(content) -> str:
    """Extract plain text from string or block-list message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


async def stream_react_agent(
    graph,
    messages: List[BaseMessage],
    config: Optional[dict] = None,
) -> AsyncGenerator[StreamResponse, None]:
    """Run a compiled ReAct graph and yield StreamResponses; ends with done()."""
    started_tool_calls: set[str] = set()

    async for chunk, _metadata in graph.astream(
        {"messages": messages}, config, stream_mode="messages"
    ):
        if isinstance(chunk, ToolMessage):
            yield streaming.tool_call_completed(
                _text_content(chunk.content), chunk.tool_call_id, chunk.name or ""
            )
            continue

        if isinstance(chunk, (AIMessageChunk, AIMessage)):
            for tool_call in chunk.tool_calls or []:
                tool_call_id = tool_call.get("id")
                tool_name = tool_call.get("name")
                if tool_call_id and tool_name and tool_call_id not in started_tool_calls:
                    started_tool_calls.add(tool_call_id)
                    yield streaming.tool_call_started(tool_call_id, tool_name)

            text = _text_content(chunk.content)
            if text:
                yield streaming.message_chunk(text)

    yield streaming.done()
