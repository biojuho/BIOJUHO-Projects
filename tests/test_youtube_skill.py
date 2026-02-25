import requests
import pytest


API_URL = "http://localhost:8001/api/agent/youtube"
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=x7X9w_GIm1s"


@pytest.mark.integration
@pytest.mark.external
def test_youtube_analysis() -> None:
    payload = {
        "url": TEST_VIDEO_URL,
        "query": "What are the main features of Python mentioned in the video?",
    }
    response = requests.post(API_URL, json=payload, timeout=30)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body.get("analysis"), str)
    assert body["analysis"].strip()
