import time

import requests


def run_manual_api_smoke() -> None:
    base_url = "http://localhost:8002"

    # 1. Create a Product
    print("\n[1] Creating a new product...")
    product_data = {
        "name": "Organic Apple",
        "description": "Fresh organic apple from Sunnyside Farm",
        "category": "Fruit",
        "origin": "Korea",
        "requires_cold_chain": True,
    }

    try:
        response = requests.post(
            f"{base_url}/products/", json=product_data, params={"owner_id": "farmer-001"}, timeout=10
        )
        response.raise_for_status()
        product = response.json()
        product_id = product["id"]
        print(f"✅ Product created successfully. ID: {product_id}")
    except Exception as e:
        print(f"❌ Failed to create product: {e}")
        return

    # 2. Add Tracking Events
    print(f"\n[2] Adding tracking events to product {product_id}...")
    tracking_events = [
        {"status": "REGISTERED", "location": "Farm Depot", "handler_id": "FARMER-01"},
        {"status": "IN_TRANSIT", "location": "Seoul Distribution Center", "handler_id": "LOGISTICS-02"},
        {"status": "DELIVERED", "location": "Retail Store A", "handler_id": "STORE-01"},
    ]

    for event in tracking_events:
        try:
            res = requests.post(f"{base_url}/products/{product_id}/track", params=event, timeout=10)
            res.raise_for_status()
            print(f"✅ Tracking event added: {event['status']} at {event['location']}")
            time.sleep(1)  # simulate slight delay for chronological testing
        except Exception as e:
            print(f"❌ Failed to add tracking event: {e}")

    # 3. Add Certification
    print(f"\n[3] Adding certification to product {product_id}...")
    try:
        res = requests.post(
            f"{base_url}/products/{product_id}/certifications",
            params={"cert_type": "Organic GAP", "issued_by": "Korean Food Safety Authority"},
            timeout=10,
        )
        res.raise_for_status()
        print("✅ Certification added successfully.")
    except Exception as e:
        print(f"❌ Failed to add certification: {e}")

    # 4. Fetch History
    print(f"\n[4] Fetching full tracking history for product {product_id}...")
    try:
        res = requests.get(f"{base_url}/products/{product_id}/history", timeout=10)
        res.raise_for_status()
        history = res.json()
        print(f"✅ Fetched History ({len(history.get('history', []))} records):")
        for record in history.get("history", []):
            print(f"   - Block {record.get('block')}: {record.get('data', {}).get('action')}")
    except Exception as e:
        print(f"❌ Failed to fetch history: {e}")


if __name__ == "__main__":
    run_manual_api_smoke()
