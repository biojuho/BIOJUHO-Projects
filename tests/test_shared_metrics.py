from types import SimpleNamespace

from packages.shared.metrics import _normalize_request_path


def test_normalize_request_path_prefers_route_template():
    request = SimpleNamespace(
        url=SimpleNamespace(path="/products/123"),
        scope={"route": SimpleNamespace(path="/products/{product_id}")},
    )

    assert _normalize_request_path(request) == "/products/{product_id}"


def test_normalize_request_path_falls_back_to_raw_path():
    request = SimpleNamespace(
        url=SimpleNamespace(path="/products/123"),
        scope={},
    )

    assert _normalize_request_path(request) == "/products/123"
