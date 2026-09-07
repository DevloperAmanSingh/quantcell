"""LangGraph-based Super Agent.

The Super Agent triages user input before planning: it either answers simple
requests directly or hands off an enriched query to the Planner. It is a
single-node LangGraph whose state is checkpointed per conversation, so each
conversation keeps its own chat history (thread_id = conversation_id).

The public contract is frozen for the orchestrator:
`run(user_input)` yields zero or more `str` chunks (streamed model output,
surfaced by the orchestrator as reasoning) followed by exactly one
`SuperAgentOutcome`.
"""

import json
import re
from enum import Enum
from typing import Annotated, AsyncIterator, Optional, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from loguru import logger
from pydantic import BaseModel, Field

import quantcell.utils.model as model_utils_mod
from quantcell.core.super_agent.prompts import (
    SUPER_AGENT_EXPECTED_OUTPUT,
    SUPER_AGENT_INSTRUCTION,
)
from quantcell.core.types import UserInput


class SuperAgentDecision(str, Enum):
    ANSWER = "answer"
    HANDOFF_TO_PLANNER = "handoff_to_planner"


class SuperAgentOutcome(BaseModel):
    decision: SuperAgentDecision = Field(..., description="Super Agent's decision")
    # Optional enriched result data
    answer_content: Optional[str] = Field(
        None, description="Optional direct answer when decision is 'answer'"
    )
    enriched_query: Optional[str] = Field(
        None, description="Optional concise restatement to forward to Planner"
    )
    reason: Optional[str] = Field(None, description="Brief rationale for the decision")


class TriageState(TypedDict):
    """Graph state: rolling chat history plus the parsed triage outcome."""

    messages: Annotated[list[BaseMessage], add_messages]
    outcome: Optional[SuperAgentOutcome]


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_outcome(text: str, model_description: str) -> SuperAgentOutcome:
    """Parse the model reply into a SuperAgentOutcome.

    Malformed output degrades to an ANSWER outcome describing the problem, so
    the orchestrator always receives a well-typed decision.
    """
    cleaned = _CODE_FENCE_RE.sub("", text.strip()).strip()
    try:
        return SuperAgentOutcome.model_validate_json(cleaned)
    except Exception:
        pass
    # Some models wrap JSON in prose; salvage the outermost object if present.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return SuperAgentOutcome.model_validate(
                json.loads(cleaned[start : end + 1])
            )
        except Exception:
            pass
    return SuperAgentOutcome(
        decision=SuperAgentDecision.ANSWER,
        answer_content=(
            f"SuperAgent produced a malformed response: `{text}`. "
            f"Please check the capabilities of your model `{model_description}` "
            "and try again later."
        ),
    )


class SuperAgent:
    """Triage agent: single-node LangGraph with per-conversation memory."""

    name: str = "QuantCellAgent"

    def __init__(self) -> None:
        # Lazy init: building the graph requires a resolved chat model.
        self._graph = None
        self._model = None
        self._model_identity: Optional[str] = None
        # One checkpointer for the agent's lifetime; per-conversation threads.
        self._checkpointer = InMemorySaver()

    def _resolve_model(self):
        try:
            return model_utils_mod.get_chat_model_for_agent("super_agent")
        except Exception as e:
            logger.warning(f"SuperAgent: failed to resolve chat model: {e}")
            return None

    def _get_or_init_graph(self):
        """Build (or rebuild on model change) the compiled triage graph.

        Rebuilding preserves the checkpointer, so conversation history
        survives a model switch made through the settings UI.
        """
        model = self._resolve_model()
        if model is None:
            return self._graph  # keep serving the existing graph if any

        identity = model_utils_mod.describe_chat_model(model)
        if self._graph is not None and identity == self._model_identity:
            return self._graph

        if self._graph is not None:
            logger.info(
                f"SuperAgent: model changed {self._model_identity} -> {identity}, "
                "rebuilding graph"
            )

        self._model = model
        self._model_identity = identity

        system_prompt = SUPER_AGENT_INSTRUCTION + "\n" + SUPER_AGENT_EXPECTED_OUTPUT

        async def triage(state: TriageState) -> dict:
            response = await model.ainvoke(
                [SystemMessage(content=system_prompt), *state["messages"]]
            )
            outcome = _parse_outcome(str(response.content), identity)
            return {"messages": [response], "outcome": outcome}

        graph = StateGraph(TriageState)
        graph.add_node("triage", triage)
        graph.add_edge(START, "triage")
        graph.add_edge("triage", END)
        self._graph = graph.compile(checkpointer=self._checkpointer)
        return self._graph

    async def run(
        self, user_input: UserInput
    ) -> AsyncIterator[str | SuperAgentOutcome]:
        """Run triage: stream model output chunks, then yield the outcome."""
        graph = self._get_or_init_graph()
        if graph is None:
            # Fallback: hand off directly to planner without a super agent model
            yield SuperAgentOutcome(
                decision=SuperAgentDecision.HANDOFF_TO_PLANNER,
                enriched_query=user_input.query,
                reason="SuperAgent unavailable: missing model/provider configuration",
            )
            return

        config = {"configurable": {"thread_id": user_input.meta.conversation_id}}
        try:
            async for chunk, _metadata in graph.astream(
                {"messages": [HumanMessage(content=user_input.query)]},
                config,
                stream_mode="messages",
            ):
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield content

            state = await graph.aget_state(config)
            outcome = state.values.get("outcome")
            if not isinstance(outcome, SuperAgentOutcome):
                outcome = _parse_outcome(str(outcome), self._model_identity or "")
            yield outcome
        except Exception as e:
            yield SuperAgentOutcome(
                decision=SuperAgentDecision.ANSWER,
                reason=(
                    f"SuperAgent encountered an error: {e}."
                    f"Please check the capabilities of your model "
                    f"`{self._model_identity}` and try again later."
                ),
            )
