from langgraph_agent_lab.metrics import ScenarioMetric, summarize_metrics
from langgraph_agent_lab.report import render_report, write_report


def test_render_report(tmp_path):
    scenario = ScenarioMetric(
        scenario_id="S01_simple",
        success=True,
        expected_route="simple",
        actual_route="simple",
        nodes_visited=4,
        retry_count=0,
        interrupt_count=0,
    )
    metrics_report = summarize_metrics([scenario])
    rendered = render_report(metrics_report)

    assert "# Day 08 Lab Report" in rendered
    assert "S01_simple" in rendered
    assert "100.00%" in rendered

    out_file = tmp_path / "report.md"
    write_report(metrics_report, out_file)
    assert out_file.exists()
    assert "# Day 08 Lab Report" in out_file.read_text(encoding="utf-8")
