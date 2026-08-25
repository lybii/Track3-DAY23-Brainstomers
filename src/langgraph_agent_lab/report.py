"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data."""
    lines: list[str] = []
    lines.append("# Day 08 Lab Report")
    lines.append("")
    lines.append("## 1. Team")
    lines.append("")
    lines.append("- Repo: github.com/lybii/Track3-DAY23_LeThiHaiYen_2A202601570")
    lines.append("- Date: 2026-08-25")
    lines.append("")
    lines.append("| Member | Student ID | Part | Files | Status |")
    lines.append("|---|---|---|---|---|")
    lines.append("| Lê Thị Hải Yến | 2A202601570 | 1 — State & LLM nodes | `state.py`, `nodes.py`, `llm.py` | Done |")
    lines.append("| Nguyễn Hải Anh | 2A202601670 | 2 — Routing & graph wiring | `routing.py`, `graph.py` | Done |")
    lines.append("| Tô Ngọc Hải | 2A202601580 | 3 — Persistence, metrics & report | `persistence.py`, `report.py` | Done |")
    lines.append("")


    lines.append("## 2. Architecture")
    lines.append("")
    lines.append(
        "`state.py` defines `AgentState` (a `TypedDict`) with append-only reducers (`operator.add`) on "
        "`messages`, `tool_results`, `errors`, and `events` for a full audit trail, and overwrite fields "
        "for `route`, `attempt`, `evaluation_result`, `pending_question`, `proposed_action`, and "
        "`approval`. `nodes.py` implements all 10 node functions:"
    )
    lines.append("")
    lines.append(
        "- `classify_node` — **LLM call** using `.with_structured_output(Classification)` (Pydantic model "
        "with `route`/`risk_level`/`reasoning`) to pick one of `simple | tool | missing_info | risky | "
        "error`, following the priority `risky > tool > missing_info > error > simple`."
    )
    lines.append(
        "- `tool_node` — mock tool call; simulates a transient `ERROR` result for `error`-route queries "
        "while `attempt < 2`, to exercise the retry loop."
    )
    lines.append(
        "- `evaluate_node` — heuristic gate: `\"needs_retry\"` if the latest `tool_results` entry contains "
        "`\"ERROR\"`, else `\"success\"`."
    )
    lines.append(
        "- `answer_node` — **LLM call** grounded in `tool_results` and `approval`, generating the final "
        "response text."
    )
    lines.append(
        "- `ask_clarification_node`, `risky_action_node`, `approval_node` (mock-approved by default, "
        "optional real `interrupt()` behind `LANGGRAPH_INTERRUPT=true`), `retry_or_fallback_node`, "
        "`dead_letter_node`, `finalize_node` — deterministic state transitions, no LLM required."
    )
    lines.append("")
    lines.append("### Architecture (Part 2 scope)")
    lines.append("")
    lines.append("`routing.py` implements routing functions for conditional edges:")
    lines.append("- `route_after_classify`: Maps the `route` provided by `classify_node` to the appropriate next node.")
    lines.append("- `route_after_evaluate`: Acts as a gate after a tool call, routing to `retry` if `evaluation_result` is `\"needs_retry\"`, otherwise proceeding to `answer`.")
    lines.append("- `route_after_retry`: Bounds the retry loop by checking `attempt < max_attempts`. If the limit is reached, it routes to `dead_letter`, otherwise it goes back to `tool`.")
    lines.append("- `route_after_approval`: Routes based on the human approval decision, proceeding to `tool` if approved, or routing to `clarify` if rejected.")
    lines.append("")
    lines.append("`graph.py` wires everything together into a `StateGraph` using `AgentState`:")
    lines.append("- Registers all node functions defined in `nodes.py`.")
    lines.append("- Establishes unconditional edges for linear paths (e.g., `START -> intake -> classify`, `answer -> finalize -> END`).")
    lines.append("- Applies the routing functions from `routing.py` as conditional edges to handle complex branching logic, retries, and approvals.")
    lines.append("")

    lines.append("## 3. State schema")
    lines.append("")
    lines.append("| Field | Reducer | Why |")
    lines.append("|---|---|---|")
    lines.append("| messages | append | audit trail of node activity |")
    lines.append("| tool_results | append | preserve every tool attempt across retries |")
    lines.append("| errors | append | accumulate retry/failure history |")
    lines.append("| events | append | full audit log for grading/debugging |")
    lines.append("| route | overwrite | current route only |")
    lines.append("| attempt | overwrite | current retry count |")
    lines.append("| evaluation_result | overwrite | latest retry-loop gate decision |")
    lines.append("| pending_question | overwrite | latest clarification question |")
    lines.append("| proposed_action | overwrite | latest risky action description |")
    lines.append("| approval | overwrite | latest approval decision |")
    lines.append("| final_answer | overwrite | latest response to the user |")
    lines.append("")

    lines.append("## 4. Scenario results")
    lines.append("")
    lines.append(f"- Total scenarios: {metrics.total_scenarios}")
    lines.append(f"- Success rate: {metrics.success_rate:.2%}")
    lines.append(f"- Avg nodes visited: {metrics.avg_nodes_visited:.2f}")
    lines.append(f"- Total retries: {metrics.total_retries}")
    lines.append(f"- Total interrupts (approvals): {metrics.total_interrupts}")
    lines.append("")
    lines.append("| Scenario | Expected route | Actual route | Success | Retries | Interrupts |")
    lines.append("|---|---|---|---:|---:|---:|")
    for item in metrics.scenario_metrics:
        lines.append(
            f"| {item.scenario_id} | {item.expected_route} | {item.actual_route} | "
            f"{'yes' if item.success else 'no'} | {item.retry_count} | {item.interrupt_count} |"
        )
    lines.append("")

    lines.append("## 5. Failure analysis")
    lines.append("")
    lines.append(
        "1. Retry or tool failure: `tool_node` simulates a transient failure for `error`-route "
        "queries on the first two attempts. `evaluate_node` flags this via `evaluation_result="
        '\"needs_retry\"`, and `route_after_retry` bounds the loop with `attempt < max_attempts`; '
        "once exhausted, the flow moves to `dead_letter_node` instead of looping forever."
    )
    lines.append(
        "2. Risky action without approval: `risky_action_node` never executes side effects "
        "itself — it only prepares a `proposed_action` description. `approval_node` gates "
        "execution, and `route_after_approval` only sends the flow to `tool` when "
        "`approval.approved` is true; a rejection routes to `clarify` instead, so a "
        "side-effecting action can never run unapproved."
    )
    lines.append("")

    lines.append("## 6. Persistence / recovery evidence")
    lines.append("")
    lines.append(
        "`persistence.py` supports `memory` (default, `MemorySaver`) and `sqlite` "
        "(`SqliteSaver` over a WAL-mode `sqlite3` connection) checkpointers. Each scenario run is "
        "invoked with a unique `thread_id` (`thread-<scenario_id>`) via "
        '`config={"configurable": {"thread_id": ...}}`, so state history is addressable per '
        "run and resumable across process restarts when the SQLite backend is selected."
    )
    lines.append("")

    lines.append("## 7. Extension work")
    lines.append("")
    lines.append(
        "SQLite persistence (`build_checkpointer(\"sqlite\")`) and an optional real HITL path "
        "(`approval_node` calls `langgraph.types.interrupt()` when `LANGGRAPH_INTERRUPT=true`) are "
        "implemented as extensions beyond the mocked default."
    )
    lines.append("")

    lines.append("## 8. Improvement plan")
    lines.append("")
    lines.append(
        "With one more day: replace the heuristic `evaluate_node` with an LLM-as-judge for richer "
        "quality checks, add `Send()`-based parallel fan-out for multi-tool lookups, and build a "
        "small Streamlit approval UI on top of the real `interrupt()` HITL path."
    )
    lines.append("")

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")

