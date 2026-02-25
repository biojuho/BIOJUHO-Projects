import requests


def run_manual_api_smoke() -> None:
    url = "http://localhost:8002/products/"
    data = {
        "name": "Organic Apple",
        "description": "Fresh organic apple",
        "category": "Fruit",
        "origin": "Korea",
        "requires_cold_chain": False,
    }

    response = requests.post(url, json=data, params={"owner_id": "farmer-001"}, timeout=10)
    print("Create Product Status Code:", response.status_code)
    print("Response:", response.json())

    # Fetch all products
    print("\nFetching all products:")
    res_get = requests.get(url, timeout=10)
    print(res_get.json())


if __name__ == "__main__":
    run_manual_api_smoke()
