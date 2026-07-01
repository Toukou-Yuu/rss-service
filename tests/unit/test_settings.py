from rss_service.settings import Settings


def test_blank_fetch_proxy_is_normalized_to_none():
    settings = Settings(RSS_FETCH_PROXY="")
    assert settings.fetch_proxy is None


def test_fetch_proxy_accepts_configured_url():
    settings = Settings(RSS_FETCH_PROXY="http://proxy.example:8080")
    assert settings.fetch_proxy == "http://proxy.example:8080"
