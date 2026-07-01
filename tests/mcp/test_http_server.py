from rss_service.mcp.server import create_mcp_http_app, create_mcp_server


def test_create_mcp_http_app_exposes_asgi_app() -> None:
    app = create_mcp_http_app(host="127.0.0.1", port=8788, path="/mcp")

    assert callable(app)


def test_mcp_server_uses_service_name_and_http_path() -> None:
    server = create_mcp_server(host="127.0.0.1", port=8788, path="/mcp")

    assert server.name == "rss-service"
    assert server.settings.streamable_http_path == "/mcp"
