from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ReportType(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class FeedCreate(BaseModel):
    name: str
    url: HttpUrl
    category: str
    source_type: str = "rss"
    enabled: bool = True
    priority: int = Field(default=50, ge=0, le=100)


class FeedPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    source_type: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    fetch_interval_minutes: int | None = Field(default=None, ge=1)


class FeedRead(BaseModel):
    id: int
    name: str
    url: str
    category: str
    source_type: str
    enabled: bool
    priority: int
    etag: str | None = None
    last_modified: str | None = None
    last_checked_at: str | None = None
    last_success_at: str | None = None
    last_error: str | None = None
    error_count: int
    fetch_interval_minutes: int
    created_at: str
    updated_at: str


class FetchRequest(BaseModel):
    feed_ids: list[int] | None = None
    categories: list[str] | None = None
    force: bool = False


class ExternalSearchItemIn(BaseModel):
    provider: str | None = None
    query: str | None = None
    title: str
    url: HttpUrl
    summary: str
    category: str
    published_at: datetime | None = None
    retrieved_at: datetime


class ExternalItemsRequest(BaseModel):
    items: list[ExternalSearchItemIn]


class ExternalItemsResponse(BaseModel):
    accepted: int
    inserted: int
    updated: int
    skipped: int


class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    at: datetime
    force: bool = False


class ReportRead(BaseModel):
    report_id: str = Field(alias="id")
    report_type: Literal["daily", "weekly", "monthly"]
    period_start: str
    period_end: str
    generated_at: str
    markdown_path: str
    sources_json_path: str
    source_count: int
    item_count: int
    status: str
