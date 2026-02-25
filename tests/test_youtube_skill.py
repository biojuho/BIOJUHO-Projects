import requests
import pytest


API_URL = "http://localhost:8001/api/agent/youtube"
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=x7X9w_GIm1s"


@pytest.mark.integration
@pytest.mark.external
def test_youtube_analysis() -> None:
    try:
        health = requests.get("http://localhost:8001/health", timeout=5)
        if health.status_code >= 500:
            pytest.skip(f"BioLinker service unhealthy: {health.status_code}")
    except requests.RequestException as exc:
        pytest.skip(f"BioLinker service is not reachable on :8001 ({exc})")

    payload = {
        "url": TEST_VIDEO_URL,
        "query": "What are the main features of Python mentioned in the video?",
    }
    response = requests.post(API_URL, json=payload, timeout=30)

    assert response.status_code == 200, response.text
    body = response.json()
    if isinstance(body, dict) and body.get("error"):
        pytest.skip(f"YouTube analysis prerequisites are not met: {body['error']}")
    assert isinstance(body.get("analysis"), str)
    assert body["analysis"].strip()
