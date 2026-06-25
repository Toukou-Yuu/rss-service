from tests.snapshot.test_daily_report_snapshot import _generate


def test_monthly_report_snapshot(isolated_env: None) -> None:
    markdown, sources = _generate("monthly", "2026-07-01T10:00:00+08:00")
    assert "# Hikari Monthly Briefing - 2026-06" in markdown
    assert "knowledge_base_write: false" in markdown
    assert markdown.index("## 本月概览") < markdown.index("## 本月主题演化")
    assert markdown.index("## 本月主题演化") < markdown.index("## AI 与 Agent")
    assert markdown.index("## AI 与 Agent") < markdown.index("## 长期关注候选")
    assert "content:" not in markdown
    assert sources["report_id"] == "monthly-2026-06"
