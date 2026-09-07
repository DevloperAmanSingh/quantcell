"""Planner: create execution plans from user input.

LangGraph-based ExecutionPlanner. A three-node graph turns a user request
into a validated `PlannerResponse`:

    generate -> validate -> (END | clarify -> generate)

- `generate` prompts the chat model with the planner instruction, a live
  catalog of planable agent cards, and the JSON output contract, then parses
  the reply into `PlannerResponse`.
- `validate` is the hallucination guard: any task naming an unregistered
  agent turns the response into guidance instead of an executable plan.
- `clarify` implements human-in-the-loop via LangGraph `interrupt()`: when
  the planner needs confirmation (e.g. schedules), the graph pauses, the
  orchestrator surfaces the prompt through `UserInputRequest`, and the
  user's answer resumes the graph with `Command(resume=...)`. Rounds are
  capped so an indecisive model cannot loop forever.

The public contract (`create_plan(user_input, user_input_callback,
thread_id)`) is unchanged from the Agno implementation, so PlanService and
the orchestrator are untouched.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Annotated, Callable, List, Optional, Tuple, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from loguru import logger

import quantcell.utils.model as model_utils_mod
from quantcell.core.agent.connect import RemoteConnections
from quantcell.core.task.models import Task, TaskStatus
from quantcell.core.types import UserInput
from quantcell.utils import generate_uuid
from quantcell.utils.uuid import generate_conversation_id

from .models import ExecutionPlan, PlannerInput, PlannerResponse
from .prompts import (
    PLANNER_EXPECTED_OUTPUT,
    PLANNER_INSTRUCTION,
)

MAX_CLARIFICATION_ROUNDS = 3

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class UserInputRequest:
    """
    Represents a request for user input during plan creation or execution.

    This class uses asyncio.Event to enable non-blocking waiting for user responses
    in the Human-in-the-Loop workflow.
    """

    def __init__(self, prompt: str):
        """Create a new request object for planner-driven user input.

        Args:
            prompt: Human-readable prompt describing the information needed.
        """
        self.prompt = prompt
        self.response: Optional[str] = None
        self.event = asyncio.Event()

    async def wait_for_response(self) -> str:
        """Block until a response is provided and return it."""
        await self.event.wait()
        return self.response

    def provide_response(self, response: str):
        """Supply the user's response and wake any waiter."""
        self.response = response
        self.event.set()


class PlannerState(TypedDict):
    """Graph state for one planning run (thread_id = conversation_id)."""

    messages: Annotated[List[BaseMessage], add_messages]
    planner_response: Optional[PlannerResponse]
    # True when the response is final guidance that must NOT enter the
    # clarification loop (malformed output, hallucinated agents).
    terminal_guidance: bool
    clarify_count: int


def _parse_planner_response(text: str, model_description: str) -> PlannerResponse:
    """Parse the model reply into a PlannerResponse; degrade to guidance."""
    cleaned = _CODE_FENCE_RE.sub("", text.strip()).strip()
    try:
        return PlannerResponse.model_validate_json(cleaned)
    except Exception:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return PlannerResponse.model_validate(json.loads(cleaned[start : end + 1]))
        except Exception:
            pass
    return PlannerResponse(
        tasks=[],
        adequate=False,
        reason="malformed planner output",
        guidance_message=(
            f"Planner produced a malformed response: `{text}`. "
            f"Please check the capabilities of your model `{model_description}` "
            "and try again later."
        ),
    )


