"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event


def _extract_text(content: object) -> str:
    """Normalize a chat model's .content into plain text.

    Some providers (e.g. Gemini with thinking enabled) return a list of
    content blocks instead of a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
    return str(content)


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


class Classification(BaseModel):
    """Structured intent classification output."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="The single best-matching route for this support query."
    )
    risk_level: Literal["high", "low"] = Field(
        description="'high' if the route is risky, 'low' otherwise."
    )
    reasoning: str = Field(default="", description="One short sentence explaining the choice.")


CLASSIFY_SYSTEM_PROMPT = """You are an intent classifier for a support-ticket agent.
Classify the user's query into exactly one route:

- risky: actions with side effects (refunds, deletions, cancellations, sending emails,
  account changes) that require human approval before execution.
- tool: information lookups that need an external system (order status, tracking,
  account search, diagnostics) but have no side effects.
- missing_info: the query is too vague or incomplete to act on (no concrete subject,
  no identifiers, unclear intent).
- error: the query describes a system failure, timeout, crash, or service outage.
- simple: general questions answerable directly, without tools or side effects.

Apply this priority when multiple could match: risky > tool > missing_info > error > simple.
Set risk_level to "high" only for the risky route; otherwise "low"."""


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM."""
    query = state.get("query", "")
    llm = get_llm()
    structured_llm = llm.with_structured_output(Classification)
    result: Classification = structured_llm.invoke(
        [
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
    )
    return {
        "route": result.route,
        "risk_level": result.risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified as {result.route}",
                reasoning=result.reasoning,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.
    """
    query = state.get("query", "")
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    proposed_action = state.get("proposed_action", "")

    if route == "error" and attempt < 2:
        result = f"ERROR: transient tool failure on attempt {attempt}"
        return {
            "tool_results": [result],
            "events": [make_event("tool", "failed", result, attempt=attempt)],
        }

    if proposed_action:
        result = f"mock_tool_success: executed approved action - {proposed_action}"
    else:
        result = f"mock_tool_success: retrieved data for query '{query[:60]}'"

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", result, attempt=attempt)],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Heuristic evaluation: a result is unsatisfactory if it looks like an error.
    """
    tool_results = state.get("tool_results", [])
    latest = tool_results[-1] if tool_results else ""
    evaluation_result = "needs_retry" if "ERROR" in latest else "success"
    return {
        "evaluation_result": evaluation_result,
        "events": [make_event("evaluate", "completed", f"evaluation={evaluation_result}")],
    }


ANSWER_SYSTEM_PROMPT = """You are a helpful support agent. Write a concise, friendly response
to the user's query, grounded strictly in the provided context. Do not invent facts that
are not present in the context. If an action was approved or executed, confirm it clearly."""


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM."""
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    context_lines = [f"User query: {query}"]
    if tool_results:
        context_lines.append("Tool results:\n" + "\n".join(tool_results))
    if approval is not None:
        context_lines.append(f"Approval decision: {approval}")
    context = "\n\n".join(context_lines)

    llm = get_llm()
    response = llm.invoke(
        [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]
    )
    final_answer = _extract_text(getattr(response, "content", response))

    return {
        "final_answer": final_answer,
        "events": [make_event("answer", "completed", "generated grounded response")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    question = (
        f"Your request ('{query}') is missing key details. "
        "Could you specify what you need help with — for example, an order number, "
        "account identifier, or the specific action you'd like taken?"
    )
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "requested clarification")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    proposed_action = f"Proposed action requiring approval: '{query}' (side effects: yes)"
    return {
        "proposed_action": proposed_action,
        "events": [make_event("risky_action", "completed", proposed_action)],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default: mock approval (approved=True) so tests and CI run offline.
    Extension: LANGGRAPH_INTERRUPT=true uses langgraph.types.interrupt() for real HITL.
    """
    proposed_action = state.get("proposed_action", "")

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        decision = interrupt(
            {"question": "Approve this action?", "proposed_action": proposed_action}
        )
        is_dict = isinstance(decision, dict)
        approved = bool(decision.get("approved", False)) if is_dict else bool(decision)
        reviewer = decision.get("reviewer", "human-reviewer") if is_dict else "human-reviewer"
        comment = decision.get("comment", "") if is_dict else ""
    else:
        approved = True
        reviewer = "mock-reviewer"
        comment = "auto-approved (mock mode)"

    approval = {"approved": approved, "reviewer": reviewer, "comment": comment}
    return {
        "approval": approval,
        "events": [make_event("approval", "completed", f"approved={approved}", reviewer=reviewer)],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt."""
    attempt = state.get("attempt", 0) + 1
    tool_results = state.get("tool_results", [])
    reason = tool_results[-1] if tool_results else "unknown transient failure"
    return {
        "attempt": attempt,
        "errors": [f"retry #{attempt}: {reason}"],
        "events": [make_event("retry", "completed", f"attempt incremented to {attempt}")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded."""
    attempt = state.get("attempt", 0)
    final_answer = (
        "We were unable to complete your request after multiple attempts. "
        "This has been escalated to our support team for manual follow-up."
    )
    return {
        "final_answer": final_answer,
        "errors": [f"dead_letter: exhausted retries after {attempt} attempts"],
        "events": [make_event("dead_letter", "completed", "max retries exhausted")],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
