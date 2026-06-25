import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

TRACKING_PARAMS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid", "ref", "spm"}


def canonicalize_url(url: str) -> str:
    stripped = url.strip()
    parts = urlsplit(stripped)
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    query_pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in TRACKING_PARAMS:
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((scheme, host, parts.path, query, ""))


def clean_summary(value: str, max_length: int = 240) -> str:
    text = BeautifulSoup(value, "html.parser").get_text(" ")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def normalize_title(title: str) -> str:
    text = html.unescape(title)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"[^\w\s.-]", "", text)


def is_http_url(url: str) -> bool:
    return urlsplit(url).scheme.lower() in {"http", "https"}
