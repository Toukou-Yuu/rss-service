import json
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from rss_service.api.deps import repository_dep, require_token, settings_dep
from rss_service.db.repository import Repository
from rss_service.models import ReportGenerateRequest
from rss_service.reports.generator import ReportGenerator
from rss_service.settings import Settings

router = APIRouter(dependencies=[Depends(require_token)], tags=["reports"])


@router.post("/reports/generate")
def generate_report(
    payload: ReportGenerateRequest,
    repository: Annotated[Repository, Depends(repository_dep)],
    settings: Annotated[Settings, Depends(settings_dep)],
) -> dict[str, Any]:
    return ReportGenerator(repository, settings).generate(
        report_type=payload.report_type.value,
        at=payload.at,
        force=payload.force,
    )


@router.get("/reports")
def list_reports(
    repository: Annotated[Repository, Depends(repository_dep)],
) -> list[dict[str, Any]]:
    return repository.list_reports()


@router.get("/reports/{report_id}")
def get_report(
    report_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {
        "report_id": report["id"],
        "markdown": Path(str(report["markdown_path"])).read_text(encoding="utf-8"),
        "sources": json.loads(Path(str(report["sources_json_path"])).read_text(encoding="utf-8")),
        "metadata": report,
    }


@router.get("/reports/{report_id}/markdown", response_class=PlainTextResponse)
def get_report_markdown(
    report_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> str:
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return Path(str(report["markdown_path"])).read_text(encoding="utf-8")


@router.get("/reports/{report_id}/sources")
def get_report_sources(
    report_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, Any]:
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return cast(
        dict[str, Any],
        json.loads(Path(str(report["sources_json_path"])).read_text(encoding="utf-8")),
    )


@router.delete("/reports/{report_id}")
def delete_report(
    report_id: str,
    repository: Annotated[Repository, Depends(repository_dep)],
) -> dict[str, bool]:
    deleted = repository.delete_report(report_id)
    repository.connection.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="report not found")
    return {"deleted": True}
