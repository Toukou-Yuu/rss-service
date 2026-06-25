from datetime import datetime

from rss_service.reports.periods import compute_report_period


def test_daily_period_is_previous_24_hours() -> None:
    period = compute_report_period(
        "daily",
        datetime.fromisoformat("2026-06-24T10:00:00+08:00"),
        "Asia/Singapore",
    )
    assert period.report_id == "daily-2026-06-24"
    assert period.period_start.isoformat() == "2026-06-23T10:00:00+08:00"
    assert period.period_end.isoformat() == "2026-06-24T10:00:00+08:00"


def test_weekly_period_is_previous_calendar_week() -> None:
    period = compute_report_period(
        "weekly",
        datetime.fromisoformat("2026-06-29T10:00:00+08:00"),
        "Asia/Singapore",
    )
    assert period.report_id == "weekly-2026-W26"
    assert period.period_start.isoformat() == "2026-06-22T00:00:00+08:00"


def test_monthly_period_is_previous_calendar_month() -> None:
    period = compute_report_period(
        "monthly",
        datetime.fromisoformat("2026-07-01T10:00:00+08:00"),
        "Asia/Singapore",
    )
    assert period.report_id == "monthly-2026-06"
    assert period.period_start.isoformat() == "2026-06-01T00:00:00+08:00"
