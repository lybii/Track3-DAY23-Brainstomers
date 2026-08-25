# Day 08 Lab Report

## 1. Team

- Repo: github.com/lybii/Track3-DAY23_LeThiHaiYen_2A202601570
- Date: 2026-08-25

| Member | Student ID | Part | Files | Status |
|---|---|---|---|---|
| Lê Thị Hải Yến | 2A202601570 | 1 — State & LLM nodes | `state.py`, `nodes.py`, `llm.py` | Done |
| Nguyễn Hải Anh | 2A202601670 | 2 — Routing & graph wiring | `routing.py`, `graph.py` | Done |
| (fill in) | (fill in) | 3 — Persistence, metrics & report | `persistence.py`, `report.py` | Pending |

## 2. Architecture (Part 1 scope)

`state.py` defines `AgentState` (a `TypedDict`) with append-only reducers (`operator.add`) on
`messages`, `tool_results`, `errors`, and `events` for a full audit trail, and overwrite fields
for `route`, `attempt`, `evaluation_result`, `pending_question`, `proposed_action`, and
`approval`. `nodes.py` implements all 10 node functions:

- `classify_node` — **LLM call** using `.with_structured_output(Classification)` (Pydantic model
  with `route`/`risk_level`/`reasoning`) to pick one of `simple | tool | missing_info | risky |
  error`, following the priority `risky > tool > missing_info > error > simple`.
- `tool_node` — mock tool call; simulates a transient `ERROR` result for `error`-route queries
  while `attempt < 2`, to exercise the retry loop once Part 2's graph wires it in.
- `evaluate_node` — heuristic gate: `"needs_retry"` if the latest `tool_results` entry contains
  `"ERROR"`, else `"success"`.
- `answer_node` — **LLM call** grounded in `tool_results` and `approval`, generating the final
  response text.
- `ask_clarification_node`, `risky_action_node`, `approval_node` (mock-approved by default,
  optional real `interrupt()` behind `LANGGRAPH_INTERRUPT=true`), `retry_or_fallback_node`,
  `dead_letter_node`, `finalize_node` — deterministic state transitions, no LLM required.

`llm.py` was extended with `load_dotenv()` at import time so `.env` is picked up both by the CLI
and by pytest (see `tests/conftest.py`).

### Architecture (Part 2 scope)

`routing.py` implements routing functions for conditional edges:
- `route_after_classify`: Maps the `route` provided by `classify_node` to the appropriate next node.
- `route_after_evaluate`: Acts as a gate after a tool call, routing to `retry` if `evaluation_result` is `"needs_retry"`, otherwise proceeding to `answer`.
- `route_after_retry`: Bounds the retry loop by checking `attempt < max_attempts`. If the limit is reached, it routes to `dead_letter`, otherwise it goes back to `tool`.
- `route_after_approval`: Routes based on the human approval decision, proceeding to `tool` if approved, or routing to `clarify` if rejected.

`graph.py` wires everything together into a `StateGraph` using `AgentState`:
- Registers all node functions defined in `nodes.py`.
- Establishes unconditional edges for linear paths (e.g., `START → intake → classify`, `answer → finalize → END`).
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

Not available yet — running scenarios end-to-end requires `graph.py` (Part 2) to compile the
`StateGraph`. Part 1's nodes were unit-tested in isolation with a real LLM call (Gemini,
`gemini-flash-lite-latest`) to confirm `classify_node` and `answer_node` work correctly; full
`outputs/metrics.json` will be generated once Part 2 lands.

## 5. Failure analysis

1. Retry or tool failure: `tool_node` simulates a transient failure for `error`-route queries on
   the first two attempts (`attempt < 2`), returning a result string containing `"ERROR"`.
   `evaluate_node` flags this via `evaluation_result="needs_retry"`. Bounding the loop (via
   `attempt < max_attempts`) is Part 2's responsibility in `route_after_retry`.
2. Risky action without approval: `risky_action_node` never executes side effects itself — it
   only prepares a `proposed_action` description. `approval_node` gates execution and defaults to
   mock-approved so the graph can run offline; only Part 2's `route_after_approval` decides
   whether an approved action is allowed to reach `tool_node`.

## 6. Persistence / recovery evidence

Not implemented in this part — see Part 3 (`persistence.py`).

## 7. Extension work

None in Part 1. Extensions (SQLite persistence, real HITL `interrupt()`) are split across Part 3
and the `approval_node` hook already exposed in `nodes.py` (`LANGGRAPH_INTERRUPT=true`).

## 8. Improvement plan

Once Parts 2 and 3 are merged: rerun `make run-scenarios`, verify all 7 sample scenarios route
correctly, and fill in sections 4, 6, and 7 with real metrics and persistence evidence.
