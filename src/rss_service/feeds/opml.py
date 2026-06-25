from xml.etree import ElementTree


def feeds_to_opml(feeds: list[dict[str, object]]) -> str:
    root = ElementTree.Element("opml", {"version": "2.0"})
    body = ElementTree.SubElement(root, "body")
    for feed in feeds:
        ElementTree.SubElement(
            body,
            "outline",
            {
                "type": "rss",
                "text": str(feed["name"]),
                "title": str(feed["name"]),
                "xmlUrl": str(feed["url"]),
                "category": str(feed["category"]),
            },
        )
    return ElementTree.tostring(root, encoding="unicode")
