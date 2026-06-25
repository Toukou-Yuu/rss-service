from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ReportPeriod:
    report_id: str
    label: str
    period_start: datetime
    period_end: datetime


def ensure_timezone(value: datetime, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def compute_report_period(report_type: str, at: datetime, timezone: str) -> ReportPeriod:
    local_at = ensure_timezone(at, timezone)
    if report_type == "daily":
        end = local_at
        start = end - timedelta(hours=24)
        label = end.strftime("%Y-%m-%d")
        return ReportPeriod(
            report_id=f"daily-{label}",
            label=label,
            period_start=start,
            period_end=end,
        )
    if report_type == "weekly":
        current_week_start = _day_start(local_at - timedelta(days=local_at.weekday()))
        start = current_week_start - timedelta(days=7)
        end = current_week_start
        iso = start.isocalendar()
        label = f"{iso.year}-W{iso.week:02d}"
        return ReportPeriod(
            report_id=f"weekly-{label}",
            label=label,
            period_start=start,
            period_end=end,
        )
    if report_type == "monthly":
        current_month_start = _day_start(local_at.replace(day=1))
        previous_month_end = current_month_start
        previous_month_last_day = current_month_start - timedelta(days=1)
        start = _day_start(previous_month_last_day.replace(day=1))
        label = start.strftime("%Y-%m")
        return ReportPeriod(
            report_id=f"monthly-{label}",
            label=label,
            period_start=start,
            period_end=previous_month_end,
        )
    raise ValueError(f"unsupported report type: {report_type}")


def _day_start(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)
