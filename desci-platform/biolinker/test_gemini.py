import requests
import json
import sys

# Safe print function for Windows console
def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))

url = "http://localhost:8001/analyze"

payload = {
    "user_profile": {
        "company_name": "Test Bio",
        "tech_keywords": ["Antibody", "ADC", "Cancer"],
        "tech_description": "Next-gen ADC development",
        "company_size": "Venture",
        "current_trl": "TRL 3"
    },
    "rfp_text": """
    [Notice] 2024 Bio Health R&D
    
    1. Field: Innovative Drug (Antibody, Cell Therapy)
    2. Target: Venture companies < 7 years
    3. Support: Pre-clinical/Clinical (Max 500M KRW)
    4. Preference: ADC, mRNA
    """,
    "rfp_url": "http://example.com/rfp/123"
}

safe_print("Sending request to BioLinker...")
try:
    response = requests.post(url, json=payload, timeout=120)
    safe_print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        safe_print("\n=== Analysis Result ===")
        safe_print(json.dumps(data['result'], indent=2, ensure_ascii=False))
        
        # Validation
        score = data['result']['fit_score']
        grade = data['result']['fit_grade']
        safe_print(f"\nScore: {score}, Grade: {grade}")
        
        if score > 0:
            safe_print("[SUCCESS] Gemini Pro Integration Successful!")
        else:
            safe_print("[WARNING] Score is 0 (Analysis might have failed or Mock used)")
    else:
        safe_print(f"[ERROR] Error: {response.text}")

except Exception as e:
    safe_print(f"[EXCEPTION] {e}")
