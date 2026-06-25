import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import yaml

from rss_service.db.repository import Repository, utc_now
from rss_service.logging import log_extra
from rss_service.reports.periods import ReportPeriod, compute_report_period
from rss_service.reports.renderer import render_report
from rss_service.reports.sources import build_sources_json
from rss_service.reports.writer import atomic_write_json, atomic_write_text
from rss_service.settings import Settings

LOGGER = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, repository: Repository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def generate(self, *, report_type: str, at: datetime, force: bool = False) -> dict[str, Any]:
        period = compute_report_period(report_type, at, self.settings.timezone)
        existing = self.repository.get_report(period.report_id)
        if existing and not force:
            return existing

        log_extra(
            LOGGER,
            logging.INFO,
            "report_generation_started",
            report_id=period.report_id,
            report_type=report_type,
        )
        generated_at = utc_now()
        selected_items = self._select_items(report_type, period)
        markdown_path, sources_path = self._report_paths(report_type, period)
        sources_payload = build_sources_json(
            report_id=period.report_id,
            report_type=report_type,
            period_start=period.period_start.isoformat(),
            period_end=period.period_end.isoformat(),
            generated_at=generated_at,
            items=selected_items,
        )
        markdown = render_report(
            report_type,
            {
                "report_id": period.report_id,
                "report_type": report_type,
                "period_label": period.label,
                "period_start": period.period_start.isoformat(),
                "period_end": period.period_end.isoformat(),
                "generated_at": generated_at,
                "source_count": len(selected_items),
                "item_count": len(selected_items),
                "sections": self._sections_for_render(selected_items),
                "overview": self._overview(selected_items),
            },
        )
        atomic_write_text(markdown_path, markdown)
        atomic_write_json(sources_path, sources_payload)
        report = self.repository.save_report(
            report_id=period.report_id,
            report_type=report_type,
            period_start=period.period_start.isoformat(),
            period_end=period.period_end.isoformat(),
            generated_at=generated_at,
            markdown_path=str(markdown_path),
            sources_json_path=str(sources_path),
            source_count=len(selected_items),
            item_count=len(selected_items),
            items=selected_items,
        )
        log_extra(
            LOGGER,
            logging.INFO,
            "report_generation_completed",
            report_id=period.report_id,
            item_count=len(selected_items),
        )
        return report

    def _select_items(self, report_type: str, period: ReportPeriod) -> list[dict[str, Any]]:
        categories = _load_yaml(self.settings.config_dir / "categories.yaml")["categories"]
        period_start = period.period_start.isoformat()
        period_end = period.period_end.isoformat()
        rss_items = [
            _rss_projection(item, categories)
            for item in self.repository.list_entries(
                limit=1000,
                period_start=period_start,
                period_end=period_end,
            )
        ]
        external_items = [
            _external_projection(item, categories)
            for item in self.repository.list_external_items(
                limit=1000,
                period_start=period_start,
                period_end=period_end,
            )
        ]
        candidates = sorted(
            [*rss_items, *external_items],
            key=lambda item: (item["sort_time"], item["priority"]),
            reverse=True,
        )
        seen: set[str] = set()
        grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in categories}
        for item in candidates:
            key = f"{item['primary_url']}|{item['title'].lower()}"
            if key in seen:
                continue
            seen.add(key)
            grouped.setdefault(item["category"], []).append(item)

        selected: list[dict[str, Any]] = []
        for category, config in categories.items():
            limit = int(config.get(f"default_limit_{report_type}", 10))
            section_name = str(config["report_section"])
            for rank, item in enumerate(grouped.get(category, [])[:limit], start=1):
                item["section_name"] = section_name
                item["rank_in_section"] = rank
                selected.append(item)
        return selected

    def _sections_for_render(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        categories = _load_yaml(self.settings.config_dir / "categories.yaml")["categories"]
        sections: list[dict[str, Any]] = []
        for category, config in categories.items():
            section_items = [item for item in items if item["category"] == category]
            sections.append(
                {
                    "category": category,
                    "name": config["report_section"],
                    "entries": section_items,
                }
            )
        return sections

    def _overview(self, items: list[dict[str, Any]]) -> list[str]:
        if not items:
            return ["本周期未收集到符合条件的新条目。"]
        return [f"{item['section_name']}：{item['title']}" for item in items[:5]]

    def _report_paths(self, report_type: str, period: ReportPeriod) -> tuple[Path, Path]:
        base = self.settings.reports_dir / report_type
        markdown = base / f"{period.label}.md"
        sources = base / f"{period.label}.sources.json"
        return markdown, sources


def _load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def _rss_projection(item: dict[str, Any], categories: dict[str, Any]) -> dict[str, Any]:
    source_type = "RSSHub" if item["feed_source_type"] == "rsshub" else "RSS"
    category = str(item["category"])
    return {
        "item_id": item["id"],
        "item_source": "rss",
        "category": category,
        "section_name": categories[category]["report_section"],
        "rank_in_section": 0,
        "title": item["title"],
        "summary": item["summary"],
        "primary_url": item["canonical_url"],
        "source_type": source_type,
        "source_name": item["feed_name"],
        "feed_id": item["feed_id"],
        "feed_url": item["feed_url"],
        "provider": None,
        "query": None,
        "published_at": item["published_at"],
        "retrieved_at": None,
        "sort_time": item["published_at"] or item["fetched_at"],
        "priority": int(item["feed_priority"]),
    }


def _external_projection(item: dict[str, Any], categories: dict[str, Any]) -> dict[str, Any]:
    category = str(item["category"])
    return {
        "item_id": item["id"],
        "item_source": "external",
        "category": category,
        "section_name": categories[category]["report_section"],
        "rank_in_section": 0,
        "title": item["title"],
        "summary": item["summary"],
        "primary_url": item["canonical_url"],
        "source_type": "Web Search",
        "source_name": item["provider"] or "web_search",
        "feed_id": None,
        "feed_url": None,
        "provider": item["provider"],
        "query": item["query"],
        "published_at": item["published_at"],
        "retrieved_at": item["retrieved_at"],
        "sort_time": item["published_at"] or item["retrieved_at"],
        "priority": 0,
    }
