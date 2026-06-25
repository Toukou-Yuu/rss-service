from rss_service.feeds.normalizer import canonicalize_url, clean_summary


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    url = "HTTPS://Example.COM/path?a=1&utm_source=x&fbclid=y#top"
    assert canonicalize_url(url) == "https://example.com/path?a=1"


def test_clean_summary_strips_html_entities_and_whitespace() -> None:
    summary = clean_summary("<p>Hello&nbsp; <strong>RSS</strong></p>\n\nWorld", 240)
    assert summary == "Hello RSS World"
