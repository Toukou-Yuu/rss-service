from tests.snapshot.test_daily_report_snapshot import _generate


def test_weekly_report_snapshot(isolated_env: None) -> None:
    markdown, sources = _generate("weekly", "2026-06-29T10:00:00+08:00")
    assert "# Hikari Weekly Briefing - 2026-W26" in markdown
    assert "knowledge_base_write: false" in markdown
    assert markdown.index("## 本周概览") < markdown.index("## 本周趋势")
    assert markdown.index("## 本周趋势") < markdown.index("## AI 与 Agent")
    assert markdown.index("## AI 与 Agent") < markdown.index("## 后续可跟进主题")
    assert "content:" not in markdown
    assert sources["report_id"] == "weekly-2026-W26"
