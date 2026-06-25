from rss_service.settings import Settings


def scheduler_enabled(settings: Settings) -> bool:
    return settings.enable_internal_scheduler