class ExecutionPlanner:
    """
    Creates execution plans by analyzing user input and determining appropriate agent tasks.

    Uses a LangGraph state machine with interrupt-based Human-in-the-Loop:
    the graph pauses when clarification is needed and resumes with the
    user's answer.
    """

    def __init__(
        self,
        agent_connections: RemoteConnections,
    ):
        self.agent_connections = agent_connections
        # Lazy graph construction: requires a resolved chat model.
        self._graph = None
        self._model_identity: Optional[str] = None
        self._checkpointer = InMemorySaver()

    # ------------------------
    # Graph construction
    # ------------------------

    def _render_agent_catalog(self) -> str:
        """Render all planable agent cards as prompt context.

        Replaces the former LLM tools (`tool_get_enabled_agents`,
        `tool_get_agent_description`): the catalog is always in context, so
        planning needs no tool round-trips.
        """
        cards = self.agent_connections.get_planable_agent_cards()
        parts = ["<available_agents>"]
        for agent_name, card in cards.items():
            parts.append(f"<{agent_name}>")
            parts.append(agentcard_to_prompt(card))
            parts.append(f"</{agent_name}>")
        parts.append("</available_agents>")
        return "\n".join(parts)

    def _resolve_model(self):
        try:
            # Planner shares the super_agent model configuration (parity with
            # the previous implementation).
            return model_utils_mod.get_chat_model_for_agent("super_agent")
        except Exception as e:
            logger.warning(f"Planner: failed to resolve chat model: {e}")
            return None

    def _get_or_init_graph(self):
        """Build (or rebuild on model change) the compiled planning graph."""
        model = self._resolve_model()
        if model is None:
            return self._graph

        identity = model_utils_mod.describe_chat_model(model)
        if self._graph is not None and identity == self._model_identity:
            return self._graph

        self._model_identity = identity

        async def generate(state: PlannerState) -> dict:
            system_prompt = "\n".join(
                [
                    PLANNER_INSTRUCTION,
                    self._render_agent_catalog(),
                    PLANNER_EXPECTED_OUTPUT,
                ]
            )
            response = await model.ainvoke(
                [SystemMessage(content=system_prompt), *state["messages"]]
            )
            parsed = _parse_planner_response(str(response.content), identity)
            return {
                "messages": [response],
                "planner_response": parsed,
                "terminal_guidance": parsed.reason == "malformed planner output",
            }

        def validate(state: PlannerState) -> dict:
            parsed = state["planner_response"]
            if parsed is None or not parsed.tasks:
                return {}
            planable = set(self.agent_connections.get_planable_agent_cards().keys())
            invalid = {t.agent_name for t in parsed.tasks if t.agent_name not in planable}
            if not invalid:
                return {}
            invalid_list = ", ".join(sorted(invalid))
            logger.warning(f"Planner proposed unsupported agents: {invalid_list}")
            return {
                "planner_response": PlannerResponse(
                    tasks=[],
                    adequate=False,
                    reason="unsupported agents",
                    guidance_message=(
                        f"Planner selected unsupported agent(s): {invalid_list}. "
                        f"Maybe the chosen model `{identity}` hallucinated."
                    ),
                ),
                "terminal_guidance": True,
            }

        def clarify(state: PlannerState) -> dict:
            parsed = state["planner_response"]
            prompt = parsed.guidance_message or parsed.reason or "More detail needed."
            answer = interrupt(prompt)
            return {
                "messages": [HumanMessage(content=str(answer))],
                "clarify_count": state["clarify_count"] + 1,
            }

        def route_after_validate(state: PlannerState) -> str:
            parsed = state["planner_response"]
            if parsed is None or state["terminal_guidance"]:
                return END
            if parsed.adequate and parsed.tasks:
                return END
            if parsed.guidance_message and state["clarify_count"] < (
                MAX_CLARIFICATION_ROUNDS
            ):
                return "clarify"
            return END

        graph = StateGraph(PlannerState)
        graph.add_node("generate", generate)
        graph.add_node("validate", validate)
        graph.add_node("clarify", clarify)
        graph.add_edge(START, "generate")
        graph.add_edge("generate", "validate")
        graph.add_conditional_edges(
            "validate", route_after_validate, {END: END, "clarify": "clarify"}
        )
        graph.add_edge("clarify", "generate")
        self._graph = graph.compile(checkpointer=self._checkpointer)
        return self._graph

    # ------------------------
    # Public API
    # ------------------------

    async def create_plan(
        self,
        user_input: UserInput,
        user_input_callback: Callable,
        thread_id: str,
    ) -> ExecutionPlan:
        """
        Create an execution plan from user input.

        `user_input_callback` is invoked with a `UserInputRequest` whenever the
        planning graph interrupts for clarification; the orchestrator registers
        the request and the user's eventual answer resumes the graph.
        """
        conversation_id = user_input.meta.conversation_id
        plan = ExecutionPlan(
            plan_id=generate_uuid("plan"),
            conversation_id=conversation_id,
            user_id=user_input.meta.user_id,
            orig_query=user_input.query,
            created_at=datetime.now().isoformat(),
        )

        tasks, guidance_message = await self._run_graph(
            user_input, conversation_id, user_input_callback, thread_id
        )
        plan.tasks = tasks
        plan.guidance_message = guidance_message
        return plan

    async def _run_graph(
        self,
        user_input: UserInput,
        conversation_id: str,
        user_input_callback: Callable,
        thread_id: str,
    ) -> Tuple[List[Task], Optional[str]]:
        graph = self._get_or_init_graph()
        if graph is None:
            return [], (
                "Planner is unavailable: failed to initialize model/provider. "
                "Please configure a valid API key or provider settings and retry."
            )

        config = {"configurable": {"thread_id": conversation_id}}
        payload = PlannerInput(
            target_agent_name=user_input.target_agent_name or "",
            query=user_input.query,
        ).model_dump_json()
        graph_input = {
            "messages": [HumanMessage(content=payload)],
            "planner_response": None,
            "terminal_guidance": False,
            "clarify_count": 0,
        }

        try:
            result = await graph.ainvoke(graph_input, config)
            while "__interrupt__" in result:
                prompt = str(result["__interrupt__"][0].value)
                request = UserInputRequest(prompt)
                await user_input_callback(request)
                answer = await request.wait_for_response()
                result = await graph.ainvoke(Command(resume=answer), config)
        except Exception as exc:
            logger.exception("Planner run failed: %s", exc)
            return [], (
                f"Planner encountered an error during execution: {exc}. "
                f"Please check the capabilities of your model "
                f"`{self._model_identity}` and try again later."
            )

        plan_raw = result.get("planner_response")
        if not isinstance(plan_raw, PlannerResponse):
            return [], (
                f"Planner produced a malformed response: `{plan_raw}`. "
                f"Please check the capabilities of your model "
                f"`{self._model_identity}` and try again later."
            )
        logger.info(f"Planner produced plan: {plan_raw}")

        guidance_message = plan_raw.guidance_message or plan_raw.reason
        if not plan_raw.adequate or not plan_raw.tasks:
            logger.info(f"Planner needs user guidance: {guidance_message}")
            return [], guidance_message

        tasks = [
            self._create_task(
                t,
                user_input.meta.user_id,
                conversation_id=user_input.meta.conversation_id,
                thread_id=thread_id,
                handoff_from_super_agent=(not user_input.target_agent_name),
            )
            for t in plan_raw.tasks
        ]
        return tasks, None

    def _create_task(
        self,
        task_brief,
        user_id: str,
        conversation_id: str | None = None,
        thread_id: str | None = None,
        handoff_from_super_agent: bool = False,
    ) -> Task:
        """Create a new task for the specified agent from a planning brief."""
        # Reuse parent thread_id across subagent handoff.
        # When handing off from Super Agent, a NEW conversation_id is created for
        # the subagent, but we PRESERVE the parent thread_id to correlate the
        # entire flow as one interaction.
        if handoff_from_super_agent:
            conversation_id = generate_conversation_id()

        return Task(
            conversation_id=conversation_id,
            thread_id=thread_id,
            user_id=user_id,
            agent_name=task_brief.agent_name,
            status=TaskStatus.PENDING,
            title=task_brief.title,
            query=task_brief.query,
            pattern=task_brief.pattern,
            schedule_config=task_brief.schedule_config,
            handoff_from_super_agent=handoff_from_super_agent,
        )


def agentcard_to_prompt(card):
    """Convert an AgentCard to an LLM-friendly prompt string."""

    prompt = f"# Agent: {card.name}\n\n"
    prompt += f"**Description:** {card.description}\n\n"

    if getattr(card, "skills", None):
        prompt += "## Available Skills\n\n"
        for i, skill in enumerate(card.skills, 1):
            prompt += f"### {i}. {skill.name} (`{skill.id}`)\n\n"
            prompt += f"**Description:** {skill.description}\n\n"
            if skill.examples:
                prompt += "**Examples:**\n"
                for example in skill.examples:
                    prompt += f"- {example}\n"
                prompt += "\n"
            if skill.tags:
                tags_str = ", ".join([f"`{tag}`" for tag in skill.tags])
                prompt += f"**Tags:** {tags_str}\n\n"
            if i < len(card.skills):
                prompt += "---\n\n"

    return prompt.strip()
