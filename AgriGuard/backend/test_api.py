import requests

url = "http://localhost:8002/products/"
data = {
    "name": "Organic Apple",
    "description": "Fresh organic apple",
    "category": "Fruit",
    "origin": "Korea",
    "requires_cold_chain": False
}

response = requests.post(url, json=data)
print("Create Product Status Code:", response.status_code)
print("Response:", response.json())

# Fetch all products
print("\nFetching all products:")
res_get = requests.get(url)
print(res_get.json())
