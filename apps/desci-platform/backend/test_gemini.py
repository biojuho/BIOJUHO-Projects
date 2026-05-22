import json

import pytest
import requests

API_URL = "http://localhost:8001/analyze"

PAYLOAD = {
    "user_profile": {
        "company_name": "Test Bio",
        "tech_keywords": ["Antibody", "ADC", "Cancer"],
        "tech_description": "Next-gen ADC development",
        "company_size": "Venture",
        "current_trl": "TRL 3",
    },
    "rfp_text": """
    [Notice] 2024 Bio Health R&D

    1. Field: Innovative Drug (Antibody, Cell Therapy)
    2. Target: Venture companies < 7 years
    3. Support: Pre-clinical/Clinical (Max 500M KRW)
    4. Preference: ADC, mRNA
    """,
    "rfp_url": "http://example.com/rfp/123",
}


@pytest.mark.integration
@pytest.mark.external
def test_analyze_with_gemini() -> None:
    try:
        health = requests.get("http://localhost:8001/health", timeout=5)
        if health.status_code >= 500:
            pytest.skip(f"BioLinker service unhealthy: {health.status_code}")
    except requests.RequestException as exc:
        pytest.skip(f"BioLinker service is not reachable on :8001 ({exc})")

    response = requests.post(API_URL, json=PAYLOAD, timeout=120)
    assert response.status_code == 200, response.text

    data = response.json()
    assert "result" in data

    print(json.dumps(data["result"], indent=2, ensure_ascii=False))

    score = data["result"].get("fit_score", 0)
    grade = data["result"].get("fit_grade", "")
    assert score > 0
    assert isinstance(grade, str)
    assert grade
