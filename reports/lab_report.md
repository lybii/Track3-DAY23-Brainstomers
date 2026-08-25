# Day 08 Lab Report

## 1. Team

- Repo: github.com/lybii/Track3-DAY23_LeThiHaiYen_2A202601570
- Date: 2026-08-25

| Member | Student ID | Part | Files | Status |
|---|---|---|---|---|
| Lê Thị Hải Yến | 2A202601570 | 1 — State & LLM nodes | `state.py`, `nodes.py`, `llm.py` | Done |
| Nguyễn Hải Anh | 2A202601670 | 2 — Routing & graph wiring | `routing.py`, `graph.py` | Done |
| Tô Ngọc Hải | 2A202601580 | 3 — Persistence, metrics & report | `persistence.py`, `report.py` | Done |

## 2. Architecture

`state.py` defines `AgentState` (a `TypedDict`) with append-only reducers (`operator.add`) on `messages`, `tool_results`, `errors`, and `events` for a full audit trail, and overwrite fields for `route`, `attempt`, `evaluation_result`, `pending_question`, `proposed_action`, and `approval`. `nodes.py` implements all 10 node functions:

- `classify_node` — **LLM call** using `.with_structured_output(Classification)` (Pydantic model with `route`/`risk_level`/`reasoning`) to pick one of `simple | tool | missing_info | risky | error`, following the priority `risky > tool > missing_info > error > simple`.
- `tool_node` — mock tool call; simulates a transient `ERROR` result for `error`-route queries while `attempt < 2`, to exercise the retry loop.
- `evaluate_node` — heuristic gate: `"needs_retry"` if the latest `tool_results` entry contains `"ERROR"`, else `"success"`.
- `answer_node` — **LLM call** grounded in `tool_results` and `approval`, generating the final response text.
- `ask_clarification_node`, `risky_action_node`, `approval_node` (mock-approved by default, optional real `interrupt()` behind `LANGGRAPH_INTERRUPT=true`), `retry_or_fallback_node`, `dead_letter_node`, `finalize_node` — deterministic state transitions, no LLM required.

### Architecture (Part 2 scope)

`routing.py` implements routing functions for conditional edges:
- `route_after_classify`: Maps the `route` provided by `classify_node` to the appropriate next node.
- `route_after_evaluate`: Acts as a gate after a tool call, routing to `retry` if `evaluation_result` is `"needs_retry"`, otherwise proceeding to `answer`.
- `route_after_retry`: Bounds the retry loop by checking `attempt < max_attempts`. If the limit is reached, it routes to `dead_letter`, otherwise it goes back to `tool`.
- `route_after_approval`: Routes based on the human approval decision, proceeding to `tool` if approved, or routing to `clarify` if rejected.

`graph.py` wires everything together into a `StateGraph` using `AgentState`:
- Registers all node functions defined in `nodes.py`.
- Establishes unconditional edges for linear paths (e.g., `START -> intake -> classify`, `answer -> finalize -> END`).
- Applies the routing functions from `routing.py` as conditional edges to handle complex branching logic, retries, and approvals.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| messages | append | audit trail of node activity |
| tool_results | append | preserve every tool attempt across retries |
| errors | append | accumulate retry/failure history |
| events | append | full audit log for grading/debugging |
| route | overwrite | current route only |
| attempt | overwrite | current retry count |
| evaluation_result | overwrite | latest retry-loop gate decision |
| pending_question | overwrite | latest clarification question |
| proposed_action | overwrite | latest risky action description |
| approval | overwrite | latest approval decision |
| final_answer | overwrite | latest response to the user |

## 4. Scenario results

- Total scenarios: 7
- Success rate: 100.00%
- Avg nodes visited: 6.43
- Total retries: 3
- Total interrupts (approvals): 2

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | yes | 0 | 0 |
| S02_tool | tool | tool | yes | 0 | 0 |
| S03_missing | missing_info | missing_info | yes | 0 | 0 |
| S04_risky | risky | risky | yes | 0 | 1 |
| S05_error | error | error | yes | 2 | 0 |
| S06_delete | risky | risky | yes | 0 | 1 |
| S07_dead_letter | error | error | yes | 1 | 0 |

## 5. Failure analysis

1. Retry or tool failure: `tool_node` simulates a transient failure for `error`-route queries on the first two attempts. `evaluate_node` flags this via `evaluation_result="needs_retry"`, and `route_after_retry` bounds the loop with `attempt < max_attempts`; once exhausted, the flow moves to `dead_letter_node` instead of looping forever.
2. Risky action without approval: `risky_action_node` never executes side effects itself — it only prepares a `proposed_action` description. `approval_node` gates execution, and `route_after_approval` only sends the flow to `tool` when `approval.approved` is true; a rejection routes to `clarify` instead, so a side-effecting action can never run unapproved.

## 6. Persistence / recovery evidence

`persistence.py` supports `memory` (default, `MemorySaver`) and `sqlite` (`SqliteSaver` over a WAL-mode `sqlite3` connection) checkpointers. Each scenario run is invoked with a unique `thread_id` (`thread-<scenario_id>`) via `config={"configurable": {"thread_id": ...}}`, so state history is addressable per run and resumable across process restarts when the SQLite backend is selected.

## 7. Extension work

SQLite persistence (`build_checkpointer("sqlite")`) and an optional real HITL path (`approval_node` calls `langgraph.types.interrupt()` when `LANGGRAPH_INTERRUPT=true`) are implemented as extensions beyond the mocked default.

## 8. Improvement plan

With one more day: replace the heuristic `evaluate_node` with an LLM-as-judge for richer quality checks, add `Send()`-based parallel fan-out for multi-tool lookups, and build a small Streamlit approval UI on top of the real `interrupt()` HITL path.
